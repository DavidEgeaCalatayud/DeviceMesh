# Distributed probe operations

The distributed probe is designed to remain safe and observable when connectivity to DeviceMesh Server is intermittent.

## Durable delivery

Completed synthetic results are written to the local SQLite outbox before upload. Server/network failures therefore retain completed results for a later flush. The existing exponential backoff with jitter prevents synchronized retry storms.

## Local liveness

Synthetic mode writes an atomic liveness document periodically while its asyncio event loop is running. This is deliberately independent from server reachability: a probe can be locally healthy while the server or route to it is unavailable.

Environment variables:

- `DEVICEMESH_PROBE_HEALTH_PATH` — liveness file path. The official container defaults to `/data/probe-health.json`; the systemd unit uses `/var/lib/devicemesh-probe/probe-health.json`.
- `DEVICEMESH_PROBE_HEALTH_STALE_SECONDS` — maximum accepted liveness age, default `45` seconds.

Run the same check used by the official container:

```bash
devicemesh-probe --health-check
```

Exit code `0` means the local event loop updated its state recently. Exit code `1` means the state is absent, invalid or stale.

The Docker image defines a native `HEALTHCHECK` using this command. Remote reachability is intentionally not part of Docker liveness because restarting a healthy probe cannot repair an upstream outage.

## Server-side health

The probe sends authenticated heartbeats to DeviceMesh. The server marks probes offline after `DEVICEMESH_SYNTHETIC_PROBE_OFFLINE_AFTER_SECONDS`, so operators can distinguish:

- local process failure — container/systemd liveness fails;
- probe-to-server path failure — local liveness stays healthy but server heartbeat becomes stale;
- monitored-target failure — probe/server remain healthy while synthetic checks fail.

## Credentials

Probe registration returns the plaintext bearer token once; DeviceMesh stores only its digest. Administrators can rotate credentials through the probe credential rotation endpoint. Store the probe token in a protected environment file or Docker secret-backed file and restart the process after credential replacement.

## Least privilege

The official image runs as UID `10001`. The systemd unit uses `DynamicUser`, `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict` and an empty capability bounding set. ICMP availability therefore depends on the host/container runtime permitting unprivileged `ping`; do not run the complete probe as root solely for ICMP.
