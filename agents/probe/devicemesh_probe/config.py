import os
import socket
from dataclasses import dataclass

from devicemesh_probe.discovery import DiscoveryScope


@dataclass(frozen=True, slots=True)
class ProbeConfig:
    server_url: str
    source: str
    scopes: tuple[DiscoveryScope, ...]
    probe_id: str = "network-probe"
    probe_token: str | None = None
    tcp_ports: tuple[int, ...] = ()

    @classmethod
    def from_environment(cls, *, require_scopes: bool = True) -> "ProbeConfig":
        raw_scopes = os.environ.get("DEVICEMESH_PROBE_SCOPES", "")
        scopes = tuple(
            DiscoveryScope(value.strip())
            for value in raw_scopes.split(",")
            if value.strip()
        )
        if require_scopes and not scopes:
            raise ValueError("DEVICEMESH_PROBE_SCOPES must explicitly allow at least one CIDR")
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

        return cls(
            server_url=os.environ.get("DEVICEMESH_SERVER_URL", "http://localhost:8000").rstrip("/"),
            source=os.environ.get("DEVICEMESH_PROBE_SOURCE", "network-probe"),
            scopes=scopes,
            probe_id=os.environ.get("DEVICEMESH_PROBE_ID", socket.gethostname()),
            probe_token=os.environ.get("DEVICEMESH_PROBE_TOKEN"),
            tcp_ports=ports,
        )

    def require_probe_token(self) -> str:
        if not self.probe_token:
            raise ValueError("DEVICEMESH_PROBE_TOKEN is required for synthetic monitoring")
        return self.probe_token

    def require_allowed(self, requested: DiscoveryScope) -> None:
        network = requested.network()
        if not any(network.subnet_of(allowed.network()) for allowed in self.scopes):
            raise ValueError(f"requested scope {network} is outside DEVICEMESH_PROBE_SCOPES")
