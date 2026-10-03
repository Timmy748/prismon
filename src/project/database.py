from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from project.settings import get_settings


@lru_cache
def get_session_factory() -> async_sessionmaker[
    AsyncSession
]:  # pragma: no cover
    engine = create_async_engine(get_settings().database_url)
    return async_sessionmaker(engine, expire_on_commit=False)
