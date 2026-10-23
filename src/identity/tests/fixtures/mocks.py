from unittest.mock import AsyncMock, MagicMock

import pytest

from identity.repositories.token import IRefreshTokenRepository
from identity.repositories.user import IUserRepository
from identity.security.jwt import ITokenProvider
from identity.security.password_hasher import PasswordHasher
from identity.unit_of_work import IdentityUnitOfWork


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
def mock_unit_of_work(mock_user_repo, mock_token_repo):
    uow = MagicMock(spec=IdentityUnitOfWork)
    uow.user_repository = mock_user_repo
    uow.token_repository = mock_token_repo
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    return uow
