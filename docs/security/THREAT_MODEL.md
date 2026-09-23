# Threat model

## Assets

- operator authentication material
- agent enrollment tokens and credentials
- device inventory and telemetry
- command and audit history

## Trust boundaries

- browser/mobile client ↔ API
- agent/probe ↔ ingestion API
- API ↔ PostgreSQL/Redis
- DeviceMesh host ↔ local network

## Agent credential controls

- Human/operator and agent credentials are distinct authentication domains.
- Enrollment tokens are high-entropy, short-lived and one-time.
- Enrollment tokens and agent credentials are stored as SHA-256 digests, never plaintext.
- Heartbeat and telemetry require a dedicated active agent credential.
- Timestamp skew limits stale requests and a persisted per-credential nonce prevents exact replay.
- Credential rotation revokes previous active credentials; explicit revocation stops ingestion immediately.
- Security-sensitive lifecycle actions are written to a dedicated audit table without raw secrets.

## Residual risks

- A compromised agent host can use its credential until the operator revokes or rotates it.
- Compromise of the DeviceMesh database exposes credential digests and telemetry, but not the original high-entropy secrets.
- LAN discovery observes network metadata and must stay scoped to operator-configured CIDRs.
- TLS termination and secret provisioning remain deployment responsibilities for non-local traffic.
