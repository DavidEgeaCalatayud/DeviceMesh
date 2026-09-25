# Version and compatibility policy

DeviceMesh versions distributable components independently. Package version compatibility and wire-protocol compatibility are therefore evaluated separately.

## Server contract

`GET /api/v1/system/version` returns the backend package version, API/protocol versions, database schema revision and the supported client matrix.

Current minimum package versions are:

| Component | Minimum package | Supported protocol |
|---|---:|---:|
| `windows-agent` | `0.2.0` | `1` |
| `linux-agent` | `0.2.0` | `1` |
| `macos-agent` | `0.1.0` | `1` |
| `distributed-probe` | `0.2.0` | `1` |

Mobile and ESP32 scaffolds are intentionally absent until they implement a production-capable server contract.

## Runtime compatibility check

Operators and client installers can evaluate a concrete release before rollout:

```text
GET /api/v1/system/compatibility/windows-agent?packageVersion=0.2.0&protocolVersion=1
```

A successful evaluation returns:

```json
{
  "component": "windows-agent",
  "packageVersion": "0.2.0",
  "protocolVersion": 1,
  "compatible": true,
  "reason": "compatible",
  "minimumVersion": "0.2.0",
  "supportedProtocolVersions": [1]
}
```

Compatibility reasons are stable machine-readable values:

- `compatible`: package and protocol are supported.
- `package_too_old`: package SemVer is below the server minimum.
- `unsupported_protocol`: the package version is new enough but its protocol is unsupported.
- `invalid_version`: package version is not numeric `major.minor.patch`.
- unknown component names return HTTP `404`.

A package version greater than the minimum is **not** by itself proof that every future feature is supported. The protocol version remains the wire-level compatibility boundary.

## Change rules

- Backward-compatible server work keeps the current protocol version.
- A wire-breaking change requires a new protocol version and a transition period where the server accepts both versions when feasible.
- Increasing a component minimum version is an explicit compatibility-policy change and must include tests and release notes.
- Database schema compatibility is independent. `/ready` refuses service when the running schema revision differs from the backend-required revision.
- Release pipelines use numeric Semantic Versioning for agent packages so runtime comparison is deterministic.

## CI validation

Backend integration tests iterate through all production-capable components and require each documented minimum version to be accepted on protocol v1. The same suite verifies rejection of an outdated package, an unsupported protocol, malformed SemVer and unknown component names. This prevents the published compatibility matrix and the executable policy from drifting apart.
