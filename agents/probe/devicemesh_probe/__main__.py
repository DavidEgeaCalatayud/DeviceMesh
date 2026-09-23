import argparse

from devicemesh_probe.client import publish_observations
from devicemesh_probe.config import ProbeConfig
from devicemesh_probe.discovery import DiscoveryScope, scan_scope


def main() -> None:
    parser = argparse.ArgumentParser(description="DeviceMesh bounded LAN discovery probe")
    parser.add_argument("--scope", required=True, help="IPv4 CIDR inside DEVICEMESH_PROBE_SCOPES")
    parser.add_argument("--workers", type=int, default=64)
    parser.add_argument("--timeout", type=float, default=1.0)
    args = parser.parse_args()

    config = ProbeConfig.from_environment()
    scope = DiscoveryScope(args.scope)
    config.require_allowed(scope)
    observations = scan_scope(
        scope,
        max_workers=args.workers,
        timeout_seconds=args.timeout,
    )
    publish_observations(config.server_url, config.source, observations)
    print(f"discovered {len(observations)} reachable host(s) in {scope.network()}")


if __name__ == "__main__":
    main()
