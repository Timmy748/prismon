from dataclasses import field
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False, extra='ignore', env_file='.env'
    )

    DATABASE_URL: str = field(init=False)
    PASSWORD_PEPPER: SecretStr = field(init=False)
    JWT_SECRET_KEY: SecretStr = field(init=False)
    JWT_ALGORITHM: str = 'HS256'
    JWT_EXPIRES_IN_MINUTES: int = 15


@lru_cache
def get_settings() -> Settings:  # pragma: no cover
    return Settings()
