from dataclasses import field
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):  # pragma: no cover
    model_config = SettingsConfigDict(
        case_sensitive=False, extra='ignore', env_file='.env'
    )
    DATABASE_URL: str = field(init=False)
    RUSTFS_ENDPOINT_URL: str = field(init=False)
    RUSTFS_PUBLIC_ENDPOINT_URL: str = field(init=False)
    RUSTFS_BUCKET: str = field(init=False)
    RUSTFS_ACCESS_KEY: str = field(init=False)
    RUSTFS_SECRET_KEY: str = field(init=False)
    RUSTFS_REGION: str = field(init=False)
    RUSTFS_PRESIGNED_URL_TTL_SECONDS: int = Field(default=3600, ge=1, le=604800)
    API_KEY_KEK: SecretStr = SecretStr('')


@lru_cache
def get_settings() -> Settings:  # pragma: no cover
    return Settings()
