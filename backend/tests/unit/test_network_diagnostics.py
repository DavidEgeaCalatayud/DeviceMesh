from datetime import UTC, datetime, timedelta

from app.application.use_cases.network_diagnostics import NetworkDiagnostics
from app.domain.telemetry.models import (
    DiagnosticState,
    MetricSeries,
    MetricSeriesPoint,
)


class FakeTelemetryRepository:
    def append(self, batch: object) -> None:
        raise NotImplementedError

    def list_latest(self) -> list[object]:
        return []

    def list_history(
        self,
        device_id: str,
        metric_name: str,
        start: datetime,
        end: datetime,
        *,
        limit: int = 1000,
        bucket_seconds: int | None = None,
    ) -> MetricSeries:
        values = {
            "network.latency.ms": (42.0, "ms"),
            "network.jitter.ms": (8.0, "ms"),
            "network.packet_loss.percent": (2.0, "percent"),
        }
        value, unit = values[metric_name]
        return MetricSeries(
            device_id=device_id,
            metric_name=metric_name,
            unit=unit,
            start=start,
            end=end,
            bucket_seconds=None,
            points=(MetricSeriesPoint(end - timedelta(seconds=1), value, value, value, 1),),
        )


def test_network_diagnostic_is_explainable_and_uses_worst_signal() -> None:
    end = datetime.now(UTC)
    diagnostic = NetworkDiagnostics(FakeTelemetryRepository()).evaluate("device-1", end)
    assert diagnostic.state is DiagnosticState.DEGRADED
    assert diagnostic.coverage == "complete"
    assert any("Packet loss" in reason for reason in diagnostic.reasons)
    assert diagnostic.method == "threshold-heuristic-v1"
    assert diagnostic.approximate is True
