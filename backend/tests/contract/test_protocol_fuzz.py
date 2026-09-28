from __future__ import annotations

import math
import re
from datetime import UTC, datetime

from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.api.schemas.agent import HeartbeatRequest, TelemetryRequest
from app.core.logging import sanitize_request_id
from app.core.version import COMPONENT_COMPATIBILITY, evaluate_component_compatibility

FUZZ = settings(max_examples=400, derandomize=True, deadline=None)


def _heartbeat(agent_id: str = "agent-1") -> dict[str, object]:
    return {
        "type": "heartbeat",
        "protocolVersion": 1,
        "agentId": agent_id,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def _telemetry(metric_name: str, value: float = 1.0) -> dict[str, object]:
    return {
        "type": "telemetry",
        "protocolVersion": 1,
        "agentId": "agent-1",
        "timestamp": datetime.now(UTC).isoformat(),
        "metrics": [{"name": metric_name, "value": value, "unit": "percent"}],
    }


@FUZZ
@given(st.text(max_size=300))
def test_fuzz_agent_identifier_boundaries(agent_id: str) -> None:
    valid = 1 <= len(agent_id) <= 128
    try:
        HeartbeatRequest.model_validate(_heartbeat(agent_id))
    except ValidationError:
        assert not valid
    else:
        assert valid


@FUZZ
@given(
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            min_codepoint=32,
            max_codepoint=126,
        ),
        max_size=160,
    )
)
def test_fuzz_metric_name_contract(metric_name: str) -> None:
    valid = re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", metric_name) is not None
    try:
        TelemetryRequest.model_validate(_telemetry(metric_name))
    except ValidationError:
        assert not valid
    else:
        assert valid


@FUZZ
@given(st.floats(allow_nan=True, allow_infinity=True, width=64))
def test_fuzz_metric_numbers_never_accept_non_finite_values(value: float) -> None:
    try:
        TelemetryRequest.model_validate(_telemetry("cpu.usage", value))
    except ValidationError:
        assert not math.isfinite(value)
    else:
        assert math.isfinite(value)


json_scalar = st.none() | st.booleans() | st.integers() | st.floats(
    allow_nan=False,
    allow_infinity=False,
) | st.text(max_size=256)
json_values = st.recursive(
    json_scalar,
    lambda children: st.lists(children, max_size=12)
    | st.dictionaries(st.text(max_size=64), children, max_size=12),
    max_leaves=40,
)


@FUZZ
@given(json_values)
def test_fuzz_arbitrary_json_cannot_crash_protocol_models(payload: object) -> None:
    for model in (HeartbeatRequest, TelemetryRequest):
        try:
            model.model_validate(payload)
        except ValidationError:
            continue


@FUZZ
@given(st.text(max_size=256))
def test_fuzz_request_id_sanitizer_is_strict(value: str) -> None:
    sanitized = sanitize_request_id(value)
    if sanitized is None:
        return
    assert sanitized == value
    assert 1 <= len(sanitized) <= 64
    assert re.fullmatch(r"[A-Za-z0-9._-]+", sanitized) is not None


@FUZZ
@given(
    st.sampled_from(sorted(COMPONENT_COMPATIBILITY)),
    st.text(max_size=80),
    st.integers(min_value=-1000, max_value=1000),
)
def test_fuzz_component_compatibility_never_fails_open(
    component: str,
    package_version: str,
    protocol_version: int,
) -> None:
    compatible, reason = evaluate_component_compatibility(
        component,
        package_version,
        protocol_version,
    )
    assert reason in {
        "compatible",
        "invalid_version",
        "package_too_old",
        "unsupported_protocol",
    }
    if not compatible:
        return

    policy = COMPONENT_COMPATIBILITY[component]
    parsed = tuple(int(part) for part in package_version.split("."))
    minimum = tuple(int(part) for part in policy.minimum_version.split("."))
    assert len(parsed) == 3
    assert parsed >= minimum
    assert protocol_version in policy.protocol_versions


def test_unicode_numeric_semver_is_rejected_without_exception() -> None:
    compatible, reason = evaluate_component_compatibility(
        "windows-agent",
        "².².²",
        1,
    )
    assert compatible is False
    assert reason == "invalid_version"
