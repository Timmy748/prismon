from dataclasses import field
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):  # pragma: no cover
    model_config = SettingsConfigDict(
        case_sensitive=False, extra='ignore', env_file='.env'
    )
    database_url: str = field(init=False)
    storage_path: Path = Path('storage')


@lru_cache
def get_settings() -> Settings:  # pragma: no cover
    return Settings()
