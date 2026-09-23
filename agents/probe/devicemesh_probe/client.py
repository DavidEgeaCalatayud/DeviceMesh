import json
from collections.abc import Sequence
from urllib.request import Request, urlopen

from devicemesh_probe.discovery import HostObservation


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
                "attributes": {"latencyMs": observation.latency_ms},
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
