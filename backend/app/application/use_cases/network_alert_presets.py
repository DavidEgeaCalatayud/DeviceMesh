from dataclasses import dataclass

from app.application.ports import AlertRepository
from app.domain.alerts.models import AlertRule, ThresholdRule

NETWORK_QUALITY_PRESETS: tuple[ThresholdRule, ...] = (
    ThresholdRule("network.latency.ms", ">=", 150.0, 60),
    ThresholdRule("network.jitter.ms", ">=", 30.0, 60),
    ThresholdRule("network.packet_loss.percent", ">=", 5.0, 60),
)


@dataclass(frozen=True, slots=True)
class AlertPresetResult:
    rules: tuple[AlertRule, ...]
    created: int


def ensure_network_quality_alert_rules(repository: AlertRepository) -> AlertPresetResult:
    existing_rules = repository.list_rules()
    by_condition = {
        (
            rule.condition.metric_name,
            rule.condition.operator,
            rule.condition.threshold,
            rule.condition.duration_seconds,
        ): rule
        for rule in existing_rules
    }

    resolved: list[AlertRule] = []
    created = 0
    for preset in NETWORK_QUALITY_PRESETS:
        key = (
            preset.metric_name,
            preset.operator,
            preset.threshold,
            preset.duration_seconds,
        )
        rule = by_condition.get(key)
        if rule is None:
            rule = repository.create_rule(preset)
            by_condition[key] = rule
            created += 1
        resolved.append(rule)

    return AlertPresetResult(tuple(resolved), created)
