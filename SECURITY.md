# Security Policy

## Reporting

Do not open public issues for vulnerabilities that expose credentials, remote execution, authentication bypass or sensitive network information. Contact the repository owner privately through GitHub instead.

## Security principles

- User credentials and agent credentials are separate.
- Enrollment tokens are short-lived and single-purpose.
- Agent payloads are untrusted input and validated at the boundary.
- Secrets are supplied through runtime configuration and never committed.
- Network discovery is scoped to networks explicitly managed by the user.
- Dependency and container scanning are CI gates.
- Remote operations are pull-based and bound to the enrolled target agent.
- Remote operation types are an explicit allowlist; V1.1 accepts no operation arguments.
- DeviceMesh does not expose a generic shell, PowerShell, Bash, executable-path or arbitrary-command remote operation.
- Remote operation queue, claim, completion and expiry transitions are auditable.
- Maintenance windows silence notification/action semantics without deleting telemetry or incident history.

## Remote-operation boundary

The V1.1 remote-operation contract intentionally supports only:

- `telemetry.collect`
- `inventory.refresh`
- `agent.health_check`

Adding capabilities to this channel requires a new named operation with explicit server validation and an explicit agent implementation. Do not add a generic operation that accepts command text and passes it to a shell or process launcher.

Agents authenticate every claim/completion request with the existing agent credential, agent id, timestamp and nonce headers. The backend verifies that only the agent bound to an operation can claim or complete it.

See `docs/security/THREAT_MODEL.md` for the evolving threat model and `docs/operations/health-maintenance-remote-operations.md` for operational behavior.
