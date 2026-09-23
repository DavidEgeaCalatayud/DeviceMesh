import json
from collections.abc import Sequence
from urllib.request import Request, urlopen

from devicemesh_probe.discovery import HostObservation


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
