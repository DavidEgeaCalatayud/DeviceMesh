from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.security import require_operator
from app.api.schemas.alerts import AlertResponse, AlertRuleCreateRequest, AlertRuleResponse
from app.domain.alerts.models import AlertIncident, AlertRule, ThresholdRule
from app.infrastructure.repositories.alerts import SqlAlchemyAlertRepository
from app.runtime import get_alert_repository

router = APIRouter(prefix="/api/v1", tags=["alerts"])
AlertRepositoryDependency = Annotated[SqlAlchemyAlertRepository, Depends(get_alert_repository)]
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


def _alert_response(incident: AlertIncident, rule: AlertRule) -> AlertResponse:
    condition = rule.condition
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


@router.get("/alerts", response_model=list[AlertResponse])
def list_alerts(
    repository: AlertRepositoryDependency,
    active_only: Annotated[bool, Query(alias="activeOnly")] = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AlertResponse]:
    rules = {rule.id: rule for rule in repository.list_rules()}
    incidents = repository.list_alerts(active_only=active_only, limit=limit)
    return [
        _alert_response(incident, rules[incident.rule_id])
        for incident in incidents
        if incident.rule_id in rules
    ]
