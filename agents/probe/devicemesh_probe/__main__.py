import argparse
import asyncio

from devicemesh_probe.client import publish_observations
from devicemesh_probe.config import ProbeConfig
from devicemesh_probe.discovery import DiscoveryScope, scan_scope
from devicemesh_probe.synthetics import run_synthetic_loop


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
    args = parser.parse_args()

    config = ProbeConfig.from_environment()
    if args.synthetic:
        asyncio.run(run_synthetic_loop(config, once=args.once))
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
    publish_observations(config.server_url, config.source, observations)
    service_count = sum(len(observation.services) for observation in observations)
    print(
        f"discovered {len(observations)} reachable host(s) in {scope.network()} "
        f"with {service_count} allowed TCP service(s) open"
    )


if __name__ == "__main__":
    main()
