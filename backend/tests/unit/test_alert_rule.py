import pytest

from app.domain.alerts.models import ThresholdRule


def test_threshold_rule_matches() -> None:
    assert ThresholdRule("cpu.usage", ">", 90).matches(95)
    assert not ThresholdRule("cpu.usage", ">", 90).matches(90)


def test_threshold_rule_rejects_unknown_operator() -> None:
    with pytest.raises(ValueError):
        ThresholdRule("cpu.usage", "==", 90).matches(90)
