from app.application.use_cases.record_heartbeat import RecordHeartbeat
from app.application.use_cases.record_telemetry import RecordTelemetry
from app.infrastructure.repositories.in_memory import (
    InMemoryDeviceRepository,
    InMemoryTelemetryRepository,
)

# Bootstrap adapters. PostgreSQL implementations replace these as the persistence slice lands.
device_repository = InMemoryDeviceRepository()
telemetry_repository = InMemoryTelemetryRepository()
heartbeat_use_case = RecordHeartbeat(device_repository)
telemetry_use_case = RecordTelemetry(telemetry_repository)


def get_heartbeat_use_case() -> RecordHeartbeat:
    return heartbeat_use_case


def get_telemetry_use_case() -> RecordTelemetry:
    return telemetry_use_case
