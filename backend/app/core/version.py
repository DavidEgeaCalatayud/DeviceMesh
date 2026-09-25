"""Wire compatibility is independent of the distributable package version."""
from importlib.metadata import version

SERVER_VERSION = version("devicemesh-backend")
PROTOCOL_VERSION = 1
SCHEMA_REVISION = "0014"
