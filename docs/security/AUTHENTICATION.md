# Authentication

## Human authentication and RBAC

DeviceMesh V1 has a complete local human-authentication path for self-hosted deployments:

- passwords are stored with Argon2id;
- roles are `viewer`, `operator`, and `administrator`;
- access and refresh credentials are random values whose SHA-256 digests are stored server-side;
- refresh is rotating: using a refresh credential revokes its previous session;
- logout, user disablement, MFA changes, and administrator recovery revoke affected sessions;
- login throttling is persisted in PostgreSQL and applies by username and source IP;
- human mutations and authentication lifecycle events are recorded in the audit log.

The web client keeps access/refresh credentials in `sessionStorage`, so closing the browser tab clears the local copy.

## Human multi-factor authentication

A persisted human account can enable MFA from **Account security** or with `POST /api/v1/auth/mfa`.

DeviceMesh V1 uses a high-entropy possession factor generated with the operating system CSPRNG. The plaintext factor is returned **once** when MFA is enabled or rotated. PostgreSQL stores only its SHA-256 digest, never the plaintext factor. The operator must place the factor in a password manager or another protected secret store.

Once enabled, successful login requires both:

1. the account password; and
2. the current possession factor in `mfaCode`.

The server intentionally returns the same authentication error whether the password or possession factor is wrong. Enabling or rotating MFA revokes existing sessions. A user can disable MFA only by presenting the current factor. If the factor is lost, an administrator can use the audited recovery endpoint `DELETE /api/v1/admin/users/{user_id}/mfa`; recovery also revokes the user's sessions.

This design avoids a reversible TOTP seed in the DeviceMesh database and uses the same one-time-secret handling model as agent and distributed-probe credentials.

## Federation boundary

OIDC and LDAP are **optional future federation adapters**, not part of the V1 local-auth acceptance contract. DeviceMesh does not claim an OIDC/LDAP integration until a real identity provider/directory is configured and exercised in acceptance tests. Local Argon2id + RBAC + rotating sessions + possession-factor MFA remains the supported V1 human-authentication path.

## Operator bootstrap

Self-hosted deployments retain `DEVICEMESH_OPERATOR_TOKEN` as a bootstrap/administrative escape hatch. The development default must be replaced before exposing DeviceMesh beyond localhost or a trusted development network.

Bootstrap requests use:

```text
Authorization: Bearer <operator-token>
```

This token is never valid for agent ingestion. Normal day-to-day human access should use persisted human accounts rather than sharing the bootstrap token.

## Windows Agent enrollment

Generate a one-time enrollment token through the operator API, then provide it to the Windows service through configuration/environment for its first successful launch, for example:

```text
DeviceMesh__EnrollmentToken=<one-time-token>
```

The agent exchanges it at `/api/v1/agents/enroll`. The returned long-lived agent credential is protected with Windows DPAPI using `CurrentUser` and persisted beneath the configured `CredentialFilePath`. The raw credential is not written to `appsettings.json` or application logs.

After successful enrollment, remove the enrollment token from the service environment/configuration. Reusing it is rejected server-side.

## Credential lifecycle

The operator API supports credential rotation and revocation. A rotated/revoked Windows Agent must be provisioned with a fresh enrollment/credential flow as appropriate; revoked secrets cannot ingest heartbeat or telemetry.
