from __future__ import annotations

import asyncio
import ipaddress
import math
import platform
import random
import shutil
import socket
import ssl
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from devicemesh_probe.config import ProbeConfig
from devicemesh_probe.outbox import ResultOutbox
from devicemesh_probe.synthetic_secrets import SyntheticSecretResolver


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
    http_headers: dict[str, str]
    http_secret_headers: dict[str, str]
    expected_body_contains: str | None


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


async def _resolved_addresses(hostname: str, port: int, *, sock_type: int = socket.SOCK_STREAM) -> set[str]:
    if not hostname or len(hostname) > 253:
        raise ValueError("target hostname is invalid")
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(hostname, port, type=sock_type)
    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise socket.gaierror("target DNS resolution returned no addresses")
    return addresses


async def _validate_hostname(hostname: str, port: int) -> None:
    addresses = await _resolved_addresses(hostname, port)
    rejected = sorted(address for address in addresses if not _address_allowed(address))
    if rejected:
        raise ValueError(f"target resolves to a prohibited address: {rejected[0]}")


def _string_map(raw: object, *, field: str) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise TypeError(f"synthetic work item {field} is invalid")
    if len(raw) > 32:
        raise ValueError(f"synthetic work item {field} exceeds 32 entries")
    result: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise TypeError(f"synthetic work item {field} must contain string pairs")
        result[key] = value
    return result


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
        expected_body_contains = monitor_raw.get("expectedBodyContains")
        if expected_body_contains is not None and not isinstance(expected_body_contains, str):
            raise TypeError("synthetic work item expectedBodyContains is invalid")
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
                    http_headers=_string_map(monitor_raw.get("httpHeaders"), field="httpHeaders"),
                    http_secret_headers=_string_map(
                        monitor_raw.get("httpSecretHeaders"),
                        field="httpSecretHeaders",
                    ),
                    expected_body_contains=expected_body_contains,
                ),
            )
        )
    return items


async def _execute_icmp(target: str, timeout_seconds: float) -> tuple[bool, str | None]:
    ping = shutil.which("ping")
    if ping is None:
        return False, "ping executable is not installed in the probe runtime"

    system = platform.system()
    if system == "Darwin":
        args = [ping, "-n", "-c", "1", "-W", str(max(1, int(timeout_seconds * 1000))), target]
    else:
        args = [ping, "-n", "-c", "1", "-W", str(max(1, math.ceil(timeout_seconds))), target]

    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds + 1.0)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise
    if process.returncode == 0:
        return True, None
    message = stderr.decode(errors="replace").strip()[:512]
    return False, message or f"ping exited with status {process.returncode}"


