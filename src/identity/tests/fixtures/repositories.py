import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from identity.repositories.token import RefreshTokenRepository
from identity.repositories.user import UserRepository


@pytest.fixture
def user_repo(session: AsyncSession) -> UserRepository:
    return UserRepository(session)


@pytest.fixture
def token_repo(session: AsyncSession) -> RefreshTokenRepository:
    return RefreshTokenRepository(session)
