# ADR-0001: Use a monorepo

**Status:** Accepted

## Context
DeviceMesh spans server, web, mobile, agents, firmware and shared protocol contracts.

## Decision
Keep all first-party components in one repository with independent build boundaries.

## Alternatives
Separate repositories per component.

## Consequences
Cross-component contract changes are reviewable atomically. CI must remain path-aware to avoid unnecessary work.
