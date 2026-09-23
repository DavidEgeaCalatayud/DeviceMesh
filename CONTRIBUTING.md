# Contributing to DeviceMesh

DeviceMesh uses short-lived branches and pull requests into `main`.

## Branches

Use `feat/*`, `fix/*`, `refactor/*`, `test/*`, `docs/*`, `build/*` or `ci/*`.

## Commits

Prefer Conventional Commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `build:`, `ci:` and `chore:`.

## Definition of done

A change is complete when relevant tests pass, contracts remain compatible, documentation is updated, secrets are not committed and CI is green.

## Architecture

Business rules belong in domain/application layers. Framework code, persistence and transport details belong in infrastructure/adapters. Cross-language communication must use the versioned protocol fixtures under `protocol/`.
