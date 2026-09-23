from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.schemas.telemetry import (
    DiagnosticSignalResponse,
    MetricSeriesPointResponse,
    MetricSeriesResponse,
    NetworkDiagnosticResponse,
)
from app.application.use_cases.network_diagnostics import NetworkDiagnostics
from app.runtime import telemetry_repository

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])
diagnostics = NetworkDiagnostics(telemetry_repository)
_MAX_HISTORY_RANGE = timedelta(days=30)


@router.get("/latest")
def latest_metrics() -> list[dict[str, object]]:
    return [
        {
            "deviceId": sample.device_id,
            "timestamp": sample.timestamp,
            "name": sample.metric.name,
            "value": sample.metric.value,
            "unit": sample.metric.unit,
        }
        for sample in telemetry_repository.list_latest()
    ]


@router.get("/history", response_model=MetricSeriesResponse)
def metric_history(
    device_id: Annotated[str, Query(alias="deviceId", min_length=1, max_length=128)],
    name: Annotated[str, Query(min_length=1, max_length=128)],
    start: Annotated[datetime, Query()],
    end: Annotated[datetime, Query()],
    limit: Annotated[int, Query(ge=10, le=5000)] = 600,
    bucket_seconds: Annotated[int | None, Query(alias="bucketSeconds", ge=10, le=86400)] = None,
) -> MetricSeriesResponse:
    _validate_window(start, end)
    series = telemetry_repository.list_history(
        device_id,
        name,
        start,
        end,
        limit=limit,
        bucket_seconds=bucket_seconds,
    )
    return MetricSeriesResponse(
        deviceId=series.device_id,
        name=series.metric_name,
        unit=series.unit,
        start=series.start,
        end=series.end,
        bucketSeconds=series.bucket_seconds,
        truncated=series.truncated,
        points=[
            MetricSeriesPointResponse(
                timestamp=point.timestamp,
                value=point.value,
                minimum=point.minimum,
                maximum=point.maximum,
                samples=point.samples,
            )
            for point in series.points
        ],
    )


@router.get("/network-diagnostics", response_model=NetworkDiagnosticResponse)
def network_diagnostics(
    device_id: Annotated[str, Query(alias="deviceId", min_length=1, max_length=128)],
    window_minutes: Annotated[int, Query(alias="windowMinutes", ge=5, le=1440)] = 15,
    end: Annotated[datetime | None, Query()] = None,
) -> NetworkDiagnosticResponse:
    effective_end = end or datetime.now(UTC)
    if effective_end.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end must include a timezone",
        )
    result = diagnostics.evaluate(device_id, effective_end, window_minutes=window_minutes)
    return NetworkDiagnosticResponse(
        deviceId=result.device_id,
        state=result.state.value,
        coverage=result.coverage,
        windowStart=result.window_start,
        windowEnd=result.window_end,
        method=result.method,
        approximate=result.approximate,
        signals=[
            DiagnosticSignalResponse(
                name=signal.metric_name,
                latest=signal.latest,
                average=signal.average,
                unit=signal.unit,
                samples=signal.sample_count,
            )
            for signal in result.signals
        ],
        reasons=list(result.reasons),
    )


def _validate_window(start: datetime, end: datetime) -> None:
    if start.tzinfo is None or end.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start and end must include a timezone",
        )
    if end <= start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end must be after start",
        )
    if end - start > _MAX_HISTORY_RANGE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="history range cannot exceed 30 days",
        )