async def execute_work(
    work: SyntheticWork,
    secret_resolver: SyntheticSecretResolver | None = None,
) -> ProbeOutcome:
    monitor = work.monitor
    started = time.perf_counter()
    try:
        if monitor.kind == "http":
            parsed = urlsplit(monitor.target)
            if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
                raise ValueError("invalid HTTP target")
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            await _validate_hostname(parsed.hostname, port)
            headers = {"User-Agent": "DeviceMesh-Distributed-Probe/1.0", **monitor.http_headers}
            for name, secret_ref in monitor.http_secret_headers.items():
                if secret_resolver is None:
                    raise RuntimeError("required synthetic secret is not configured")
                headers[name] = secret_resolver.resolve(secret_ref)
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(monitor.timeout_seconds),
                follow_redirects=False,
            ) as client:
                response = await client.request(
                    monitor.http_method or "GET",
                    monitor.target,
                    headers=headers,
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
            if (
                monitor.expected_body_contains is not None
                and monitor.expected_body_contains not in response.text
            ):
                return ProbeOutcome(
                    success=False,
                    latency_ms=latency,
                    http_status=response.status_code,
                    error_kind="assertion",
                    error="expected response body substring was not present",
                )
            return ProbeOutcome(success=True, latency_ms=latency, http_status=response.status_code)

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
            return ProbeOutcome(success=True, latency_ms=(time.perf_counter() - started) * 1000.0)

        if monitor.kind == "dns":
            addresses = await _resolved_addresses(monitor.target, 443)
            rejected = sorted(address for address in addresses if not _address_allowed(address))
            if rejected:
                raise ValueError(f"target resolves to a prohibited address: {rejected[0]}")
            return ProbeOutcome(success=True, latency_ms=(time.perf_counter() - started) * 1000.0)

        if monitor.kind == "tls":
            port = monitor.port or 443
            await _validate_hostname(monitor.target, port)
            context = ssl.create_default_context()
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    monitor.target,
                    port,
                    ssl=context,
                    server_hostname=monitor.target,
                ),
                timeout=monitor.timeout_seconds,
            )
            writer.close()
            await writer.wait_closed()
            return ProbeOutcome(success=True, latency_ms=(time.perf_counter() - started) * 1000.0)

        if monitor.kind == "icmp":
            await _validate_hostname(monitor.target, 443)
            success, error = await _execute_icmp(monitor.target, monitor.timeout_seconds)
            return ProbeOutcome(
                success=success,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                error_kind=None if success else "connection",
                error=error,
            )

        return ProbeOutcome(
            success=False,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            error_kind="unsupported",
            error=f"unsupported synthetic monitor kind: {monitor.kind}",
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
    except (ssl.SSLError, ssl.CertificateError) as exc:
        return ProbeOutcome(
            success=False,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            error_kind="tls",
            error=f"TLS validation failed: {exc}"[:1024],
        )
    except RuntimeError:
        return ProbeOutcome(
            success=False,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            error_kind="policy",
            error="required synthetic secret is not configured",
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
    def __init__(self, config: ProbeConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.config = config
        self.outbox = ResultOutbox(Path(config.result_queue_path))
        self._secret_resolver = SyntheticSecretResolver(config.synthetic_secret_directory)
        token = config.require_synthetic_token()
        self._client = httpx.AsyncClient(
            transport=transport,
            base_url=config.server_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(20.0),
        )

    async def close(self) -> None:
        await self._client.aclose()
        self.outbox.close()

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
        self.outbox.enqueue({
            "workId": work.work_id,
            "checkedAt": datetime.now(UTC).isoformat(),
            "success": outcome.success,
            "latencyMs": outcome.latency_ms,
            "httpStatus": outcome.http_status,
            "errorKind": outcome.error_kind,
            "error": outcome.error,
        })

    async def flush(self) -> None:
        for work_id, payload in self.outbox.pending():
            response = await self._client.post("/api/v1/probes/results", json=payload)
            response.raise_for_status()
            self.outbox.acknowledge(work_id)

    async def run_once(self) -> int:
        await self.heartbeat()
        await self.flush()
        capacity = min(self.config.max_concurrent_checks, self.outbox.capacity - self.outbox.count())
        if capacity <= 0:
            return 0
        work_items = await self.claim(limit=capacity)
        targets: dict[str, asyncio.Semaphore] = {}

        async def run(work: SyntheticWork) -> None:
            target = urlsplit(work.monitor.target).hostname or work.monitor.target
            lock = targets.setdefault(target, asyncio.Semaphore(1))
            async with lock:
                try:
                    async with asyncio.timeout(work.monitor.timeout_seconds):
                        outcome = await execute_work(work, self._secret_resolver)
                except TimeoutError:
                    outcome = ProbeOutcome(
                        False,
                        work.monitor.timeout_seconds * 1000,
                        error_kind="timeout",
                        error="total check deadline exceeded",
                    )
                await self.submit(work, outcome)

        await asyncio.gather(*(run(work) for work in work_items))
        await self.flush()
        return len(work_items)


async def run_synthetic_loop(config: ProbeConfig, *, once: bool = False) -> None:
    client = DistributedSyntheticClient(config)
    failures = 0
    try:
        while True:
            try:
                count = await client.run_once()
                failures = 0
                if count:
                    print(f"completed {count} synthetic work item(s)")
            except httpx.HTTPError as exc:
                failures = min(failures + 1, 6)
                print(f"synthetic probe server unavailable: {type(exc).__name__}; queued results retained")
            if once:
                return
            await asyncio.sleep(
                min(300, config.synthetic_poll_seconds * (2**failures)) * random.uniform(0.8, 1.2)
            )
    finally:
        await client.close()
