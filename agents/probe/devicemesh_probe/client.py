import json
from collections.abc import Sequence
from urllib.request import Request, urlopen

from devicemesh_probe.discovery import HostObservation
from devicemesh_probe.synthetics import SyntheticExecutionResult, SyntheticMonitorSpec


def _quality_attributes(observation: HostObservation) -> dict[str, object]:
    attributes: dict[str, object] = {
        "latencyMs": observation.latency_ms,
        "qualityAttempts": observation.quality_attempts,
        "qualitySuccesses": observation.quality_successes,
    }
    if observation.jitter_ms is not None:
        attributes["jitterMs"] = observation.jitter_ms
    if observation.packet_loss_percent is not None:
        attributes["packetLossPercent"] = observation.packet_loss_percent
    return attributes


def publish_observations(
    server_url: str,
    source: str,
    observations: Sequence[HostObservation],
) -> None:
    payload = {
        "observations": [
            {
                "source": source,
                "observedAt": observation.observed_at.isoformat(),
                "hostname": observation.hostname,
                "ipAddress": observation.ip_address,
                "macAddress": observation.mac_address,
                "manufacturer": None,
                "networkCidr": observation.network_cidr,
                "services": [
                    {
                        "port": service.port,
                        "transport": service.transport,
                        "name": service.name,
                    }
                    for service in observation.services
                ],
                "serviceSnapshotComplete": bool(observation.scanned_tcp_ports),
                "scannedTcpPorts": list(observation.scanned_tcp_ports),
                "attributes": _quality_attributes(observation),
            }
            for observation in observations
        ]
    }
    if not payload["observations"]:
        return
    request = Request(
        f"{server_url.rstrip('/')}/api/v1/discovery/observations",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"DeviceMesh server returned HTTP {response.status}")


def fetch_synthetic_monitors(
    server_url: str,
    probe_token: str,
) -> list[SyntheticMonitorSpec]:
    request = Request(
        f"{server_url.rstrip('/')}/api/v1/probe/synthetic-monitors",
        headers={"Authorization": f"Probe {probe_token}"},
        method="GET",
    )
    with urlopen(request, timeout=15) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"DeviceMesh server returned HTTP {response.status}")
        payload = json.load(response)
    if not isinstance(payload, list):
        raise RuntimeError("DeviceMesh synthetic monitor response is invalid")

    monitors: list[SyntheticMonitorSpec] = []
    for item in payload:
        if not isinstance(item, dict):
            raise RuntimeError("DeviceMesh synthetic monitor item is invalid")
        monitor_id = item.get("id")
        monitor_type = item.get("monitorType")
        target = item.get("target")
        timeout_seconds = item.get("timeoutSeconds")
        interval_seconds = item.get("intervalSeconds")
        if not isinstance(monitor_id, str) or not isinstance(monitor_type, str):
            raise RuntimeError("DeviceMesh synthetic monitor identity is invalid")
        if not isinstance(target, str) or not isinstance(timeout_seconds, int):
            raise RuntimeError("DeviceMesh synthetic monitor target is invalid")
        if not isinstance(interval_seconds, int):
            raise RuntimeError("DeviceMesh synthetic monitor interval is invalid")
        port = item.get("port")
        minimum = item.get("expectedStatusMin")
        maximum = item.get("expectedStatusMax")
        monitors.append(
            SyntheticMonitorSpec(
                id=monitor_id,
                monitor_type=monitor_type,
                target=target,
                port=port if isinstance(port, int) else None,
                expected_status_min=minimum if isinstance(minimum, int) else None,
                expected_status_max=maximum if isinstance(maximum, int) else None,
                timeout_seconds=timeout_seconds,
                interval_seconds=interval_seconds,
            )
        )
    return monitors


def publish_synthetic_results(
    server_url: str,
    probe_token: str,
    probe_id: str,
    results: Sequence[SyntheticExecutionResult],
) -> None:
    if not results:
        return
    payload = {
        "probeId": probe_id,
        "results": [result.as_payload() for result in results],
    }
    request = Request(
        f"{server_url.rstrip('/')}/api/v1/probe/synthetic-results",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Probe {probe_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"DeviceMesh server returned HTTP {response.status}")
