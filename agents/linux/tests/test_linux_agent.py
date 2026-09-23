from __future__ import annotations

import json
import stat
from pathlib import Path

import httpx

from devicemesh_linux_agent import (
    AGENT_HEALTH_CHECK,
    AgentConfig,
    CredentialStore,
    DeviceMeshLinuxAgent,
    heartbeat_payload,
    telemetry_payload,
)


def config(tmp_path: Path) -> AgentConfig:
    return AgentConfig(
        server="https://devicemesh.invalid",
        agent_id="linux-test",
        interval_seconds=30,
        enrollment_token=None,
        credential_file=tmp_path / "agent.credential",
        credential_override="test-credential",
    )


def test_payloads_use_shared_host_metric_and_identity_contract() -> None:
    heartbeat = heartbeat_payload("linux-test")
    telemetry = telemetry_payload("linux-test")

    assert heartbeat["type"] == "heartbeat"
    assert heartbeat["agentId"] == "linux-test"
    device = heartbeat["device"]
    assert isinstance(device, dict)
    assert device["hostname"]
    assert device["operatingSystem"]

    metrics = telemetry["metrics"]
    assert isinstance(metrics, list)
    names = {metric["name"] for metric in metrics if isinstance(metric, dict)}
    assert "host.cpu.utilization.percent" in names
    assert "host.memory.utilization.percent" in names
    assert "host.disk.utilization.percent" in names
    assert "host.uptime.seconds" in names


def test_credential_store_writes_owner_only_file(tmp_path: Path) -> None:
    path = tmp_path / "state" / "credential"
    store = CredentialStore(path)
    store.save("secret")

    assert store.load() == "secret"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_agent_authenticates_and_completes_allowlisted_health_check(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["Authorization"] == "Agent test-credential"
        assert request.headers["X-DeviceMesh-Agent-ID"] == "linux-test"
        assert request.headers["X-DeviceMesh-Nonce"]
        if request.url.path == "/api/v1/agents/operations/claim":
            return httpx.Response(
                200,
                json={
                    "id": "operation-1",
                    "operationType": AGENT_HEALTH_CHECK,
                    "arguments": {},
                    "expiresAt": "2026-09-23T18:00:00Z",
                },
            )
        if request.url.path.endswith("/complete"):
            body = json.loads(request.content)
            assert body["status"] == "succeeded"
            assert body["result"]["platform"] == "linux"
            return httpx.Response(200, json={})
        return httpx.Response(202, json={})

    client = httpx.Client(
        base_url="https://devicemesh.invalid",
        transport=httpx.MockTransport(handler),
    )
    agent = DeviceMeshLinuxAgent(config(tmp_path), client=client)
    agent.process_one_operation()

    assert [request.url.path for request in requests] == [
        "/api/v1/agents/operations/claim",
        "/api/v1/agents/operations/operation-1/complete",
    ]


def test_linux_executor_rejects_arguments_and_unknown_operation(tmp_path: Path) -> None:
    client = httpx.Client(
        base_url="https://devicemesh.invalid",
        transport=httpx.MockTransport(lambda _: httpx.Response(204)),
    )
    agent = DeviceMeshLinuxAgent(config(tmp_path), client=client)

    succeeded, _, error = agent.execute_operation(
        {"operationType": AGENT_HEALTH_CHECK, "arguments": {"command": "id"}}
    )
    assert not succeeded
    assert error is not None and "arguments" in error

    succeeded, _, error = agent.execute_operation(
        {"operationType": "shell.execute", "arguments": {}}
    )
    assert not succeeded
    assert error is not None and "unsupported" in error
