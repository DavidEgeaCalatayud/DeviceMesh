from __future__ import annotations

import asyncio
import ipaddress
import socket
import ssl
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from app.domain.synthetics.models import (
    SyntheticCheckErrorKind,
    SyntheticMonitor,
    SyntheticMonitorKind,
)
from app.infrastructure.repositories.synthetic_http import SyntheticHttpSettings
from app.infrastructure.synthetic_secrets import SyntheticSecretResolver


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


async def _resolved_addresses(hostname: str, port: int, *, sock_type: int = socket.SOCK_STREAM) -> set[str]:
    if not hostname or len(hostname) > 253:
        raise SyntheticTargetPolicyError("target hostname is invalid")
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(hostname, port, type=sock_type)
    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise socket.gaierror("target DNS resolution returned no addresses")
    return addresses


async def validate_hostname(hostname: str, port: int) -> None:
    try:
        addresses = await _resolved_addresses(hostname, port)
    except socket.gaierror as exc:
        raise SyntheticTargetPolicyError("target DNS resolution failed") from exc
    rejected = sorted(address for address in addresses if not _address_allowed(address))
    if rejected:
        raise SyntheticTargetPolicyError(
            f"target resolves to a prohibited address: {rejected[0]}"
        )


def _validate_host_only(target: str, label: str) -> None:
    if "://" in target or not target or len(target) > 253:
        raise SyntheticTargetPolicyError(f"{label} target must be a hostname or IP, not a URL")


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
        _validate_host_only(target, "TCP")
        if port is None or not 1 <= port <= 65535:
            raise SyntheticTargetPolicyError("TCP monitor requires a valid port")
        if http_method is not None or expected_status is not None:
            raise SyntheticTargetPolicyError("HTTP expectations are only valid for HTTP monitors")
        return

    if kind is SyntheticMonitorKind.ICMP:
        _validate_host_only(target, "ICMP")
        if port is not None or http_method is not None or expected_status is not None:
            raise SyntheticTargetPolicyError("ICMP monitor does not accept port or HTTP fields")
        return

    if kind is SyntheticMonitorKind.DNS:
        _validate_host_only(target, "DNS")
        if port is not None or http_method is not None or expected_status is not None:
            raise SyntheticTargetPolicyError("DNS monitor does not accept port or HTTP fields")
        return

    if kind is SyntheticMonitorKind.TLS:
        _validate_host_only(target, "TLS")
        if port is not None and not 1 <= port <= 65535:
            raise SyntheticTargetPolicyError("TLS monitor port must be between 1 and 65535")
        if http_method is not None or expected_status is not None:
            raise SyntheticTargetPolicyError("TLS monitor does not accept HTTP fields")
        return

    raise SyntheticTargetPolicyError("unsupported synthetic monitor kind")


class SyntheticProbeExecutor:
    def __init__(self, secret_resolver: SyntheticSecretResolver | None = None) -> None:
        self._secret_resolver = secret_resolver

    async def execute(
        self,
        monitor: SyntheticMonitor,
        http_settings: SyntheticHttpSettings | None = None,
    ) -> ProbeOutcome:
        started = time.perf_counter()
        try:
            if monitor.kind is SyntheticMonitorKind.HTTP:
                return await self._http(monitor, started, http_settings)
            if monitor.kind is SyntheticMonitorKind.TCP:
                return await self._tcp(monitor, started)
            if monitor.kind is SyntheticMonitorKind.DNS:
                return await self._dns(monitor, started)
            if monitor.kind is SyntheticMonitorKind.TLS:
                return await self._tls(monitor, started)
            return ProbeOutcome(
                success=False,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                error_kind=SyntheticCheckErrorKind.UNSUPPORTED,
                error="ICMP requires an explicitly privileged distributed probe runtime",
            )
        except SyntheticTargetPolicyError as exc:
            return ProbeOutcome(
                success=False,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                error_kind=SyntheticCheckErrorKind.POLICY,
                error=str(exc),
            )
        except RuntimeError:
            return ProbeOutcome(
                success=False,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                error_kind=SyntheticCheckErrorKind.POLICY,
                error="required synthetic secret is not configured",
            )
        except socket.gaierror:
            return ProbeOutcome(
                success=False,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                error_kind=SyntheticCheckErrorKind.DNS,
                error="target DNS resolution failed",
            )
        except (ssl.SSLError, ssl.CertificateError) as exc:
            return ProbeOutcome(
                success=False,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                error_kind=SyntheticCheckErrorKind.TLS,
                error=f"TLS validation failed: {exc}"[:1024],
            )
        except TimeoutError:
            return ProbeOutcome(
                success=False,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                error_kind=SyntheticCheckErrorKind.TIMEOUT,
                error="probe timed out",
            )
        except httpx.TimeoutException:
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

    async def _http(
        self,
        monitor: SyntheticMonitor,
        started: float,
        settings: SyntheticHttpSettings | None,
    ) -> ProbeOutcome:
        parsed = urlsplit(monitor.target)
        assert parsed.hostname is not None
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        await validate_hostname(parsed.hostname, port)
        headers = {"User-Agent": "DeviceMesh-Synthetic/1.0"}
        if settings is not None:
            headers.update(settings.headers)
            for name, secret_ref in settings.secret_headers.items():
                if self._secret_resolver is None:
                    raise RuntimeError("synthetic secret resolver is unavailable")
                headers[name] = self._secret_resolver.resolve(secret_ref)
        timeout = httpx.Timeout(monitor.timeout_seconds)
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            max_redirects=0,
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
                error_kind=SyntheticCheckErrorKind.HTTP_STATUS,
                error=f"expected HTTP {expected}, received {response.status_code}",
            )
        if settings is not None and settings.expected_body_contains is not None:
            if settings.expected_body_contains not in response.text:
                return ProbeOutcome(
                    success=False,
                    latency_ms=latency,
                    http_status=response.status_code,
                    error_kind=SyntheticCheckErrorKind.ASSERTION,
                    error="expected response body substring was not present",
                )
        return ProbeOutcome(success=True, latency_ms=latency, http_status=response.status_code)

    async def _tcp(self, monitor: SyntheticMonitor, started: float) -> ProbeOutcome:
        assert monitor.port is not None
        await validate_hostname(monitor.target, monitor.port)
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(monitor.target, monitor.port),
            timeout=monitor.timeout_seconds,
        )
        del reader
        writer.close()
        await writer.wait_closed()
        return ProbeOutcome(success=True, latency_ms=(time.perf_counter() - started) * 1000.0)

    async def _dns(self, monitor: SyntheticMonitor, started: float) -> ProbeOutcome:
        addresses = await _resolved_addresses(monitor.target, 443)
        rejected = sorted(address for address in addresses if not _address_allowed(address))
        if rejected:
            raise SyntheticTargetPolicyError(
                f"target resolves to a prohibited address: {rejected[0]}"
            )
        return ProbeOutcome(success=True, latency_ms=(time.perf_counter() - started) * 1000.0)

    async def _tls(self, monitor: SyntheticMonitor, started: float) -> ProbeOutcome:
        port = monitor.port or 443
        await validate_hostname(monitor.target, port)
        context = ssl.create_default_context()
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                monitor.target,
                port,
                ssl=context,
                server_hostname=monitor.target,
            ),
            timeout=monitor.timeout_seconds,
        )
        del reader
        writer.close()
        await writer.wait_closed()
        return ProbeOutcome(success=True, latency_ms=(time.perf_counter() - started) * 1000.0)
