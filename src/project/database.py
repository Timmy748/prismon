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
    engine = create_async_engine(get_settings().DATABASE_URL)
    logger.info('Project database session factory initialized')
    return async_sessionmaker(engine, expire_on_commit=False)
