from app.application.use_cases.record_heartbeat import RecordHeartbeat
from app.application.use_cases.record_observation import RecordObservation
from app.application.use_cases.record_telemetry import RecordTelemetry
from app.core.config import get_settings
from app.infrastructure.database import SessionFactory
from app.infrastructure.nms_secrets import NmsSecretResolver
from app.infrastructure.notification_delivery import (
    NotificationDispatcher,
    NotificationSecretResolver,
    NotificationTransport,
)
from app.infrastructure.offline import OfflineDeviceSweeper
from app.infrastructure.realtime.events import (
    EventPublisher,
    InProcessEventPublisher,
    PublishingEventRepository,
)
from app.infrastructure.realtime.redis_events import RedisEventPublisher
from app.infrastructure.repositories.alerting_telemetry import AlertingTelemetryRepository
from app.infrastructure.repositories.alerts import SqlAlchemyAlertRepository
from app.infrastructure.repositories.event_recording import EventRecordingDeviceRepository
from app.infrastructure.repositories.events import SqlAlchemyEventRepository
from app.infrastructure.repositories.health import (
    SqlAlchemyHealthRepository,
    SqlAlchemyMaintenanceRepository,
)
from app.infrastructure.repositories.network import SqlAlchemyNetworkRepository
from app.infrastructure.repositories.nms import SqlAlchemyNmsRepository
from app.infrastructure.repositories.notifications import SqlAlchemyNotificationRepository
from app.infrastructure.repositories.operations import SqlAlchemyRemoteOperationRepository
from app.infrastructure.repositories.retention import SqlAlchemyTelemetryRetentionRepository
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyDeviceRepository,
    SqlAlchemyTelemetryRepository,
)
from app.infrastructure.repositories.synthetic_consensus import RoundAwareSyntheticRepository
from app.infrastructure.repositories.synthetic_http import (
    SqlAlchemySyntheticHttpSettingsRepository,
)
from app.infrastructure.repositories.synthetics import SqlAlchemySyntheticRepository
from app.infrastructure.repositories.syslog import SqlAlchemySyslogRepository
from app.infrastructure.security.agent_auth import AgentAuthService
from app.infrastructure.snmp_poller import NetworkPollWorker
from app.infrastructure.synthetic_secrets import SyntheticSecretResolver
from app.infrastructure.synthetic_worker import SyntheticProbeWorker
from app.infrastructure.synthetics import SyntheticProbeExecutor

settings = get_settings()
realtime_event_publisher: EventPublisher = (
    RedisEventPublisher(settings.redis_url) if settings.event_backend == "redis"
    else InProcessEventPublisher()
)
raw_event_repository = SqlAlchemyEventRepository(SessionFactory)
event_repository = PublishingEventRepository(raw_event_repository, realtime_event_publisher)
health_repository = SqlAlchemyHealthRepository(SessionFactory)
maintenance_repository = SqlAlchemyMaintenanceRepository(SessionFactory)
remote_operation_repository = SqlAlchemyRemoteOperationRepository(SessionFactory)
notification_repository = SqlAlchemyNotificationRepository(SessionFactory)
notification_dispatcher = NotificationDispatcher(
    notification_repository,
    NotificationSecretResolver(settings),
    NotificationTransport(settings),
    settings,
)
synthetic_repository: SqlAlchemySyntheticRepository = RoundAwareSyntheticRepository(
    SessionFactory,
    quorum_ratio=settings.synthetic_consensus_quorum_ratio,
    minimum_quorum=settings.synthetic_consensus_minimum_quorum,
    round_window_seconds=settings.synthetic_consensus_round_window_seconds,
    probe_stale_seconds=settings.synthetic_probe_offline_after_seconds,
)
synthetic_http_settings_repository = SqlAlchemySyntheticHttpSettingsRepository(SessionFactory)
synthetic_probe_executor = SyntheticProbeExecutor(SyntheticSecretResolver(settings))
synthetic_probe_worker = SyntheticProbeWorker(
    synthetic_repository,
    synthetic_http_settings_repository,
    synthetic_probe_executor,
    probe_id=settings.synthetic_probe_id,
    batch_size=settings.synthetic_probe_batch_size,
)
raw_device_repository = SqlAlchemyDeviceRepository(SessionFactory)
device_repository = EventRecordingDeviceRepository(
    raw_device_repository,
    event_repository,
    health_repository,
)
network_repository = SqlAlchemyNetworkRepository(SessionFactory)
nms_repository = SqlAlchemyNmsRepository(SessionFactory)
nms_poll_worker = NetworkPollWorker(
    nms_repository,
    network_repository,
    NmsSecretResolver(settings),
)
raw_telemetry_repository = SqlAlchemyTelemetryRepository(SessionFactory)
telemetry_retention_repository = SqlAlchemyTelemetryRetentionRepository(SessionFactory)
syslog_repository = SqlAlchemySyslogRepository(SessionFactory)
alert_repository = SqlAlchemyAlertRepository(SessionFactory, maintenance_repository)
telemetry_repository = AlertingTelemetryRepository(
    raw_telemetry_repository,
    alert_repository,
    event_repository,
    notification_repository,
)
agent_auth_service = AgentAuthService(SessionFactory, settings)
offline_device_sweeper = OfflineDeviceSweeper(
    SessionFactory,
    event_repository,
    health_repository,
    settings.device_offline_after_seconds,
)
heartbeat_use_case = RecordHeartbeat(device_repository)
observation_use_case = RecordObservation(
    device_repository,
    network_repository,
    event_repository,
)
telemetry_use_case = RecordTelemetry(telemetry_repository)


def get_heartbeat_use_case() -> RecordHeartbeat:
    return heartbeat_use_case


def get_observation_use_case() -> RecordObservation:
    return observation_use_case


def get_telemetry_use_case() -> RecordTelemetry:
    return telemetry_use_case


def get_agent_auth_service() -> AgentAuthService:
    return agent_auth_service


def get_alert_repository() -> SqlAlchemyAlertRepository:
    return alert_repository


def get_notification_repository() -> SqlAlchemyNotificationRepository:
    return notification_repository


def get_network_repository() -> SqlAlchemyNetworkRepository:
    return network_repository


def get_nms_repository() -> SqlAlchemyNmsRepository:
    return nms_repository


def get_syslog_repository() -> SqlAlchemySyslogRepository:
    return syslog_repository


def get_telemetry_retention_repository() -> SqlAlchemyTelemetryRetentionRepository:
    return telemetry_retention_repository


def get_health_repository() -> SqlAlchemyHealthRepository:
    return health_repository


def get_maintenance_repository() -> SqlAlchemyMaintenanceRepository:
    return maintenance_repository


def get_remote_operation_repository() -> SqlAlchemyRemoteOperationRepository:
    return remote_operation_repository


def get_synthetic_repository() -> SqlAlchemySyntheticRepository:
    return synthetic_repository


def get_synthetic_http_settings_repository() -> SqlAlchemySyntheticHttpSettingsRepository:
    return synthetic_http_settings_repository
