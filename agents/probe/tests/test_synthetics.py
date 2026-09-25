import asyncio

import pytest

from devicemesh_probe.config import ProbeConfig
from devicemesh_probe.synthetics import _address_allowed, _execute_icmp, _parse_work


def test_synthetic_mode_does_not_require_discovery_scopes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEVICEMESH_PROBE_SCOPES", raising=False)
    monkeypatch.setenv("DEVICEMESH_PROBE_TOKEN", "probe-secret")

    config = ProbeConfig.from_environment()

    assert config.scopes == ()
    assert config.require_synthetic_token() == "probe-secret"


def test_discovery_scope_remains_explicitly_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEVICEMESH_PROBE_SCOPES", raising=False)
    config = ProbeConfig.from_environment()

    with pytest.raises(ValueError, match="must explicitly allow"):
        from devicemesh_probe.discovery import DiscoveryScope

        config.require_allowed(DiscoveryScope("192.0.2.0/30"))


def test_parse_distributed_work_contract() -> None:
    work = _parse_work(
        [
            {
                "workId": "11111111-1111-1111-1111-111111111111",
                "assignedAt": "2026-09-24T08:00:00Z",
                "leaseExpiresAt": "2026-09-24T08:01:00Z",
                "monitor": {
                    "id": "22222222-2222-2222-2222-222222222222",
                    "name": "Public API",
                    "kind": "http",
                    "target": "https://example.com/health",
                    "port": None,
                    "timeoutSeconds": 5,
                    "httpMethod": "GET",
                    "expectedStatus": 200,
                },
            },
            {
                "workId": "33333333-3333-3333-3333-333333333333",
                "assignedAt": "2026-09-24T08:00:00Z",
                "leaseExpiresAt": "2026-09-24T08:01:00Z",
                "monitor": {
                    "id": "44444444-4444-4444-4444-444444444444",
                    "name": "Public TLS",
                    "kind": "tls",
                    "target": "example.com",
                    "port": 443,
                    "timeoutSeconds": 5,
                    "httpMethod": None,
                    "expectedStatus": None,
                },
            },
        ]
    )

    assert len(work) == 2
    assert work[0].monitor.kind == "http"
    assert work[0].monitor.expected_status == 200
    assert work[1].monitor.kind == "tls"
    assert work[1].monitor.port == 443


def test_synthetic_network_boundary_blocks_local_addresses() -> None:
    assert _address_allowed("8.8.8.8") is True
    assert _address_allowed("127.0.0.1") is False
    assert _address_allowed("169.254.1.1") is False
    assert _address_allowed("224.0.0.1") is False


def test_icmp_reports_missing_runtime_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("devicemesh_probe.synthetics.shutil.which", lambda _: None)

    success, error = asyncio.run(_execute_icmp("example.com", 1.0))

    assert success is False
    assert error == "ping executable is not installed in the probe runtime"
