from dataclasses import field
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):  # pragma: no cover
    model_config = SettingsConfigDict(
        case_sensitive=False, extra='ignore', env_file='.env'
    )
    DATABASE_URL: str = field(init=False)


@lru_cache
def get_settings() -> Settings:  # pragma: no cover
    return Settings()
