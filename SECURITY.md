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

See `docs/security/THREAT_MODEL.md` for the evolving threat model.
