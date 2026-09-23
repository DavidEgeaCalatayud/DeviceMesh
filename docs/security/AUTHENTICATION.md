# Authentication

## Operator bootstrap

V1 self-hosted deployments use `DEVICEMESH_OPERATOR_TOKEN` for privileged operator endpoints. The development default must be replaced before exposing DeviceMesh beyond localhost or a trusted development network.

Operator requests use:

```text
Authorization: Bearer <operator-token>
```

This token is never valid for agent ingestion.

## Windows Agent enrollment

Generate a one-time enrollment token through the operator API, then provide it to the Windows service through configuration/environment for its first successful launch, for example:

```text
DeviceMesh__EnrollmentToken=<one-time-token>
```

The agent exchanges it at `/api/v1/agents/enroll`. The returned long-lived agent credential is protected with Windows DPAPI using `CurrentUser` and persisted beneath the configured `CredentialFilePath`. The raw credential is not written to `appsettings.json` or application logs.

After successful enrollment, remove the enrollment token from the service environment/configuration. Reusing it is rejected server-side.

## Credential lifecycle

The operator API supports credential rotation and revocation. A rotated/revoked Windows Agent must be provisioned with a fresh enrollment/credential flow as appropriate; revoked secrets cannot ingest heartbeat or telemetry.
