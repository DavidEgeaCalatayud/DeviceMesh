from app.application.use_cases.record_heartbeat import RecordHeartbeat
from app.application.use_cases.record_observation import RecordObservation
from app.application.use_cases.record_telemetry import RecordTelemetry
from app.core.config import get_settings
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.event_recording import EventRecordingDeviceRepository
from app.infrastructure.repositories.events import SqlAlchemyEventRepository
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyDeviceRepository,
    SqlAlchemyTelemetryRepository,
)
from app.infrastructure.security.agent_auth import AgentAuthService

raw_device_repository = SqlAlchemyDeviceRepository(SessionFactory)
event_repository = SqlAlchemyEventRepository(SessionFactory)
device_repository = EventRecordingDeviceRepository(raw_device_repository, event_repository)
telemetry_repository = SqlAlchemyTelemetryRepository(SessionFactory)
agent_auth_service = AgentAuthService(SessionFactory, get_settings())
heartbeat_use_case = RecordHeartbeat(device_repository)
observation_use_case = RecordObservation(device_repository)
telemetry_use_case = RecordTelemetry(telemetry_repository)


def get_heartbeat_use_case() -> RecordHeartbeat:
    return heartbeat_use_case


def get_observation_use_case() -> RecordObservation:
    return observation_use_case


def get_telemetry_use_case() -> RecordTelemetry:
    return telemetry_use_case


def get_agent_auth_service() -> AgentAuthService:
    return agent_auth_service
