# Compatibility

DeviceMesh treats application/package versions, API versions, database schema revisions and the agent wire protocol as separate compatibility dimensions.

## Current compatibility matrix

| Component | Status | API | Agent protocol |
| --- | --- | ---: | ---: |
| Server / Web | Supported | v1 | v1 ingestion |
| Windows Agent | Supported | v1 endpoints | v1 |
| Linux Agent | Supported | v1 endpoints | v1 |
| macOS Agent | Supported | v1 endpoints | v1 |
| Distributed Probe | Supported | v1 probe endpoints | v1 |
| Android | Scaffold / not in V1 compatibility contract | — | — |
| iOS | Scaffold / not in V1 compatibility contract | — | — |
| ESP32 firmware | Scaffold / not in V1 compatibility contract | — | — |

`GET /api/v1/system/version` is the machine-readable source of truth. It publishes the server package version, API version, current and supported protocol versions, minimum/maximum protocol version, database schema revision and the supported protocol set for every production-capable component.

## Rules

1. Protocol v1 payloads are rejected if their `protocolVersion` is not supported by the receiving schema.
2. Breaking wire changes require a new integer protocol version; package SemVer alone never changes wire semantics.
3. A server may support more than one protocol version during a migration. `supportedProtocolVersions`, `minProtocolVersion` and `maxProtocolVersion` describe that window.
4. A component must not be added to `componentCompatibility` until its implementation and contract tests support the advertised protocol.
5. Database readiness is independent of protocol compatibility. `/ready` returns failure when the runtime schema does not match `schemaRevision`.
6. Removing an advertised protocol version is a compatibility event and must be called out in release notes before deployment.

Python server schemas and contract fixtures are the reference for protocol v1. C#, Swift and probe implementations must remain fixture-compatible; future Kotlin/C clients enter the matrix only after equivalent contract coverage exists.
