import pytest

from devicemesh_probe.discovery import DiscoveryScope, candidate_addresses


def test_candidate_addresses_are_scoped() -> None:
    assert candidate_addresses(DiscoveryScope("192.0.2.0/30")) == ["192.0.2.1", "192.0.2.2"]


def test_large_scope_is_rejected() -> None:
    with pytest.raises(ValueError):
        DiscoveryScope("10.0.0.0/8").network()
