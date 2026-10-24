from dataclasses import field
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False, extra='ignore', env_file='.env'
    )

    OTEL_SERVICE_NAME: str = field(init=False)
    OTEL_EXPORTER_OTLP_ENDPOINT: str = field(init=False)
    OTEL_EXPORTER_OTLP_LOGS_ENDPOINT: str = field(init=False)


@lru_cache
def get_settings() -> Settings:  # pragma: no cover
    return Settings()
