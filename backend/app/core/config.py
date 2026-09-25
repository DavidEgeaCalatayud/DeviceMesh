from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEVICEMESH_", env_file=".env", extra="ignore", hide_input_in_errors=True)

    env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://devicemesh:devicemesh@localhost:5432/devicemesh"
    redis_url: str = "redis://localhost:6379/0"
    operator_token: str = "development-operator-change-me"
    operator_token_file: str | None = None
    database_url_file: str | None = None
    cors_origins: list[str] = ["http://localhost:5173"]
    public_reads: bool = True
    embedded_workers: bool = True
    event_backend: str = "memory"
    worker_metrics_host: str = "0.0.0.0"
    worker_metrics_port: int = Field(default=9100, ge=1, le=65535)
    session_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    refresh_ttl_seconds: int = Field(default=604800, ge=3600, le=2592000)
    agent_enrollment_ttl_seconds: int = 900
    agent_request_max_skew_seconds: int = 300
    agent_nonce_retention_seconds: int = 900
    device_offline_after_seconds: int = 90
    device_offline_sweep_interval_seconds: int = 15
    synthetic_probe_sweep_interval_seconds: int = 5
    synthetic_probe_batch_size: int = 10
    synthetic_probe_id: str = "backend-probe"
    synthetic_probe_offline_after_seconds: int = 120
    synthetic_probe_work_lease_seconds: int = 60
    synthetic_probe_credential_ttl_days: int = Field(default=90, ge=1, le=3650)
    synthetic_consensus_quorum_ratio: float = Field(default=0.5, ge=0.5, lt=1.0)
    synthetic_consensus_minimum_quorum: int = Field(default=1, ge=1, le=32)
    synthetic_consensus_round_window_seconds: int = Field(default=30, ge=1, le=300)
    retention_run_interval_seconds: int = Field(default=3600, ge=60, le=86400)
    telemetry_raw_retention_days: int = Field(default=7, ge=1, le=90)
    telemetry_hourly_retention_days: int = Field(default=365, ge=30, le=3650)
    event_retention_days: int = Field(default=90, ge=7, le=3650)
    # SLOs support a 90-day window; check history must never be configured shorter.
    synthetic_check_retention_days: int = Field(default=90, ge=90, le=3650)

    @model_validator(mode="after")
    def validate_runtime(self) -> Self:
        for field in ("operator_token", "database_url"):
            filename = getattr(self, f"{field}_file")
            if filename:
                setattr(self, field, Path(filename).read_text().strip())
        if self.event_backend not in {"memory", "redis"}:
            raise ValueError("event_backend must be memory or redis")
        if self.env == "production":
            if len(self.operator_token) < 32 or "change-me" in self.operator_token:
                raise ValueError("production requires a unique operator token of at least 32 characters")
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("production requires PostgreSQL with the psycopg driver")
            if self.public_reads:
                raise ValueError("public_reads must be false in production")
            if "*" in self.cors_origins:
                raise ValueError("wildcard CORS is not allowed in production")
        for field in (
            "device_offline_after_seconds", "device_offline_sweep_interval_seconds",
            "synthetic_probe_sweep_interval_seconds", "synthetic_probe_batch_size",
            "synthetic_probe_work_lease_seconds", "synthetic_probe_credential_ttl_days",
            "synthetic_consensus_minimum_quorum", "synthetic_consensus_round_window_seconds",
            "retention_run_interval_seconds", "telemetry_raw_retention_days",
            "telemetry_hourly_retention_days", "event_retention_days",
            "synthetic_check_retention_days",
        ):
            if getattr(self, field) <= 0:
                raise ValueError(f"{field} must be positive")
        if self.telemetry_hourly_retention_days <= self.telemetry_raw_retention_days:
            raise ValueError("telemetry_hourly_retention_days must be greater than telemetry_raw_retention_days")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
