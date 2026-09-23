# Threat Model

## Protected assets
User accounts, agent credentials, enrollment tokens, device inventory, telemetry and network topology.

## Primary threats
- fake or cloned agents
- replayed telemetry
- stolen enrollment token
- compromised managed device
- malicious payloads
- abuse of discovery capability
- privilege escalation
- accidental secret disclosure

## V1 controls
TLS at deployment edge, separate agent credentials, short-lived enrollment tokens, input validation, scoped discovery, rate limits, audit events and dependency scanning.
