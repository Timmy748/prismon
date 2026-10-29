from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from project.clients.client_user import IdentityClient


def _api_user():
    return SimpleNamespace(id=8, username='lee', email='lee@example.com')


@pytest.fixture
def identity_api():
    api_user = _api_user()
    return SimpleNamespace(
        get_by_id=AsyncMock(return_value=api_user),
        get_current_user=AsyncMock(return_value=api_user),
    )


@pytest.fixture
def identity_client(identity_api):
    return IdentityClient(identity_api)
