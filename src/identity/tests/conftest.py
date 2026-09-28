import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from identity.dtos.user import UserDTO
from identity.entities.registry import mapper_registry
from identity.repositories.token import (
    IRefreshTokenRepository,
    RefreshTokenRepository,
)
from identity.repositories.user import IUserRepository, UserRepository
from identity.routes.auth import create_auth_router
from identity.routes.user import create_user_router
from identity.security.jwt import ITokenProvider, JwtTokenProvider
from identity.security.password_hasher import Argonid2Hasher, PasswordHasher

os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')
os.environ.setdefault('PASSWORD_PEPPER', 'test-pepper')
os.environ.setdefault('JWT_SECRET_KEY', 'test-jwt-secret-key')


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


@pytest.fixture
def route_user() -> UserDTO:
    now = datetime.now(timezone.utc)
    return UserDTO(
        id=1,
        username='ana',
        email='ana@example.com',
        password_hash='secret-hash',
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def identity_route_app(
    mock_user_repo,
    mock_token_repo,
    mock_password_hasher,
    mock_token_provider,
) -> FastAPI:
    app = FastAPI()

    async def user_repository_factory():
        return mock_user_repo

    async def token_repository_factory():
        return mock_token_repo

    app.include_router(
        create_user_router(
            password_hasher_factory=lambda: mock_password_hasher,
            token_provider_factory=lambda: mock_token_provider,
            repository_factory=user_repository_factory,
        )
    )
    app.include_router(
        create_auth_router(
            password_hasher_factory=lambda: mock_password_hasher,
            token_provider_factory=lambda: mock_token_provider,
            user_repository_factory=user_repository_factory,
            token_repository_factory=token_repository_factory,
        )
    )
    return app
