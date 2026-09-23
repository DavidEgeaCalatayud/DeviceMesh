from app.application.ports import TelemetryRepository
from app.domain.telemetry.models import TelemetryBatch


class RecordTelemetry:
    def __init__(self, telemetry: TelemetryRepository) -> None:
        self._telemetry = telemetry

    def execute(self, batch: TelemetryBatch) -> None:
        if len(batch.metrics) > 256:
            raise ValueError("telemetry batch exceeds 256 metrics")
        self._telemetry.append(batch)
