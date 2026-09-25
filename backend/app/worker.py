"""Independent worker process. A PostgreSQL advisory lock elects one scheduler."""
import asyncio
import logging
import signal
from datetime import UTC, datetime

from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.metrics import worker_runs
from app.infrastructure.database import engine
from app.runtime import offline_device_sweeper, synthetic_probe_worker

logger = logging.getLogger(__name__)


async def run_jobs(stop: asyncio.Event) -> None:
    settings = get_settings()
    next_offline = 0.0
    while not stop.is_set():
        for name, due in (("offline", asyncio.get_running_loop().time() >= next_offline),
                          ("synthetics", True)):
            if not due:
                continue
            try:
                if name == "offline":
                    await asyncio.to_thread(offline_device_sweeper.sweep, datetime.now(UTC))
                    next_offline = asyncio.get_running_loop().time() + settings.device_offline_sweep_interval_seconds
                else:
                    await synthetic_probe_worker.run_due(datetime.now(UTC))
                worker_runs.labels(name, "success").inc()
            except Exception:
                worker_runs.labels(name, "failure").inc()
                logger.exception("background job failed; retrying", extra={"route": name})
        try:
            await asyncio.wait_for(stop.wait(), settings.synthetic_probe_sweep_interval_seconds)
        except TimeoutError:
            pass


async def main() -> None:
    configure_logging()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    # Keep this dedicated connection open: PostgreSQL releases the lock on process death.
    while not stop.is_set():
        try:
            with engine.connect() as connection:
                if connection.scalar(text("SELECT pg_try_advisory_lock(684291017)")):
                    try:
                        # Verify lock ownership connection before each bounded iteration.
                        while not stop.is_set():
                            connection.execute(text("SELECT 1"))
                            iteration_stop = asyncio.Event()
                            task = asyncio.create_task(run_jobs(iteration_stop))
                            try:
                                await asyncio.wait_for(stop.wait(), 10)
                            except TimeoutError:
                                pass
                            finally:
                                iteration_stop.set()
                                await task
                    finally:
                        connection.execute(text("SELECT pg_advisory_unlock(684291017)"))
        except Exception:
            logger.exception("worker database unavailable; retrying")
        try:
            await asyncio.wait_for(stop.wait(), 5)
        except TimeoutError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
