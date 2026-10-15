from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from agents.clients import identity as identity_client_module
from agents.dtos.user import UserDTO
from agents.exceptions import (
    IdentityServiceException,
    UserAuthenticationException,
    UserNotFoundException,
)


class FakeIdentityException(Exception):
    pass


class FakeIdentityUserNotFoundException(FakeIdentityException):
    pass


class FakeAuthenticationError(Exception):
    pass


@pytest.mark.asyncio
async def test_get_by_id_converts_identity_user():
    time = datetime.now()
    identity_user = SimpleNamespace(
        id=7,
        username='ada',
        email='ada@example.com',
        password_hash='hashed',
        created_at=time,
        updated_at=time,
    )
    identity_api = Mock()
    identity_api.get_by_id = AsyncMock(return_value=identity_user)
    client = identity_client_module.IdentityClient(identity_api)

    result = await client.get_by_id(7)

    assert result == UserDTO(id=7, username='ada', email='ada@example.com')


@pytest.mark.asyncio
async def test_get_by_id_maps_missing_user(monkeypatch):
    monkeypatch.setattr(
        identity_client_module,
        'IdentityUserNotFoundException',
        FakeIdentityUserNotFoundException,
    )
    identity_api = Mock()
    identity_api.get_by_id = AsyncMock(
        side_effect=FakeIdentityUserNotFoundException(7)
    )
    client = identity_client_module.IdentityClient(identity_api)

    with pytest.raises(UserNotFoundException):
        await client.get_by_id(7)


@pytest.mark.asyncio
async def test_get_by_id_maps_identity_service_failure(monkeypatch):
    monkeypatch.setattr(
        identity_client_module, 'IdentityException', FakeIdentityException
    )
    identity_api = Mock()
    identity_api.get_by_id = AsyncMock(side_effect=FakeIdentityException())
    client = identity_client_module.IdentityClient(identity_api)

    with pytest.raises(IdentityServiceException):
        await client.get_by_id(7)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'boundary_name',
    [
        'InvalidCredentialsException',
        'InvalidTokenException',
        'TokenExpiredException',
    ],
)
async def test_get_current_user_maps_authentication_errors(
    monkeypatch, boundary_name
):
    monkeypatch.setattr(
        identity_client_module, boundary_name, FakeAuthenticationError
    )
    identity_api = Mock()
    identity_api.get_current_user = AsyncMock(
        side_effect=FakeAuthenticationError()
    )
    client = identity_client_module.IdentityClient(identity_api)

    with pytest.raises(UserAuthenticationException):
        await client.get_current_user('access-token')


@pytest.mark.asyncio
async def test_get_current_user_maps_identity_service_failure(monkeypatch):
    monkeypatch.setattr(
        identity_client_module, 'IdentityException', FakeIdentityException
    )
    identity_api = Mock()
    identity_api.get_current_user = AsyncMock(
        side_effect=FakeIdentityException()
    )
    client = identity_client_module.IdentityClient(identity_api)

    with pytest.raises(IdentityServiceException):
        await client.get_current_user('access-token')


@pytest.mark.asyncio
async def test_get_current_user_converts_identity_user():
    identity_user = SimpleNamespace(
        id=8,
        username='grace',
        email='grace@example.com',
        password_hash='hashed',
        created_at=None,
        updated_at=None,
    )
    identity_api = Mock()
    identity_api.get_current_user = AsyncMock(return_value=identity_user)
    client = identity_client_module.IdentityClient(identity_api)

    result = await client.get_current_user('access-token')

    assert result == UserDTO(id=8, username='grace', email='grace@example.com')


def test_create_identity_client_wires_identity_api():
    with (
        patch('agents.clients.identity.IdentityPublicAPI') as api_factory,
        patch(
            'agents.clients.identity.create_user_repository'
        ) as repository_factory,
        patch('agents.clients.identity.create_token_provider') as token_factory,
    ):
        api = Mock()
        api_factory.return_value = api

        result = identity_client_module.create_identity_client()

    assert (result._identity_api, api_factory.call_args) == (
        api,
        call(repository_factory, token_factory),
    )
