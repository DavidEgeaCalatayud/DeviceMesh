"""Wire/API compatibility is independent of distributable package versions."""
from importlib.metadata import version

SERVER_VERSION = version("devicemesh-backend")
API_VERSION = 1
PROTOCOL_VERSION = 1
SUPPORTED_PROTOCOL_VERSIONS = (1,)
MIN_PROTOCOL_VERSION = min(SUPPORTED_PROTOCOL_VERSIONS)
MAX_PROTOCOL_VERSION = max(SUPPORTED_PROTOCOL_VERSIONS)
SCHEMA_REVISION = "0014"

# Only components with a production-capable implementation belong here. Mobile and
# firmware scaffolds are intentionally excluded until they implement the contract.
COMPONENT_PROTOCOL_COMPATIBILITY: dict[str, tuple[int, ...]] = {
    "windows-agent": (1,),
    "linux-agent": (1,),
    "macos-agent": (1,),
    "distributed-probe": (1,),
}
