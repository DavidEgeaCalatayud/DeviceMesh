"""Wire/API compatibility is independent of distributable package versions."""
from dataclasses import dataclass
from importlib.metadata import version

SERVER_VERSION = version("devicemesh-backend")
API_VERSION = 1
PROTOCOL_VERSION = 1
SUPPORTED_PROTOCOL_VERSIONS = (1,)
MIN_PROTOCOL_VERSION = min(SUPPORTED_PROTOCOL_VERSIONS)
MAX_PROTOCOL_VERSION = max(SUPPORTED_PROTOCOL_VERSIONS)
SCHEMA_REVISION = "0014"


@dataclass(frozen=True, slots=True)
class ComponentCompatibility:
    minimum_version: str
    protocol_versions: tuple[int, ...]


# Only components with a production-capable implementation belong here. Mobile and
# firmware scaffolds are intentionally excluded until they implement the contract.
COMPONENT_COMPATIBILITY: dict[str, ComponentCompatibility] = {
    "windows-agent": ComponentCompatibility("0.2.0", (1,)),
    "linux-agent": ComponentCompatibility("0.2.0", (1,)),
    "macos-agent": ComponentCompatibility("0.1.0", (1,)),
    "distributed-probe": ComponentCompatibility("0.2.0", (1,)),
}


def _numeric_semver(value: str) -> tuple[int, int, int] | None:
    parts = value.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        return None
    return int(parts[0]), int(parts[1]), int(parts[2])


def evaluate_component_compatibility(
    component: str,
    package_version: str,
    protocol_version: int,
) -> tuple[bool, str]:
    """Evaluate a released client against the server's explicit compatibility policy."""
    policy = COMPONENT_COMPATIBILITY.get(component)
    if policy is None:
        return False, "unknown_component"

    parsed = _numeric_semver(package_version)
    minimum = _numeric_semver(policy.minimum_version)
    if parsed is None or minimum is None:
        return False, "invalid_version"
    if parsed < minimum:
        return False, "package_too_old"
    if protocol_version not in policy.protocol_versions:
        return False, "unsupported_protocol"
    return True, "compatible"
