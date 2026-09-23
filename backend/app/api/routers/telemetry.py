from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.security import require_operator
from app.api.schemas.telemetry import (
    DiagnosticSignalResponse,
    MetricSeriesPointResponse,
    MetricSeriesResponse,
    NetworkDiagnosticResponse,
    TelemetryCompactionResponse,
)
from app.application.use_cases.network_diagnostics import NetworkDiagnostics
from app.infrastructure.repositories.retention import SqlAlchemyTelemetryRetentionRepository
from app.runtime import get_telemetry_retention_repository, telemetry_repository

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])
operator_router = APIRouter(prefix="/api/v1/operator/telemetry", tags=["telemetry-operator"])
diagnostics = NetworkDiagnostics(telemetry_repository)
_MAX_RAW_HISTORY_RANGE = timedelta(days=30)
_MAX_HOURLY_HISTORY_RANGE = timedelta(days=365)
RetentionRepositoryDependency = Annotated[
    SqlAlchemyTelemetryRetentionRepository,
    Depends(get_telemetry_retention_repository),
]
Operator = Annotated[None, Depends(require_operator)]


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
    retention_repository: RetentionRepositoryDependency,
    device_id: Annotated[str, Query(alias="deviceId", min_length=1, max_length=128)],
    name: Annotated[str, Query(min_length=1, max_length=128)],
    start: Annotated[datetime, Query()],
    end: Annotated[datetime, Query()],
    limit: Annotated[int, Query(ge=10, le=5000)] = 600,
    bucket_seconds: Annotated[int | None, Query(alias="bucketSeconds", ge=10, le=86400)] = None,
    resolution: Annotated[Literal["raw", "hourly"], Query()] = "raw",
) -> MetricSeriesResponse:
    maximum_range = _MAX_RAW_HISTORY_RANGE if resolution == "raw" else _MAX_HOURLY_HISTORY_RANGE
    _validate_window(start, end, maximum_range=maximum_range)

    if resolution == "hourly":
        if bucket_seconds not in (None, 3600):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="hourly resolution uses a fixed 3600-second bucket",
            )
        hourly_series = retention_repository.list_hourly(
            device_id,
            name,
            start,
            end,
            limit=limit,
        )
        unit = next(
            (point.unit for point in hourly_series.points if point.unit is not None),
            None,
        )
        return MetricSeriesResponse(
            deviceId=hourly_series.device_id,
            name=hourly_series.metric_name,
            unit=unit,
            start=hourly_series.start,
            end=hourly_series.end,
            bucketSeconds=3600,
            resolution="hourly",
            truncated=hourly_series.truncated,
            points=[
                MetricSeriesPointResponse(
                    timestamp=point.timestamp,
                    value=point.average,
                    minimum=point.minimum,
                    maximum=point.maximum,
                    samples=point.samples,
                    source="hourly_rollup",
                )
                for point in hourly_series.points
            ],
        )

    raw_series = telemetry_repository.list_history(
        device_id,
        name,
        start,
        end,
        limit=limit,
        bucket_seconds=bucket_seconds,
    )
    return MetricSeriesResponse(
        deviceId=raw_series.device_id,
        name=raw_series.metric_name,
        unit=raw_series.unit,
        start=raw_series.start,
        end=raw_series.end,
        bucketSeconds=raw_series.bucket_seconds,
        resolution="raw",
        truncated=raw_series.truncated,
        points=[
            MetricSeriesPointResponse(
                timestamp=point.timestamp,
                value=point.value,
                minimum=point.minimum,
                maximum=point.maximum,
                samples=point.samples,
                source="raw",
            )
            for point in raw_series.points
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


@operator_router.post("/compact", response_model=TelemetryCompactionResponse)
def compact_telemetry(
    _: Operator,
    retention_repository: RetentionRepositoryDependency,
    raw_retention_days: Annotated[int, Query(alias="rawRetentionDays", ge=1, le=90)] = 7,
) -> TelemetryCompactionResponse:
    cutoff = datetime.now(UTC) - timedelta(days=raw_retention_days)
    result = retention_repository.compact_before(cutoff)
    return TelemetryCompactionResponse(
        cutoff=result.cutoff,
        rollupsTouched=result.rollups_touched,
        rawSamplesDeleted=result.raw_samples_deleted,
        rawRetentionDays=raw_retention_days,
    )


def _validate_window(start: datetime, end: datetime, *, maximum_range: timedelta) -> None:
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
    if end - start > maximum_range:
        days = maximum_range.days
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"history range cannot exceed {days} days for this resolution",
        )
