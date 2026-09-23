from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.alerts.models import (
    AlertIncident,
    AlertRule,
    AlertTransition,
    AlertTransitionType,
    ThresholdRule,
)
from app.domain.telemetry.models import Metric, TelemetryBatch
from app.infrastructure.database import (
    AgentRow,
    AlertConditionStateRow,
    AlertRow,
    AlertRuleRow,
)


class SqlAlchemyAlertRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_rule(self, rule: ThresholdRule) -> AlertRule:
        self._validate_rule(rule)
        with self._session_factory() as session:
            row = AlertRuleRow(
                metric_name=rule.metric_name,
                operator=rule.operator,
                threshold=rule.threshold,
                duration_seconds=rule.duration_seconds,
                enabled=True,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._rule_to_domain(row)

    def list_rules(self) -> list[AlertRule]:
        with self._session_factory() as session:
            rows = session.scalars(select(AlertRuleRow).order_by(AlertRuleRow.id)).all()
            return [self._rule_to_domain(row) for row in rows]

    def list_alerts(
        self,
        *,
        active_only: bool = False,
        limit: int = 100,
    ) -> list[AlertIncident]:
        statement = select(AlertRow).order_by(AlertRow.opened_at.desc(), AlertRow.id.desc())
        if active_only:
            statement = statement.where(AlertRow.closed_at.is_(None))
        with self._session_factory() as session:
            rows = session.scalars(statement.limit(limit)).all()
            return [self._incident_to_domain(row) for row in rows]

    def evaluate(self, batch: TelemetryBatch) -> list[AlertTransition]:
        metrics = {metric.name: metric for metric in batch.metrics}
        if not metrics:
            return []

        transitions: list[AlertTransition] = []
        with self._session_factory() as session:
            agent = session.get(AgentRow, batch.agent_id)
            device_id = agent.device_id if agent is not None else batch.agent_id
            rows = session.scalars(
                select(AlertRuleRow).where(
                    AlertRuleRow.enabled.is_(True),
                    AlertRuleRow.metric_name.in_(tuple(metrics)),
                )
            ).all()
            for row in rows:
                transition = self._evaluate_rule(
                    session,
                    row,
                    device_id,
                    metrics[row.metric_name],
                    batch.timestamp,
                )
                if transition is not None:
                    transitions.append(transition)
            session.commit()
        return transitions

    def _evaluate_rule(
        self,
        session: Session,
        rule_row: AlertRuleRow,
        device_id: str,
        metric: Metric,
        timestamp: datetime,
    ) -> AlertTransition | None:
        rule = self._rule_to_domain(rule_row)
        active = session.scalar(
            select(AlertRow)
            .where(
                AlertRow.rule_id == rule.id,
                AlertRow.device_id == device_id,
                AlertRow.closed_at.is_(None),
            )
            .limit(1)
        )
        state = session.get(AlertConditionStateRow, (rule.id, device_id))

        if active is not None:
            if timestamp <= active.opened_at:
                return None
            if rule.condition.matches(metric.value):
                return None
            active.closed_at = timestamp
            if state is not None:
                session.delete(state)
            session.flush()
            return AlertTransition(
                AlertTransitionType.RECOVERED,
                self._incident_to_domain(active),
                rule,
                metric.value,
                timestamp,
            )

        if state is not None and timestamp <= state.last_sample_at:
            return None

        if not rule.condition.matches(metric.value):
            if state is not None:
                session.delete(state)
            return None

        if rule.condition.duration_seconds == 0:
            return self._open_incident(session, rule, device_id, metric.value, timestamp)

        if state is None:
            state = AlertConditionStateRow(
                rule_id=rule.id,
                device_id=device_id,
                first_triggered_at=timestamp,
                last_sample_at=timestamp,
                last_value=metric.value,
            )
            session.add(state)
            return None

        state.last_sample_at = timestamp
        state.last_value = metric.value
        required = timedelta(seconds=rule.condition.duration_seconds)
        if timestamp - state.first_triggered_at < required:
            return None

        session.delete(state)
        return self._open_incident(session, rule, device_id, metric.value, timestamp)

    def _open_incident(
        self,
        session: Session,
        rule: AlertRule,
        device_id: str,
        value: float,
        timestamp: datetime,
    ) -> AlertTransition:
        incident_row = AlertRow(
            rule_id=rule.id,
            device_id=device_id,
            opened_at=timestamp,
        )
        session.add(incident_row)
        session.flush()
        return AlertTransition(
            AlertTransitionType.OPENED,
            self._incident_to_domain(incident_row),
            rule,
            value,
            timestamp,
        )

    @staticmethod
    def _validate_rule(rule: ThresholdRule) -> None:
        if not rule.metric_name.strip():
            raise ValueError("metric name is required")
        if rule.operator not in {">", ">=", "<", "<="}:
            raise ValueError(f"unsupported operator: {rule.operator}")
        if rule.duration_seconds < 0:
            raise ValueError("duration must not be negative")

    @staticmethod
    def _rule_to_domain(row: AlertRuleRow) -> AlertRule:
        return AlertRule(
            id=row.id,
            condition=ThresholdRule(
                metric_name=row.metric_name,
                operator=row.operator,
                threshold=row.threshold,
                duration_seconds=row.duration_seconds,
            ),
            enabled=row.enabled,
        )

    @staticmethod
    def _incident_to_domain(row: AlertRow) -> AlertIncident:
        return AlertIncident(
            id=row.id,
            rule_id=row.rule_id,
            device_id=row.device_id,
            opened_at=row.opened_at,
            closed_at=row.closed_at,
        )
