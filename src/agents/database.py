from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from infra.logs import get_logger
from infra.settings import get_settings

logger = get_logger(__name__)


@lru_cache
def get_session_factory() -> async_sessionmaker[
    AsyncSession
]:  # pragma: no cover
    settings = get_settings()
    logger.info('Creating agents database session factory')
    engine = create_async_engine(settings.DATABASE_URL)
    return async_sessionmaker(engine, expire_on_commit=False)
