# Telemetry retention and long-range history

DeviceMesh keeps raw telemetry and long-range aggregates as separate data products. A rollup is never returned as if it were an original sample.

## Default operating model

A practical self-hosted policy is:

- keep raw samples for 7 days;
- compact older samples into one hourly rollup per device and metric;
- retain hourly rollups for long-range charts and capacity/network analysis.

The retention period is operator-controlled. DeviceMesh does not silently delete raw telemetry in V1.

## Compact raw telemetry

Compaction is an authenticated operator action:

```http
POST /api/v1/operator/telemetry/compact?rawRetentionDays=7
```

The operation is transactional:

1. aggregate every eligible raw hour into average, minimum, maximum and sample count;
2. merge late-arriving samples into an existing hourly bucket using a weighted average;
3. flush the rollup changes;
4. delete the corresponding raw samples;
5. commit the transaction.

If any step fails, PostgreSQL rolls the transaction back. Re-running compaction without new eligible samples is idempotent.

Example response:

```json
{
  "cutoff": "2026-09-16T15:00:00Z",
  "rollupsTouched": 87,
  "rawSamplesDeleted": 2140,
  "rawRetentionDays": 7
}
```

## Query provenance

Raw history remains the default:

```http
GET /api/v1/telemetry/history?deviceId=...&name=network.latency.ms&start=...&end=...&resolution=raw
```

Raw history accepts a maximum 30-day window.

Long-range history is explicit:

```http
GET /api/v1/telemetry/history?deviceId=...&name=network.latency.ms&start=...&end=...&resolution=hourly&bucketSeconds=3600
```

Hourly history accepts a maximum 365-day window. Responses include:

```json
{
  "resolution": "hourly",
  "bucketSeconds": 3600,
  "points": [
    {
      "timestamp": "2026-09-01T10:00:00Z",
      "value": 14.3,
      "minimum": 9.8,
      "maximum": 31.2,
      "samples": 120,
      "source": "hourly_rollup"
    }
  ]
}
```

The web UI uses raw history for 1h/6h/24h/7d and hourly rollups for 30d/90d.

## Network-quality alert preset

Network-quality alerts remain opt-in. An operator can install the V1 preset with:

```http
POST /api/v1/operator/alert-rules/presets/network-quality
```

The preset creates, if missing:

- `network.latency.ms >= 150` for 60 seconds;
- `network.jitter.ms >= 30` for 60 seconds;
- `network.packet_loss.percent >= 5` for 60 seconds.

Calling the endpoint again reuses matching rules instead of creating another copy. These thresholds are operational defaults, not a claim about the root cause of degraded connectivity; the measured signals and the heuristic diagnostic remain separate.
