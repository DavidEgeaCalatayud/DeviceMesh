# Contributing to DeviceMesh

DeviceMesh treats backend, agents, mobile clients, firmware, deployment and acceptance tooling as
one product. Changes should preserve the trust boundaries and cross-language contracts documented
under `docs/` and `protocol/`.

## Branches and pull requests

Use short-lived branches prefixed with `feat/`, `fix/`, `docs/`, `test/`, `security/` or
`chore/`. Pull requests must explain the product impact, security boundary and acceptance
evidence. Merged short-lived branches are removed automatically by the repository-hygiene
workflow.

Do not merge around a failing required workflow. A failure caused by an unavailable external
runner or provider must be identified as such; it must not be converted into a passing assertion
by weakening the product check.

## Required engineering rules

- Never commit passwords, API keys, enrollment tokens, signing keys, SNMP secrets or push tokens.
  Persist opaque secret references or encrypted values according to the existing subsystem.
- Remote operations remain allowlisted and structured. Do not add arbitrary shell execution.
- Network discovery and polling must stay bounded to operator-configured targets/scopes.
- Schema changes require an Alembic migration and schema-revision update.
- Public API changes require tests and regeneration of `docs/api/ENDPOINT_CATALOG.md`.
- Agent/probe protocol changes require fixtures/compatibility updates for every maintained client.
- Retention changes must state whether data is deleted, compacted or retained indefinitely.
- Mobile/hardware production claims require real signed-device/provider/HIL evidence; compilation
  alone is not acceptance.

## Local validation

Backend:

    cd backend
    pip install -e ".[dev]"
    ruff check app tests
    mypy app
    pytest

Web:

    cd web
    npm ci
    npm test
    npm run build

Use the component-specific CI workflows for Windows, Linux, macOS, Android, iOS, probes and
ESP32. Long soak and ESP32 HIL workflows are intentionally separate from ordinary PR validation.
