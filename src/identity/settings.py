from dataclasses import field
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False, extra='ignore', env_file='.env'
    )

    database_url: str = field(init=False)
    password_pepper: SecretStr = field(init=False)
    jwt_secret_key: SecretStr = field(init=False)
    jwt_algorithm: str = 'HS256'
    jwt_expires_in_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
