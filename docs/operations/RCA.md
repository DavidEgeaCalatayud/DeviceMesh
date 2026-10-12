# Explainable Root Cause Analysis

DeviceMesh RCA is deterministic correlation, not a claim of automatic causal proof. The endpoint
`GET /api/v1/incidents/{incident_id}/rca` evaluates evidence already captured by the platform and
returns ranked candidates with the exact evidence that contributed to each score.

## Evidence model

The current `dependency-temporal-evidence-v1` model uses:

- explicit service dependency paths, with upstream dependencies receiving more causal weight than
  the already-impacted service;
- incidents on monitors linked to the candidate service, with failures that precede the target
  incident weighted above failures that follow it;
- device events close to incident opening, weighted by severity;
- correlated Syslog close to incident opening, weighted by normalized Syslog severity;
- the monitored device's offline-at-open signal.

The API returns a 0-100 deterministic score, low/medium/high confidence, causal path, first signal
time and individual evidence records. Missing evidence reduces confidence; it is never interpreted
as proof that a component was healthy.

## Operational interpretation

Treat the primary candidate as the best investigation starting point. Confirm it with the incident
timeline, service dependencies, physical topology, metrics and logs before recording a human
`rootCause`. DeviceMesh deliberately keeps the generated hypothesis separate from the human
postmortem fields so an automated guess cannot overwrite the incident record.
