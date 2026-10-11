"""Independent worker process. A PostgreSQL advisory lock elects one scheduler."""
import asyncio
import logging
import signal
import time
from datetime import UTC, datetime, timedelta

from prometheus_client import start_http_server
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.config import get_settings
from app.core.logging import bind_log_context, configure_logging, reset_log_context
from app.core.metrics import (
    retention_deleted,
    retention_rollups,
    worker_last_success,
    worker_leader,
    worker_runs,
)
from app.infrastructure.database import engine
from app.runtime import (
    nms_poll_worker,
    notification_dispatcher,
    offline_device_sweeper,
    synthetic_probe_worker,
    syslog_repository,
    telemetry_retention_repository,
)

logger = logging.getLogger(__name__)


async def run_jobs(stop: asyncio.Event) -> None:
    """Run scheduled work while this process owns the scheduler lease."""
    settings = get_settings()
    next_offline = 0.0
    next_notifications = 0.0
    next_nms = 0.0
    next_retention = 0.0
    while not stop.is_set():
        loop_time = asyncio.get_running_loop().time()
        jobs = (
            ("offline", loop_time >= next_offline),
            ("synthetics", True),
            ("notifications", loop_time >= next_notifications),
            ("nms", loop_time >= next_nms),
            ("retention", loop_time >= next_retention),
        )
        for name, due in jobs:
            if not due:
                continue
            context_token = bind_log_context(job=name)
            try:
                if name == "offline":
                    await asyncio.to_thread(offline_device_sweeper.sweep, datetime.now(UTC))
                    next_offline = (
                        asyncio.get_running_loop().time()
                        + settings.device_offline_sweep_interval_seconds
                    )
                elif name == "notifications":
                    delivered, failed = await asyncio.to_thread(
                        notification_dispatcher.run_due,
                        datetime.now(UTC),
                    )
                    next_notifications = (
                        asyncio.get_running_loop().time()
                        + settings.notification_delivery_interval_seconds
                    )
                    if delivered or failed:
                        logger.info(
                            "notification outbox processed",
                            extra={
                                "route": "notifications",
                                "status": f"delivered={delivered},failed={failed}",
                            },
                        )
                elif name == "nms":
                    succeeded, failed = await asyncio.to_thread(
                        nms_poll_worker.run_due,
                        datetime.now(UTC),
                    )
                    next_nms = (
                        asyncio.get_running_loop().time()
                        + settings.nms_poll_interval_seconds
                    )
                    if succeeded or failed:
                        logger.info(
                            "NMS polling cycle processed",
                            extra={
                                "route": "nms",
                                "status": f"succeeded={succeeded},failed={failed}",
                            },
                        )
                elif name == "retention":
                    result = await asyncio.to_thread(
                        telemetry_retention_repository.enforce_policy,
                        datetime.now(UTC),
                        raw_retention_days=settings.telemetry_raw_retention_days,
                        hourly_retention_days=settings.telemetry_hourly_retention_days,
                        event_retention_days=settings.event_retention_days,
                        synthetic_check_retention_days=settings.synthetic_check_retention_days,
                    )
                    retention_rollups.inc(result.rollups_touched)
                    retention_deleted.labels("telemetry_raw").inc(result.raw_samples_deleted)
                    retention_deleted.labels("telemetry_hourly").inc(result.hourly_rollups_deleted)
                    retention_deleted.labels("device_events").inc(result.events_deleted)
                    retention_deleted.labels("synthetic_checks").inc(
                        result.synthetic_checks_deleted
                    )
                    syslog_deleted = await asyncio.to_thread(
                        syslog_repository.delete_before,
                        datetime.now(UTC) - timedelta(days=settings.syslog_retention_days),
                    )
                    retention_deleted.labels("syslog").inc(syslog_deleted)
                    next_retention = (
                        asyncio.get_running_loop().time()
                        + settings.retention_run_interval_seconds
                    )
                    logger.info(
                        "retention policy enforced",
                        extra={"route": "retention", "status": "success"},
                    )
                else:
                    await synthetic_probe_worker.run_due(datetime.now(UTC))
                worker_runs.labels(name, "success").inc()
                worker_last_success.labels(name).set(time.time())
            except Exception:
                worker_runs.labels(name, "failure").inc()
                logger.exception("background job failed; retrying", extra={"route": name})
            finally:
                reset_log_context(context_token)
        try:
            await asyncio.wait_for(stop.wait(), settings.synthetic_probe_sweep_interval_seconds)
        except TimeoutError:
            pass


async def run_as_leader(connection: Connection, stop: asyncio.Event) -> None:
    """Keep one scheduler alive for the full lifetime of the advisory lock connection."""
    scheduler_stop = asyncio.Event()
    scheduler = asyncio.create_task(run_jobs(scheduler_stop))
    try:
        while not stop.is_set():
            # Advisory locks are connection-scoped. This also detects a dead DB session.
            await asyncio.to_thread(connection.execute, text("SELECT 1"))
            try:
                await asyncio.wait_for(stop.wait(), 10)
            except TimeoutError:
                pass
    finally:
        scheduler_stop.set()
        await scheduler


async def main() -> None:
    configure_logging(service_name="scheduler-worker")
    settings = get_settings()
    start_http_server(settings.worker_metrics_port, addr=settings.worker_metrics_host)
    logger.info(
        "worker metrics server started",
        extra={"route": f"{settings.worker_metrics_host}:{settings.worker_metrics_port}"},
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    # Keep this dedicated connection open: PostgreSQL releases the lock on process death.
    while not stop.is_set():
        try:
            with engine.connect() as connection:
                if connection.scalar(text("SELECT pg_try_advisory_lock(684291017)")):
                    worker_leader.set(1)
                    try:
                        await run_as_leader(connection, stop)
                    finally:
                        worker_leader.set(0)
                        connection.execute(text("SELECT pg_advisory_unlock(684291017)"))
                else:
                    worker_leader.set(0)
        except Exception:
            worker_leader.set(0)
            logger.exception("worker database unavailable; retrying")
        try:
            await asyncio.wait_for(stop.wait(), 5)
        except TimeoutError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
