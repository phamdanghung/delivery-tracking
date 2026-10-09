from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)
    app_env: Literal["local", "test", "staging", "production"] = "local"
    database_url: SecretStr = SecretStr("")
    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: SecretStr = SecretStr("")
    s3_secret_key: SecretStr = SecretStr("")
    s3_bucket: str = "fleet-pod"
    s3_public_endpoint_url: str = ""
    pod_read_url_seconds: int = Field(default=60, ge=1, le=300)
    pod_max_bytes: int = Field(default=20 * 1024 * 1024, ge=1024)
    pod_max_pixels: int = Field(default=40_000_000, ge=1)
    traccar_url: str = "http://localhost:8082"
    traccar_email: str = ""
    traccar_password: SecretStr = SecretStr("")
    jwt_secret: SecretStr = SecretStr("")
    jwt_access_seconds: int = 900
    jwt_refresh_seconds: int = 604800
    gps_poll_seconds: int = 5
    fixed_time_tolerance_seconds: int = Field(default=900, ge=0)
    default_service_seconds: int = Field(default=600, ge=0)
    route_solver_seconds: float = Field(default=3, gt=0)
    osrm_url: str = ""
    osrm_timeout_seconds: float = Field(default=10, gt=0)
    osrm_metadata_path: str = ""
    company_latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    company_longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
