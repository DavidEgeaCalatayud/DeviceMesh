from datetime import UTC, datetime

import pytest

from devicemesh_probe.config import ProbeConfig
from devicemesh_probe.discovery import (
    DiscoveryScope,
    HostObservation,
    candidate_addresses,
    scan_scope,
)


def test_candidate_addresses_are_scoped() -> None:
    assert candidate_addresses(DiscoveryScope("192.0.2.0/30")) == ["192.0.2.1", "192.0.2.2"]


def test_large_scope_is_rejected() -> None:
    with pytest.raises(ValueError):
        DiscoveryScope("10.0.0.0/8").network()


def test_scan_uses_bounded_injected_probe_without_external_network() -> None:
    def fake_probe(address: str, _: float) -> HostObservation | None:
        if address.endswith("1"):
            return HostObservation(address, datetime.now(UTC), 1.5, hostname="fixture")
        return None

    observations = scan_scope(
        DiscoveryScope("192.0.2.0/30"),
        max_workers=2,
        probe=fake_probe,
    )
    assert [item.ip_address for item in observations] == ["192.0.2.1"]


def test_probe_config_rejects_scope_outside_allowlist() -> None:
    config = ProbeConfig(
        server_url="http://localhost:8000",
        source="test",
        scopes=(DiscoveryScope("192.168.1.0/24"),),
    )
    with pytest.raises(ValueError):
        config.require_allowed(DiscoveryScope("192.168.2.0/24"))
