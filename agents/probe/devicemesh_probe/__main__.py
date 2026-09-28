import argparse
import asyncio
import os
import time
from contextlib import suppress
from pathlib import Path

from devicemesh_probe.client import publish_observations
from devicemesh_probe.config import ProbeConfig
from devicemesh_probe.discovery import DiscoveryScope, scan_scope
from devicemesh_probe.health import ProbeHealthState, maintain_liveness
from devicemesh_probe.runtime import maintain_runtime_telemetry, publish_runtime_telemetry
from devicemesh_probe.synthetics import run_synthetic_loop


def _health_state() -> ProbeHealthState:
    return ProbeHealthState(
        Path(os.environ.get("DEVICEMESH_PROBE_HEALTH_PATH", "/data/probe-health.json"))
    )


async def _run_synthetic_with_liveness(config: ProbeConfig, *, once: bool) -> None:
    health = _health_state()
    health.write()
    started_at = time.monotonic()
    if once:
        await run_synthetic_loop(config, once=True)
        await publish_runtime_telemetry(config, started_at=started_at)
        health.write()
        return

    liveness = asyncio.create_task(maintain_liveness(health))
    runtime = asyncio.create_task(maintain_runtime_telemetry(config, started_at=started_at))
    try:
        await run_synthetic_loop(config, once=False)
    finally:
        for task in (runtime, liveness):
            task.cancel()
        for task in (runtime, liveness):
            with suppress(asyncio.CancelledError):
                await task


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DeviceMesh bounded LAN discovery and distributed synthetic probe"
    )
    parser.add_argument("--scope", help="IPv4 CIDR inside DEVICEMESH_PROBE_SCOPES")
    parser.add_argument("--workers", type=int, default=64)
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument("--service-timeout", type=float, default=0.35)
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="run the distributed synthetic work loop instead of LAN discovery",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="with --synthetic, heartbeat/claim/execute once and exit",
    )
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="exit 0 when the local probe event loop has updated its liveness state recently",
    )
    args = parser.parse_args()

    if args.health_check:
        stale_after = float(os.environ.get("DEVICEMESH_PROBE_HEALTH_STALE_SECONDS", "45"))
        raise SystemExit(0 if _health_state().healthy(stale_after) else 1)

    config = ProbeConfig.from_environment()
    if args.synthetic:
        asyncio.run(_run_synthetic_with_liveness(config, once=args.once))
        return

    if not args.scope:
        parser.error("--scope is required unless --synthetic is selected")
    scope = DiscoveryScope(args.scope)
    config.require_allowed(scope)
    observations = scan_scope(
        scope,
        max_workers=args.workers,
        timeout_seconds=args.timeout,
        service_timeout_seconds=args.service_timeout,
        tcp_ports=config.tcp_ports,
    )
    publish_observations(config.server_url, config.source, observations, token=config.synthetic_token)
    service_count = sum(len(observation.services) for observation in observations)
    print(
        f"discovered {len(observations)} reachable host(s) in {scope.network()} "
        f"with {service_count} allowed TCP service(s) open"
    )


if __name__ == "__main__":
    main()
