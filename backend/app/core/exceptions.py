class DeviceMeshError(Exception):
    """Base exception for expected DeviceMesh domain/application failures."""


class UnknownAgentError(DeviceMeshError):
    pass
