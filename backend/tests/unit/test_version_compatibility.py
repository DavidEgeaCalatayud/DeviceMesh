import pytest

from app.core.version import COMPONENT_COMPATIBILITY, evaluate_component_compatibility


@pytest.mark.parametrize("component", sorted(COMPONENT_COMPATIBILITY))
def test_minimum_component_versions_are_compatible(component: str) -> None:
    policy = COMPONENT_COMPATIBILITY[component]
    compatible, reason = evaluate_component_compatibility(
        component,
        policy.minimum_version,
        policy.protocol_versions[0],
    )
    assert compatible is True
    assert reason == "compatible"


def test_newer_numeric_patch_is_compatible() -> None:
    compatible, reason = evaluate_component_compatibility("linux-agent", "0.2.999", 1)
    assert compatible is True
    assert reason == "compatible"


def test_unknown_component_is_rejected() -> None:
    assert evaluate_component_compatibility("mobile-scaffold", "1.0.0", 1) == (
        False,
        "unknown_component",
    )
