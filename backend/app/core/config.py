from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEVICEMESH_", env_file=".env", extra="ignore")

    env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://devicemesh:devicemesh@localhost:5432/devicemesh"
    redis_url: str = "redis://localhost:6379/0"
    operator_token: str = "development-operator-change-me"
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
