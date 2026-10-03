# ruff: noqa: PLR2004
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import project.clients.client_user as client_module
from project.clients.client_user import IdentityClient, create_identity_client
from project.dtos.user import UserDTO
from project.exceptions import (
    ProjectUserAuthenticationException,
    ProjectUserNotFoundException,
    ProjectUserServiceException,
)


class FakeIdentityException(Exception):
    pass


class FakeInvalidTokenException(FakeIdentityException):
    pass


class FakeUserNotFoundException(FakeIdentityException):
    pass


def api_user():
    return SimpleNamespace(id=8, username='lee', email='lee@example.com')


@pytest.fixture
def identity_api():
    api = SimpleNamespace(
        get_by_id=AsyncMock(return_value=api_user()),
        get_current_user=AsyncMock(return_value=api_user()),
    )
    return api


@pytest.fixture
def identity_client(identity_api):
    return IdentityClient(identity_api)


@pytest.mark.asyncio
async def test_get_by_id_returns_project_owned_user(identity_client):
    user = await identity_client.get_by_id(8)
    assert user == UserDTO(8, 'lee', 'lee@example.com')


@pytest.mark.asyncio
async def test_get_current_user_returns_project_owned_user(identity_client):
    user = await identity_client.get_current_user('access')
    assert user == UserDTO(8, 'lee', 'lee@example.com')


@pytest.mark.asyncio
async def test_get_by_id_translates_identity_user_not_found(
    monkeypatch, identity_api
):
    monkeypatch.setattr(
        client_module, 'IdentityException', FakeIdentityException
    )
    monkeypatch.setattr(
        client_module, 'UserNotFoundException', FakeUserNotFoundException
    )
    identity_api.get_by_id.side_effect = FakeUserNotFoundException('missing')
    client = IdentityClient(identity_api)
    with pytest.raises(ProjectUserNotFoundException) as error:
        await client.get_by_id(88)
    assert error.value.user_id == 88
    assert isinstance(error.value.__cause__, FakeUserNotFoundException)


@pytest.mark.asyncio
async def test_get_by_id_translates_other_identity_error(
    monkeypatch, identity_api
):
    monkeypatch.setattr(
        client_module, 'IdentityException', FakeIdentityException
    )
    identity_api.get_by_id.side_effect = FakeIdentityException('down')
    with pytest.raises(ProjectUserServiceException):
        await IdentityClient(identity_api).get_by_id(8)


@pytest.mark.asyncio
async def test_get_current_user_translates_invalid_token(
    monkeypatch, identity_api
):
    monkeypatch.setattr(
        client_module, 'IdentityException', FakeIdentityException
    )
    monkeypatch.setattr(
        client_module, 'InvalidTokenException', FakeInvalidTokenException
    )
    identity_api.get_current_user.side_effect = FakeInvalidTokenException()
    with pytest.raises(ProjectUserAuthenticationException):
        await IdentityClient(identity_api).get_current_user('bad')


@pytest.mark.asyncio
async def test_get_current_user_translates_other_identity_error(
    monkeypatch, identity_api
):
    monkeypatch.setattr(
        client_module, 'IdentityException', FakeIdentityException
    )
    identity_api.get_current_user.side_effect = FakeIdentityException('down')
    with pytest.raises(ProjectUserServiceException):
        await IdentityClient(identity_api).get_current_user('token')


def test_create_identity_client_uses_public_api_factory():
    assert isinstance(create_identity_client(), IdentityClient)
