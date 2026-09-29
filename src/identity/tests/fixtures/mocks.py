from unittest.mock import AsyncMock, MagicMock

import pytest

from identity.repositories.token import IRefreshTokenRepository
from identity.repositories.user import IUserRepository
from identity.security.jwt import ITokenProvider
from identity.security.password_hasher import PasswordHasher


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
