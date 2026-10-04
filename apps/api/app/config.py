from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: Literal["local", "test", "staging", "production"] = "local"
    database_url: SecretStr = SecretStr("")
    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: SecretStr = SecretStr("")
    s3_secret_key: SecretStr = SecretStr("")
    s3_bucket: str = "fleet-pod"
    traccar_url: str = "http://localhost:8082"
    traccar_email: str = ""
    traccar_password: SecretStr = SecretStr("")
    jwt_secret: SecretStr = SecretStr("")
    jwt_access_seconds: int = 900
    jwt_refresh_seconds: int = 604800
    gps_poll_seconds: int = 5
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
