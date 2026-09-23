from datetime import datetime, timedelta

from app.application.ports import TelemetryRepository
from app.domain.telemetry.models import (
    DiagnosticSignal,
    DiagnosticState,
    NetworkDiagnostic,
)

_NETWORK_METRICS = (
    "network.latency.ms",
    "network.jitter.ms",
    "network.packet_loss.percent",
)

_DEGRADED_THRESHOLDS = {
    "network.latency.ms": 100.0,
    "network.jitter.ms": 20.0,
    "network.packet_loss.percent": 1.0,
}

_POOR_THRESHOLDS = {
    "network.latency.ms": 250.0,
    "network.jitter.ms": 50.0,
    "network.packet_loss.percent": 5.0,
}

_LABELS = {
    "network.latency.ms": "Latency",
    "network.jitter.ms": "Jitter",
    "network.packet_loss.percent": "Packet loss",
}


class NetworkDiagnostics:
    def __init__(self, telemetry: TelemetryRepository) -> None:
        self._telemetry = telemetry

    def evaluate(
        self,
        device_id: str,
        end: datetime,
        *,
        window_minutes: int = 15,
    ) -> NetworkDiagnostic:
        start = end - timedelta(minutes=window_minutes)
        signals: list[DiagnosticSignal] = []
        missing: list[str] = []

        for metric_name in _NETWORK_METRICS:
            series = self._telemetry.list_history(
                device_id,
                metric_name,
                start,
                end,
                limit=2000,
            )
            if not series.points:
                missing.append(metric_name)
                continue
            total_samples = sum(point.samples for point in series.points)
            weighted_total = sum(point.value * point.samples for point in series.points)
            signals.append(
                DiagnosticSignal(
                    metric_name=metric_name,
                    latest=series.points[-1].value,
                    average=weighted_total / total_samples,
                    unit=series.unit,
                    sample_count=total_samples,
                )
            )

        if not signals:
            return NetworkDiagnostic(
                device_id=device_id,
                state=DiagnosticState.UNKNOWN,
                coverage="none",
                window_start=start,
                window_end=end,
                signals=(),
                reasons=("No network-quality measurements are available in this window.",),
            )

        state = DiagnosticState.HEALTHY
        reasons: list[str] = []
        for signal in signals:
            poor = _POOR_THRESHOLDS[signal.metric_name]
            degraded = _DEGRADED_THRESHOLDS[signal.metric_name]
            label = _LABELS[signal.metric_name]
            if signal.average >= poor:
                state = DiagnosticState.POOR
                reasons.append(
                    f"{label} average {signal.average:.1f} {signal.unit or ''} "
                    f"meets the poor threshold ({poor:g}).".replace("  ", " ")
                )
            elif signal.average >= degraded:
                if state is DiagnosticState.HEALTHY:
                    state = DiagnosticState.DEGRADED
                reasons.append(
                    f"{label} average {signal.average:.1f} {signal.unit or ''} "
                    f"meets the degraded threshold ({degraded:g}).".replace("  ", " ")
                )

        if not reasons:
            reasons.append("Available network-quality signals remain below V1 degraded thresholds.")

        coverage = "complete" if not missing else "partial"
        if missing:
            readable = ", ".join(_LABELS[name].lower() for name in missing)
            reasons.append(f"Diagnostic coverage is partial because {readable} is unavailable.")

        return NetworkDiagnostic(
            device_id=device_id,
            state=state,
            coverage=coverage,
            window_start=start,
            window_end=end,
            signals=tuple(signals),
            reasons=tuple(reasons),
        )
