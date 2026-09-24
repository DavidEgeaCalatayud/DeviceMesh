from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from app.domain.synthetics.models import (
    SyntheticCheckErrorKind,
    SyntheticMonitor,
    SyntheticMonitorKind,
)


@dataclass(frozen=True, slots=True)
class ProbeOutcome:
    success: bool
    latency_ms: float
    http_status: int | None = None
    error_kind: SyntheticCheckErrorKind | None = None
    error: str | None = None


class SyntheticTargetPolicyError(ValueError):
    pass


def _address_allowed(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    )


async def validate_hostname(hostname: str, port: int) -> None:
    if not hostname or len(hostname) > 253:
        raise SyntheticTargetPolicyError("target hostname is invalid")
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        raise SyntheticTargetPolicyError("target DNS resolution failed") from exc
    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise SyntheticTargetPolicyError("target DNS resolution returned no addresses")
    rejected = sorted(address for address in addresses if not _address_allowed(address))
    if rejected:
        raise SyntheticTargetPolicyError(
            f"target resolves to a prohibited address: {rejected[0]}"
        )


def validate_monitor_definition(
    *,
    kind: SyntheticMonitorKind,
    target: str,
    port: int | None,
    interval_seconds: int,
    timeout_seconds: float,
    http_method: str | None,
    expected_status: int | None,
) -> None:
    if not 30 <= interval_seconds <= 86400:
        raise SyntheticTargetPolicyError("intervalSeconds must be between 30 and 86400")
    if not 0.5 <= timeout_seconds <= 30.0:
        raise SyntheticTargetPolicyError("timeoutSeconds must be between 0.5 and 30")

    if kind is SyntheticMonitorKind.HTTP:
        parsed = urlsplit(target)
        if parsed.scheme not in {"http", "https"}:
            raise SyntheticTargetPolicyError("HTTP monitor scheme must be http or https")
        if parsed.username is not None or parsed.password is not None:
            raise SyntheticTargetPolicyError("embedded URL credentials are not allowed")
        if parsed.hostname is None:
            raise SyntheticTargetPolicyError("HTTP monitor URL must include a hostname")
        if port is not None:
            raise SyntheticTargetPolicyError("HTTP monitor port must be encoded in the URL")
        if (http_method or "GET").upper() not in {"GET", "HEAD"}:
            raise SyntheticTargetPolicyError("HTTP monitor method must be GET or HEAD")
        if expected_status is not None and not 100 <= expected_status <= 599:
            raise SyntheticTargetPolicyError("expectedStatus must be a valid HTTP status")
        return

    if kind is SyntheticMonitorKind.TCP:
        if "://" in target:
            raise SyntheticTargetPolicyError("TCP target must be a hostname or IP, not a URL")
        if port is None or not 1 <= port <= 65535:
            raise SyntheticTargetPolicyError("TCP monitor requires a valid port")
        if http_method is not None or expected_status is not None:
            raise SyntheticTargetPolicyError("HTTP expectations are only valid for HTTP monitors")
        return

    if kind is SyntheticMonitorKind.ICMP:
        if "://" in target:
            raise SyntheticTargetPolicyError("ICMP target must be a hostname or IP, not a URL")
        if port is not None or http_method is not None or expected_status is not None:
            raise SyntheticTargetPolicyError("ICMP monitor does not accept port or HTTP fields")
        return

    raise SyntheticTargetPolicyError("unsupported synthetic monitor kind")


class SyntheticProbeExecutor:
    async def execute(self, monitor: SyntheticMonitor) -> ProbeOutcome:
        started = time.perf_counter()
        try:
            if monitor.kind is SyntheticMonitorKind.HTTP:
                return await self._http(monitor, started)
            if monitor.kind is SyntheticMonitorKind.TCP:
                return await self._tcp(monitor, started)
            return ProbeOutcome(
                success=False,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                error_kind=SyntheticCheckErrorKind.UNSUPPORTED,
                error="ICMP requires an explicitly privileged probe runtime and is unsupported here",
            )
        except SyntheticTargetPolicyError as exc:
            return ProbeOutcome(
                success=False,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                error_kind=SyntheticCheckErrorKind.POLICY,
                error=str(exc),
            )
        except TimeoutError:
            return ProbeOutcome(
                success=False,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                error_kind=SyntheticCheckErrorKind.TIMEOUT,
                error="probe timed out",
            )
        except (OSError, httpx.NetworkError) as exc:
            return ProbeOutcome(
                success=False,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                error_kind=SyntheticCheckErrorKind.CONNECTION,
                error=str(exc)[:1024],
            )
        except httpx.TimeoutException:
            return ProbeOutcome(
                success=False,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                error_kind=SyntheticCheckErrorKind.TIMEOUT,
                error="probe timed out",
            )

    async def _http(self, monitor: SyntheticMonitor, started: float) -> ProbeOutcome:
        parsed = urlsplit(monitor.target)
        assert parsed.hostname is not None
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        await validate_hostname(parsed.hostname, port)
        timeout = httpx.Timeout(monitor.timeout_seconds)
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            max_redirects=0,
        ) as client:
            response = await client.request(
                monitor.http_method or "GET",
                monitor.target,
                headers={"User-Agent": "DeviceMesh-Synthetic/1.0"},
            )
        latency = (time.perf_counter() - started) * 1000.0
        expected = monitor.expected_status or 200
        if response.status_code != expected:
            return ProbeOutcome(
                success=False,
                latency_ms=latency,
                http_status=response.status_code,
                error_kind=SyntheticCheckErrorKind.HTTP_STATUS,
                error=f"expected HTTP {expected}, received {response.status_code}",
            )
        return ProbeOutcome(success=True, latency_ms=latency, http_status=response.status_code)

    async def _tcp(self, monitor: SyntheticMonitor, started: float) -> ProbeOutcome:
        assert monitor.port is not None
        await validate_hostname(monitor.target, monitor.port)
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(monitor.target, monitor.port),
                timeout=monitor.timeout_seconds,
            )
        except TimeoutError as exc:
            raise TimeoutError from exc
        del reader
        writer.close()
        await writer.wait_closed()
        return ProbeOutcome(success=True, latency_ms=(time.perf_counter() - started) * 1000.0)
