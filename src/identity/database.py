from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.logs import get_logger
from identity.settings import get_settings

logger = get_logger(__name__)


@lru_cache
def get_session_factory() -> async_sessionmaker[
    AsyncSession
]:  # pragma: no cover
    engine = create_async_engine(get_settings().DATABASE_URL)
    logger.info('Identity database engine configured')
    return async_sessionmaker(engine, expire_on_commit=False)
