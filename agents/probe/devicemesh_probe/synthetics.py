from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx

from devicemesh_probe.config import ProbeConfig


@dataclass(frozen=True, slots=True)
class SyntheticWorkMonitor:
    id: str
    name: str
    kind: str
    target: str
    port: int | None
    timeout_seconds: float
    http_method: str | None
    expected_status: int | None


@dataclass(frozen=True, slots=True)
class SyntheticWork:
    work_id: str
    monitor: SyntheticWorkMonitor


@dataclass(frozen=True, slots=True)
class ProbeOutcome:
    success: bool
    latency_ms: float
    http_status: int | None = None
    error_kind: str | None = None
    error: str | None = None


def _address_allowed(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    )


async def _validate_hostname(hostname: str, port: int) -> None:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(
        hostname,
        port,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP,
    )
    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise ValueError("target DNS resolution returned no addresses")
    rejected = sorted(address for address in addresses if not _address_allowed(address))
    if rejected:
        raise ValueError(f"target resolves to a prohibited address: {rejected[0]}")


def _parse_work(payload: list[dict[str, object]]) -> list[SyntheticWork]:
    items: list[SyntheticWork] = []
    for raw in payload:
        monitor_raw = raw.get("monitor")
        if not isinstance(monitor_raw, dict):
            raise TypeError("synthetic work item is missing monitor data")
        work_id = raw.get("workId")
        monitor_id = monitor_raw.get("id")
        name = monitor_raw.get("name")
        kind = monitor_raw.get("kind")
        target = monitor_raw.get("target")
        timeout = monitor_raw.get("timeoutSeconds")
        if not all(isinstance(value, str) for value in (work_id, monitor_id, name, kind, target)):
            raise ValueError("synthetic work item contains invalid string fields")
        if not isinstance(timeout, (int, float)):
            raise TypeError("synthetic work item timeout is invalid")
        port = monitor_raw.get("port")
        http_method = monitor_raw.get("httpMethod")
        expected_status = monitor_raw.get("expectedStatus")
        items.append(
            SyntheticWork(
                work_id=work_id,
                monitor=SyntheticWorkMonitor(
                    id=monitor_id,
                    name=name,
                    kind=kind,
                    target=target,
                    port=port if isinstance(port, int) else None,
                    timeout_seconds=float(timeout),
                    http_method=http_method if isinstance(http_method, str) else None,
                    expected_status=expected_status if isinstance(expected_status, int) else None,
                ),
            )
        )
    return items


async def execute_work(work: SyntheticWork) -> ProbeOutcome:
    monitor = work.monitor
    started = time.perf_counter()
    try:
        if monitor.kind == "http":
            parsed = urlsplit(monitor.target)
            if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
                raise ValueError("invalid HTTP target")
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            await _validate_hostname(parsed.hostname, port)
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(monitor.timeout_seconds),
                follow_redirects=False,
            ) as client:
                response = await client.request(
                    monitor.http_method or "GET",
                    monitor.target,
                    headers={"User-Agent": "DeviceMesh-Distributed-Probe/1.0"},
                )
            latency = (time.perf_counter() - started) * 1000.0
            expected = monitor.expected_status or 200
            if response.status_code != expected:
                return ProbeOutcome(
                    success=False,
                    latency_ms=latency,
                    http_status=response.status_code,
                    error_kind="http_status",
                    error=f"expected HTTP {expected}, received {response.status_code}",
                )
            return ProbeOutcome(
                success=True,
                latency_ms=latency,
                http_status=response.status_code,
            )

        if monitor.kind == "tcp":
            if monitor.port is None:
                raise ValueError("TCP work item is missing port")
            await _validate_hostname(monitor.target, monitor.port)
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(monitor.target, monitor.port),
                timeout=monitor.timeout_seconds,
            )
            writer.close()
            await writer.wait_closed()
            return ProbeOutcome(
                success=True,
                latency_ms=(time.perf_counter() - started) * 1000.0,
            )

        return ProbeOutcome(
            success=False,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            error_kind="unsupported",
            error="ICMP requires an explicitly privileged probe runtime",
        )
    except TimeoutError:
        return ProbeOutcome(
            success=False,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            error_kind="timeout",
            error="probe timed out",
        )
    except httpx.TimeoutException:
        return ProbeOutcome(
            success=False,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            error_kind="timeout",
            error="probe timed out",
        )
    except socket.gaierror:
        return ProbeOutcome(
            success=False,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            error_kind="dns",
            error="target DNS resolution failed",
        )
    except ValueError as exc:
        return ProbeOutcome(
            success=False,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            error_kind="policy",
            error=str(exc)[:1024],
        )
    except (OSError, httpx.NetworkError) as exc:
        return ProbeOutcome(
            success=False,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            error_kind="connection",
            error=str(exc)[:1024],
        )
    except Exception as exc:  # noqa: BLE001 - worker must report bounded internal failures
        return ProbeOutcome(
            success=False,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            error_kind="internal",
            error=f"{type(exc).__name__}: {exc}"[:1024],
        )


class DistributedSyntheticClient:
    def __init__(self, config: ProbeConfig) -> None:
        token = config.require_synthetic_token()
        self._client = httpx.AsyncClient(
            base_url=config.server_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(20.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def heartbeat(self) -> None:
        response = await self._client.post("/api/v1/probes/heartbeat")
        response.raise_for_status()

    async def claim(self, limit: int = 10) -> list[SyntheticWork]:
        response = await self._client.get("/api/v1/probes/work", params={"limit": limit})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise TypeError("synthetic work response must be a list")
        return _parse_work(payload)

    async def submit(self, work: SyntheticWork, outcome: ProbeOutcome) -> None:
        response = await self._client.post(
            "/api/v1/probes/results",
            json={
                "workId": work.work_id,
                "checkedAt": datetime.now(UTC).isoformat(),
                "success": outcome.success,
                "latencyMs": outcome.latency_ms,
                "httpStatus": outcome.http_status,
                "errorKind": outcome.error_kind,
                "error": outcome.error,
            },
        )
        response.raise_for_status()

    async def run_once(self) -> int:
        await self.heartbeat()
        work_items = await self.claim()
        for work in work_items:
            outcome = await execute_work(work)
            await self.submit(work, outcome)
        return len(work_items)


async def run_synthetic_loop(config: ProbeConfig, *, once: bool = False) -> None:
    client = DistributedSyntheticClient(config)
    try:
        while True:
            try:
                count = await client.run_once()
                if count:
                    print(f"completed {count} synthetic work item(s)")
            except httpx.HTTPError as exc:
                print(f"synthetic probe server error: {exc}")
            if once:
                return
            await asyncio.sleep(config.synthetic_poll_seconds)
    finally:
        await client.close()
