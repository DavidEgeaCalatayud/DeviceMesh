from __future__ import annotations

import math
import os
import re
import socket
import ssl
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

_HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_LATENCY = re.compile(r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class SyntheticMonitorSpec:
    id: str
    monitor_type: str
    target: str
    port: int | None
    expected_status_min: int | None
    expected_status_max: int | None
    timeout_seconds: int
    interval_seconds: int = 60


@dataclass(frozen=True, slots=True)
class SyntheticExecutionResult:
    monitor_id: str
    observed_at: datetime
    success: bool
    latency_ms: float | None
    http_status: int | None = None
    failure_reason: str | None = None

    def as_payload(self) -> dict[str, object]:
        return {
            "monitorId": self.monitor_id,
            "observedAt": self.observed_at.isoformat(),
            "success": self.success,
            "latencyMs": self.latency_ms,
            "httpStatus": self.http_status,
            "failureReason": self.failure_reason,
            "attributes": {},
        }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


def _valid_host(host: str) -> bool:
    candidate = host.strip()
    if candidate != host or not candidate or len(candidate) > 253:
        return False
    try:
        socket.inet_pton(socket.AF_INET, candidate)
        return True
    except OSError:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, candidate.strip("[]"))
        return True
    except OSError:
        labels = candidate.rstrip(".").split(".")
        return bool(labels) and all(_HOST_LABEL.fullmatch(label) for label in labels)


def execute_monitor(monitor: SyntheticMonitorSpec) -> SyntheticExecutionResult:
    if monitor.monitor_type == "http":
        return _execute_http(monitor)
    if monitor.monitor_type == "tcp":
        return _execute_tcp(monitor)
    if monitor.monitor_type == "icmp":
        return _execute_icmp(monitor)
    return SyntheticExecutionResult(
        monitor_id=monitor.id,
        observed_at=datetime.now(UTC),
        success=False,
        latency_ms=None,
        failure_reason="unsupported_monitor_type",
    )


def _execute_http(monitor: SyntheticMonitorSpec) -> SyntheticExecutionResult:
    started = time.perf_counter()
    observed_at = datetime.now(UTC)
    request = Request(
        monitor.target,
        headers={"User-Agent": "DeviceMesh-Probe/0.2"},
        method="GET",
    )
    status_code: int | None = None
    try:
        with build_opener(_NoRedirect).open(request, timeout=monitor.timeout_seconds) as response:
            status_code = response.status
    except HTTPError as exc:
        status_code = exc.code
    except TimeoutError:
        return _failure(monitor.id, observed_at, started, "timeout")
    except ssl.SSLError:
        return _failure(monitor.id, observed_at, started, "tls_error")
    except URLError as exc:
        if isinstance(exc.reason, socket.gaierror):
            reason = "dns_error"
        elif isinstance(exc.reason, TimeoutError):
            reason = "timeout"
        else:
            reason = "connection_error"
        return _failure(monitor.id, observed_at, started, reason)
    except OSError:
        return _failure(monitor.id, observed_at, started, "connection_error")

    latency_ms = (time.perf_counter() - started) * 1000.0
    minimum = monitor.expected_status_min or 200
    maximum = monitor.expected_status_max or 399
    success = status_code is not None and minimum <= status_code <= maximum
    return SyntheticExecutionResult(
        monitor_id=monitor.id,
        observed_at=observed_at,
        success=success,
        latency_ms=latency_ms,
        http_status=status_code,
        failure_reason=None if success else f"http_status_{status_code}",
    )


def _execute_tcp(monitor: SyntheticMonitorSpec) -> SyntheticExecutionResult:
    observed_at = datetime.now(UTC)
    started = time.perf_counter()
    if monitor.port is None or not _valid_host(monitor.target):
        return SyntheticExecutionResult(
            monitor_id=monitor.id,
            observed_at=observed_at,
            success=False,
            latency_ms=None,
            failure_reason="invalid_target",
        )
    try:
        with socket.create_connection(
            (monitor.target, monitor.port),
            timeout=monitor.timeout_seconds,
        ):
            pass
    except TimeoutError:
        return _failure(monitor.id, observed_at, started, "timeout")
    except socket.gaierror:
        return _failure(monitor.id, observed_at, started, "dns_error")
    except OSError:
        return _failure(monitor.id, observed_at, started, "connection_error")
    return SyntheticExecutionResult(
        monitor_id=monitor.id,
        observed_at=observed_at,
        success=True,
        latency_ms=(time.perf_counter() - started) * 1000.0,
    )


def _execute_icmp(monitor: SyntheticMonitorSpec) -> SyntheticExecutionResult:
    observed_at = datetime.now(UTC)
    started = time.perf_counter()
    if not _valid_host(monitor.target):
        return SyntheticExecutionResult(
            monitor_id=monitor.id,
            observed_at=observed_at,
            success=False,
            latency_ms=None,
            failure_reason="invalid_target",
        )

    if os.name == "nt":
        command = [
            "ping",
            "-n",
            "1",
            "-w",
            str(max(1, monitor.timeout_seconds * 1000)),
            monitor.target,
        ]
    else:
        command = [
            "ping",
            "-c",
            "1",
            "-W",
            str(max(1, math.ceil(monitor.timeout_seconds))),
            monitor.target,
        ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=monitor.timeout_seconds + 1,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return _failure(monitor.id, observed_at, started, "timeout")
    except OSError:
        return _failure(monitor.id, observed_at, started, "ping_unavailable")

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    output = f"{completed.stdout}\n{completed.stderr}"
    match = _LATENCY.search(output)
    latency_ms = float(match.group(1)) if match else elapsed_ms
    success = completed.returncode == 0
    return SyntheticExecutionResult(
        monitor_id=monitor.id,
        observed_at=observed_at,
        success=success,
        latency_ms=latency_ms,
        failure_reason=None if success else "icmp_unreachable",
    )


def _failure(
    monitor_id: str,
    observed_at: datetime,
    started: float,
    reason: str,
) -> SyntheticExecutionResult:
    return SyntheticExecutionResult(
        monitor_id=monitor_id,
        observed_at=observed_at,
        success=False,
        latency_ms=(time.perf_counter() - started) * 1000.0,
        failure_reason=reason,
    )
