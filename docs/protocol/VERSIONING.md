# Protocol Versioning

Protocol versions are integers independent from application SemVer. Breaking changes create a new protocol version. Servers may support multiple protocol versions during migrations. Agents must never silently reinterpret an unsupported version.
