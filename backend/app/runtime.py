from app.application.use_cases.record_heartbeat import RecordHeartbeat
from app.application.use_cases.record_observation import RecordObservation
from app.application.use_cases.record_telemetry import RecordTelemetry
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyDeviceRepository,
    SqlAlchemyTelemetryRepository,
)

device_repository = SqlAlchemyDeviceRepository(SessionFactory)
telemetry_repository = SqlAlchemyTelemetryRepository(SessionFactory)
heartbeat_use_case = RecordHeartbeat(device_repository)
observation_use_case = RecordObservation(device_repository)
telemetry_use_case = RecordTelemetry(telemetry_repository)


def get_heartbeat_use_case() -> RecordHeartbeat:
    return heartbeat_use_case


def get_observation_use_case() -> RecordObservation:
    return observation_use_case


def get_telemetry_use_case() -> RecordTelemetry:
    return telemetry_use_case
