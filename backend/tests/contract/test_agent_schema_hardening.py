from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.api.schemas.agent import HeartbeatRequest, TelemetryRequest


def heartbeat_payload() -> dict[str, object]:
    return {
        "type": "heartbeat",
        "protocolVersion": 1,
        "agentId": "agent-1",
        "timestamp": datetime.now(UTC).isoformat(),
        "device": {
            "hostname": "host-1",
            "operatingSystem": "linux",
            "operatingSystemVersion": "1",
            "architecture": "x86_64",
            "manufacturer": "DeviceMesh",
            "ipAddresses": ["192.0.2.10"],
            "macAddresses": ["02:00:00:00:00:01"],
        },
    }


def telemetry_payload() -> dict[str, object]:
    return {
        "type": "telemetry",
        "protocolVersion": 1,
        "agentId": "agent-1",
        "timestamp": datetime.now(UTC).isoformat(),
        "metrics": [{"name": "cpu.usage", "value": 12.5, "unit": "percent"}],
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("agentId", ""),
        ("agentId", "x" * 129),
        ("protocolVersion", 2),
        ("type", "telemetry"),
    ],
)
def test_heartbeat_rejects_mutated_top_level_contract(field: str, value: object) -> None:
    payload = heartbeat_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        HeartbeatRequest.model_validate(payload)


def test_heartbeat_rejects_unknown_fields_at_every_level() -> None:
    payload = heartbeat_payload()
    payload["unexpected"] = "ignored-by-lax-models"
    with pytest.raises(ValidationError):
        HeartbeatRequest.model_validate(payload)

    payload = heartbeat_payload()
    assert isinstance(payload["device"], dict)
    payload["device"]["unexpected"] = True
    with pytest.raises(ValidationError):
        HeartbeatRequest.model_validate(payload)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_telemetry_rejects_non_finite_numbers(value: float) -> None:
    payload = telemetry_payload()
    assert isinstance(payload["metrics"], list)
    payload["metrics"][0]["value"] = value
    with pytest.raises(ValidationError):
        TelemetryRequest.model_validate(payload)


def test_telemetry_rejects_unknown_metric_fields() -> None:
    payload = telemetry_payload()
    assert isinstance(payload["metrics"], list)
    payload["metrics"][0]["unexpected"] = "value"
    with pytest.raises(ValidationError):
        TelemetryRequest.model_validate(payload)


def test_telemetry_rejects_metric_cardinality_over_contract_limit() -> None:
    payload = telemetry_payload()
    payload["metrics"] = [
        {"name": f"metric.{index}", "value": float(index), "unit": None}
        for index in range(257)
    ]
    with pytest.raises(ValidationError):
        TelemetryRequest.model_validate(payload)


def test_valid_boundaries_remain_accepted() -> None:
    HeartbeatRequest.model_validate(heartbeat_payload())
    telemetry = telemetry_payload()
    telemetry["metrics"] = [
        {"name": f"metric.{index}", "value": float(index), "unit": None}
        for index in range(256)
    ]
    TelemetryRequest.model_validate(telemetry)
