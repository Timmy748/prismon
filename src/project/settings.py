from dataclasses import field
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False, extra='ignore', env_file='.env'
    )
    database_url: str = field(init=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
