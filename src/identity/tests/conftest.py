import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from identity.entities.registry import mapper_registry
from identity.entities.token import RefreshToken  # noqa: F401
from identity.entities.user import User  # noqa: F401
from identity.repositories.token import RefreshTokenRepository
from identity.repositories.user import UserRepository


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')

    async with engine.begin() as conn:
        await conn.run_sync(mapper_registry.metadata.create_all)

    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(mapper_registry.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def user_repo(session: AsyncSession) -> UserRepository:
    return UserRepository(session)


@pytest.fixture
def token_repo(
    session: AsyncSession,
) -> RefreshTokenRepository:
    return RefreshTokenRepository(session)
