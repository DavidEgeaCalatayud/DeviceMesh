from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.security import require_operator
from app.api.schemas.alerts import (
    AlertPresetResponse,
    AlertResponse,
    AlertRuleCreateRequest,
    AlertRuleResponse,
)
from app.application.use_cases.network_alert_presets import ensure_network_quality_alert_rules
from app.domain.alerts.models import AlertIncident, AlertRule, ThresholdRule
from app.infrastructure.repositories.alerts import SqlAlchemyAlertRepository
from app.infrastructure.repositories.health import SqlAlchemyMaintenanceRepository
from app.runtime import get_alert_repository, get_maintenance_repository

router = APIRouter(prefix="/api/v1", tags=["alerts"])
AlertRepositoryDependency = Annotated[SqlAlchemyAlertRepository, Depends(get_alert_repository)]
MaintenanceRepositoryDependency = Annotated[
    SqlAlchemyMaintenanceRepository,
    Depends(get_maintenance_repository),
]
Operator = Annotated[None, Depends(require_operator)]


def _rule_response(rule: AlertRule) -> AlertRuleResponse:
    condition = rule.condition
    return AlertRuleResponse(
        id=rule.id,
        metricName=condition.metric_name,
        operator=condition.operator,
        threshold=condition.threshold,
        durationSeconds=condition.duration_seconds,
        enabled=rule.enabled,
    )


def _alert_response(
    incident: AlertIncident,
    rule: AlertRule,
    maintenance_window_id: int | None,
) -> AlertResponse:
    condition = rule.condition
    effective_maintenance_id = incident.maintenance_window_id or maintenance_window_id
    return AlertResponse(
        id=incident.id,
        ruleId=incident.rule_id,
        deviceId=incident.device_id,
        openedAt=incident.opened_at,
        closedAt=incident.closed_at,
        active=incident.closed_at is None,
        metricName=condition.metric_name,
        operator=condition.operator,
        threshold=condition.threshold,
        durationSeconds=condition.duration_seconds,
        silenced=effective_maintenance_id is not None,
        maintenanceWindowId=effective_maintenance_id,
    )


@router.get("/alert-rules", response_model=list[AlertRuleResponse])
def list_alert_rules(repository: AlertRepositoryDependency) -> list[AlertRuleResponse]:
    return [_rule_response(rule) for rule in repository.list_rules()]


@router.post(
    "/operator/alert-rules",
    response_model=AlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_alert_rule(
    request: AlertRuleCreateRequest,
    _: Operator,
    repository: AlertRepositoryDependency,
) -> AlertRuleResponse:
    rule = repository.create_rule(
        ThresholdRule(
            request.metricName,
            request.operator,
            request.threshold,
            request.durationSeconds,
        )
    )
    return _rule_response(rule)


@router.post(
    "/operator/alert-rules/presets/network-quality",
    response_model=AlertPresetResponse,
)
def install_network_quality_alert_preset(
    _: Operator,
    repository: AlertRepositoryDependency,
) -> AlertPresetResponse:
    result = ensure_network_quality_alert_rules(repository)
    return AlertPresetResponse(
        preset="network-quality-v1",
        created=result.created,
        rules=[_rule_response(rule) for rule in result.rules],
    )


@router.get("/alerts", response_model=list[AlertResponse])
def list_alerts(
    repository: AlertRepositoryDependency,
    maintenance: MaintenanceRepositoryDependency,
    active_only: Annotated[bool, Query(alias="activeOnly")] = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AlertResponse]:
    rules = {rule.id: rule for rule in repository.list_rules()}
    incidents = repository.list_alerts(active_only=active_only, limit=limit)
    now = datetime.now(UTC)
    responses: list[AlertResponse] = []
    for incident in incidents:
        rule = rules.get(incident.rule_id)
        if rule is None:
            continue
        current_window = None
        if incident.closed_at is None and incident.maintenance_window_id is None:
            current_window = maintenance.active_window(incident.device_id, now)
        responses.append(
            _alert_response(
                incident,
                rule,
                current_window.id if current_window is not None else None,
            )
        )
    return responses
