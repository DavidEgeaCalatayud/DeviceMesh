from app.application.use_cases.network_alert_presets import ensure_network_quality_alert_rules
from app.domain.alerts.models import AlertRule, ThresholdRule


class FakeAlertRepository:
    def __init__(self) -> None:
        self.rules: list[AlertRule] = []

    def list_rules(self) -> list[AlertRule]:
        return list(self.rules)

    def create_rule(self, rule: ThresholdRule) -> AlertRule:
        created = AlertRule(len(self.rules) + 1, rule)
        self.rules.append(created)
        return created


def test_network_quality_preset_is_duplicate_safe() -> None:
    repository = FakeAlertRepository()

    first = ensure_network_quality_alert_rules(repository)  # type: ignore[arg-type]
    second = ensure_network_quality_alert_rules(repository)  # type: ignore[arg-type]

    assert first.created == 3
    assert second.created == 0
    assert len(repository.rules) == 3
    assert [rule.condition.metric_name for rule in first.rules] == [
        "network.latency.ms",
        "network.jitter.ms",
        "network.packet_loss.percent",
    ]
    assert [rule.condition.threshold for rule in first.rules] == [150.0, 30.0, 5.0]
    assert all(rule.condition.duration_seconds == 60 for rule in first.rules)
