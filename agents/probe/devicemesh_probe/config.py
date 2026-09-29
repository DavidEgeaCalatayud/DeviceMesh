import os
from dataclasses import dataclass
from pathlib import Path

from devicemesh_probe.discovery import DiscoveryScope


@dataclass(frozen=True, slots=True)
class ProbeConfig:
    server_url: str
    source: str
    scopes: tuple[DiscoveryScope, ...]
    tcp_ports: tuple[int, ...] = ()
    synthetic_token: str | None = None
    synthetic_poll_seconds: float = 5.0
    max_concurrent_checks: int = 4
    result_queue_path: str = "data/probe-results.sqlite3"
    synthetic_secret_directory: str = "/run/secrets/devicemesh-synthetics"

    @classmethod
    def from_environment(cls) -> "ProbeConfig":
        raw_scopes = os.environ.get("DEVICEMESH_PROBE_SCOPES", "")
        scopes = tuple(
            DiscoveryScope(value.strip())
            for value in raw_scopes.split(",")
            if value.strip()
        )
        for scope in scopes:
            scope.network()

        raw_ports = os.environ.get("DEVICEMESH_PROBE_TCP_PORTS", "")
        ports = tuple(
            sorted(
                {
                    int(value.strip())
                    for value in raw_ports.split(",")
                    if value.strip()
                }
            )
        )
        if len(ports) > 32:
            raise ValueError("DEVICEMESH_PROBE_TCP_PORTS allows at most 32 ports")
        if any(port < 1 or port > 65535 for port in ports):
            raise ValueError("configured TCP ports must be between 1 and 65535")

        poll_seconds = float(os.environ.get("DEVICEMESH_PROBE_POLL_SECONDS", "5"))
        if poll_seconds < 1.0 or poll_seconds > 300.0:
            raise ValueError("DEVICEMESH_PROBE_POLL_SECONDS must be between 1 and 300")

        concurrency = int(os.environ.get("DEVICEMESH_PROBE_CONCURRENCY", "4"))
        if not 1 <= concurrency <= 32:
            raise ValueError("DEVICEMESH_PROBE_CONCURRENCY must be between 1 and 32")

        token = os.environ.get("DEVICEMESH_PROBE_TOKEN") or None
        token_file = os.environ.get("DEVICEMESH_PROBE_TOKEN_FILE") or None
        if token and token_file:
            raise ValueError("configure only one of DEVICEMESH_PROBE_TOKEN or DEVICEMESH_PROBE_TOKEN_FILE")
        if token_file:
            token = Path(token_file).read_text(encoding="utf-8").strip()
            if not token:
                raise ValueError("DEVICEMESH_PROBE_TOKEN_FILE is empty")

        return cls(
            server_url=os.environ.get("DEVICEMESH_SERVER_URL", "http://localhost:8000"),
            source=os.environ.get("DEVICEMESH_PROBE_SOURCE", "network-probe"),
            scopes=scopes,
            tcp_ports=ports,
            synthetic_token=token,
            synthetic_poll_seconds=poll_seconds,
            max_concurrent_checks=concurrency,
            result_queue_path=os.environ.get("DEVICEMESH_PROBE_QUEUE_PATH", "data/probe-results.sqlite3"),
            synthetic_secret_directory=os.environ.get(
                "DEVICEMESH_SYNTHETIC_SECRET_DIRECTORY",
                "/run/secrets/devicemesh-synthetics",
            ),
        )

    def require_allowed(self, requested: DiscoveryScope) -> None:
        if not self.scopes:
            raise ValueError("DEVICEMESH_PROBE_SCOPES must explicitly allow at least one CIDR")
        network = requested.network()
        if not any(network.subnet_of(allowed.network()) for allowed in self.scopes):
            raise ValueError(f"requested scope {network} is outside DEVICEMESH_PROBE_SCOPES")

    def require_synthetic_token(self) -> str:
        if not self.synthetic_token:
            raise ValueError("DEVICEMESH_PROBE_TOKEN or DEVICEMESH_PROBE_TOKEN_FILE is required for synthetic probe mode")
        return self.synthetic_token
