import os
from dataclasses import dataclass

from devicemesh_probe.discovery import DiscoveryScope


@dataclass(frozen=True, slots=True)
class ProbeConfig:
    server_url: str
    source: str
    scopes: tuple[DiscoveryScope, ...]

    @classmethod
    def from_environment(cls) -> "ProbeConfig":
        raw_scopes = os.environ.get("DEVICEMESH_PROBE_SCOPES", "")
        scopes = tuple(
            DiscoveryScope(value.strip())
            for value in raw_scopes.split(",")
            if value.strip()
        )
        if not scopes:
            raise ValueError("DEVICEMESH_PROBE_SCOPES must explicitly allow at least one CIDR")
        for scope in scopes:
            scope.network()
        return cls(
            server_url=os.environ.get("DEVICEMESH_SERVER_URL", "http://localhost:8000"),
            source=os.environ.get("DEVICEMESH_PROBE_SOURCE", "network-probe"),
            scopes=scopes,
        )

    def require_allowed(self, requested: DiscoveryScope) -> None:
        network = requested.network()
        if not any(network.subnet_of(allowed.network()) for allowed in self.scopes):
            raise ValueError(f"requested scope {network} is outside DEVICEMESH_PROBE_SCOPES")
