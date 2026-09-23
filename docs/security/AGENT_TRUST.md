# Agent trust model

DeviceMesh treats human/operator access and agent ingestion as separate trust domains.

## Enrollment

1. An authenticated operator creates a cryptographically random, short-lived, one-time enrollment token.
2. Only the SHA-256 digest of that token is stored server-side.
3. An agent exchanges the raw token once for a dedicated opaque agent credential.
4. Only the credential digest is persisted. The raw credential is returned once and must be protected by the agent host.

## Authenticated ingestion

Heartbeat and telemetry require all of:

- `Authorization: Agent <credential>`
- `X-DeviceMesh-Agent-ID`
- `X-DeviceMesh-Timestamp`
- `X-DeviceMesh-Nonce`

The timestamp must be inside the configured clock-skew window. A `(credential, nonce)` pair is accepted once; replay attempts are rejected before ingestion.

Operator bearer tokens are deliberately not accepted on agent ingestion endpoints.

## Rotation and revocation

Operators can rotate all active credentials for an agent or revoke a specific credential. Revoked credentials immediately fail authentication.

TLS remains mandatory whenever DeviceMesh traffic crosses an untrusted link. Header replay controls do not replace transport confidentiality.
