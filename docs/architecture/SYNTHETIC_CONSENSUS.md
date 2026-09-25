# Synthetic Consensus V2

DeviceMesh classifies distributed synthetic results using coherent observation rounds and an explicit quorum. This replaces the V1 behaviour that combined the latest recent result from each probe even when those results belonged to different polling rounds.

## Round model

For each monitor, the newest accepted observation anchors the current round. Only observations inside the configured round window are eligible. The effective window is bounded to at most half of the monitor interval, which prevents the previous polling round from satisfying quorum when the next round has only partially arrived.

Configuration:

- `DEVICEMESH_SYNTHETIC_CONSENSUS_ROUND_WINDOW_SECONDS` — maximum round width, default `30`.
- `DEVICEMESH_SYNTHETIC_PROBE_OFFLINE_AFTER_SECONDS` — determines whether an assigned probe is still an active quorum member.

## Quorum

Only enabled, recently-seen probes with enabled assignments to the monitor count as expected voters. The default quorum is a strict majority:

`floor(active_probes * quorum_ratio) + 1`

with `quorum_ratio=0.5`. Therefore:

| Active probes | Required observations |
| ---: | ---: |
| 1 | 1 |
| 2 | 2 |
| 3 | 2 |
| 4 | 3 |
| 5 | 3 |

Configuration:

- `DEVICEMESH_SYNTHETIC_CONSENSUS_QUORUM_RATIO` — default `0.5`, range `[0.5, 1.0)`.
- `DEVICEMESH_SYNTHETIC_CONSENSUS_MINIMUM_QUORUM` — lower bound, default `1`.

When there are fewer observations than the required quorum, classification is `insufficient_data`. An incomplete round therefore cannot increment incident failure/recovery streaks.

## Classification

Once quorum is met:

- all observed probes healthy → `healthy`
- all observed probes failing → `global_outage`
- mixture of healthy and failing probes → `regional_degradation`

The existing incident state machine consumes these classifications. Because `insufficient_data` is ignored by incident evaluation, a two-probe monitor with a failure threshold of two now requires two complete unhealthy rounds instead of accidentally counting the first probe arrival and the completed round as two failures.

## Delayed results

Durable probe outboxes may deliver results after connectivity returns. Existing incident state ordering still rejects a delayed observation from regressing the current incident state. Round-aware selection additionally prevents stale observations from being blended into the newest round.

## Local fallback

When no active remote assignment exists, backend-local synthetic execution remains supported. In that case the observed local result forms the available quorum, preserving single-probe deployments while strengthening multi-probe deployments.
