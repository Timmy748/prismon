from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

from agents.clients import project as project_client_module
from agents.clients.project import ProjectClient, create_project_client
from agents.exceptions import ApiKeyNotFoundException
from project.exceptions import (
    ApiKeyNotFoundException as ProjectApiKeyNotFoundException,
)


def _uow(member_repository):
    unit_of_work = AsyncMock()
    unit_of_work.member_repository = member_repository
    unit_of_work.__aenter__.return_value = unit_of_work
    return unit_of_work


@pytest.mark.asyncio
async def test_has_permission_returns_false_without_active_member():
    member_repository = Mock()
    member_repository.get_members = AsyncMock(
        return_value=SimpleNamespace(
            items=[],
            pagination=SimpleNamespace(limit=1),
        )
    )
    unit_of_work = _uow(member_repository)
    unit_of_work_factory = Mock(return_value=unit_of_work)
    project_api = Mock()
    client = ProjectClient(project_api, unit_of_work_factory)

    result = await client.has_permission(
        project_id=3,
        user_id=9,
        permission='chat:read',
    )

    assert result is False
    unit_of_work.__aexit__.assert_awaited_once_with(None, None, None)


@pytest.mark.asyncio
async def test_has_permission_queries_only_active_member_for_user():
    member = SimpleNamespace(
        id=1,
        project_id=3,
        role='member',
        status='active',
        user_id=9,
    )
    member_repository = Mock()
    member_repository.get_members = AsyncMock(
        return_value=SimpleNamespace(
            items=[member],
            pagination=SimpleNamespace(limit=1),
        )
    )
    unit_of_work = _uow(member_repository)
    client = ProjectClient(Mock(), Mock(return_value=unit_of_work))

    await client.has_permission(3, 9, 'chat:read')

    call_args = member_repository.get_members.await_args
    pagination = call_args.kwargs['pagination']
    assert (
        call_args.args,
        pagination.cursor,
        pagination.limit,
        pagination.more,
        call_args.kwargs['user_id'],
        call_args.kwargs['status'],
    ) == ((3,), None, 1, False, 9, 'active')


@pytest.mark.asyncio
async def test_has_permission_delegates_member_role_and_requested_permission():
    member = SimpleNamespace(
        id=1,
        project_id=3,
        role='collaborator',
        status='active',
        user_id=9,
    )
    member_repository = Mock()
    member_repository.get_members = AsyncMock(
        return_value=SimpleNamespace(
            items=[member],
            pagination=SimpleNamespace(limit=1),
        )
    )
    project_api = Mock()
    project_api.has_permission.return_value = True
    unit_of_work = _uow(member_repository)
    client = ProjectClient(project_api, Mock(return_value=unit_of_work))

    await client.has_permission(3, 9, 'workflow:use')

    project_api.has_permission.assert_called_once_with(
        'collaborator',
        'workflow:use',
    )


@pytest.mark.asyncio
async def test_has_permission_returns_project_permission_result():
    member = SimpleNamespace(
        id=1,
        project_id=3,
        role='collaborator',
        status='active',
        user_id=9,
    )
    member_repository = Mock()
    member_repository.get_members = AsyncMock(
        return_value=SimpleNamespace(
            items=[member],
            pagination=SimpleNamespace(limit=1),
        )
    )
    project_api = Mock()
    project_api.has_permission.return_value = False
    unit_of_work = _uow(member_repository)
    client = ProjectClient(project_api, Mock(return_value=unit_of_work))

    result = await client.has_permission(3, 9, 'chat:create')

    assert result is False


@pytest.mark.asyncio
async def test_get_api_key_delegates_to_project_public_api():
    project_api = Mock()
    project_api.get_api_key = AsyncMock(return_value='decrypted-secret')
    client = ProjectClient(project_api)

    result = await client.get_api_key(3, 9, 123)

    assert result == 'decrypted-secret'
    project_api.get_api_key.assert_awaited_once_with(3, 9, 123)


@pytest.mark.asyncio
async def test_get_api_key_translates_missing_key_exception():
    project_api = Mock()
    project_api.get_api_key = AsyncMock(
        side_effect=ProjectApiKeyNotFoundException(123)
    )
    client = ProjectClient(project_api)

    with pytest.raises(ApiKeyNotFoundException, match='API key 123 not found'):
        await client.get_api_key(3, 9, 123)


def test_create_project_client_wires_public_api():
    with (
        pytest.MonkeyPatch.context() as monkeypatch,
    ):
        api = Mock()
        api_factory = Mock(return_value=api)
        dependency_factories = {
            'create_project_unit_of_work': Mock(),
            'create_storage': Mock(),
        }
        monkeypatch.setattr(
            project_client_module, 'ProjectPublicAPI', api_factory
        )
        for name, factory in dependency_factories.items():
            monkeypatch.setattr(project_client_module, name, factory)

        result = create_project_client()

    assert (result._project_api, api_factory.call_args) == (
        api,
        call(
            unit_of_work_factory=dependency_factories[
                'create_project_unit_of_work'
            ],
            storage_factory=dependency_factories['create_storage'],
        ),
    )
