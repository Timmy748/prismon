from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from argon2 import PasswordHasher
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from identity.entities.registry import mapper_registry
from identity.repositories.token import (
    IRefreshTokenRepository,
    RefreshTokenRepository,
)
from identity.repositories.user import IUserRepository, UserRepository
from identity.security.jwt import ITokenProvider, JwtTokenProvider
from identity.security.password_hasher import Argonid2Hasher


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


@pytest.fixture
def argon2_hasher() -> Argonid2Hasher:
    return Argonid2Hasher(pepper='pepper')


@pytest.fixture
def jwt_provider() -> JwtTokenProvider:
    return JwtTokenProvider(
        secret_key='minha-chave-secreta-de-teste',
        algorithm='HS256',
        expires_in_minutes=15,
    )


@pytest.fixture
def mock_user_repo():
    return AsyncMock(spec=IUserRepository)


@pytest.fixture
def mock_token_repo():
    return AsyncMock(spec=IRefreshTokenRepository)


@pytest.fixture
def mock_password_hasher():
    return MagicMock(spec=PasswordHasher)


@pytest.fixture
def mock_token_provider():
    return MagicMock(spec=ITokenProvider)
