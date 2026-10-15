from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

from agents.clients import project as project_client_module
from agents.clients.project import ProjectClient, create_project_client


@pytest.mark.asyncio
async def test_has_permission_returns_false_without_active_member():
    member_repository = Mock()
    member_repository.get_members = AsyncMock(
        return_value=SimpleNamespace(
            items=[],
            pagination=SimpleNamespace(limit=1),
        )
    )
    repository_factory = AsyncMock(return_value=member_repository)
    project_api = Mock()
    client = ProjectClient(project_api, repository_factory)

    result = await client.has_permission(
        project_id=3,
        user_id=9,
        permission='chat:read',
    )

    assert result is False


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
    client = ProjectClient(Mock(), AsyncMock(return_value=member_repository))

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
    client = ProjectClient(
        project_api, AsyncMock(return_value=member_repository)
    )

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
    client = ProjectClient(
        project_api, AsyncMock(return_value=member_repository)
    )

    result = await client.has_permission(3, 9, 'chat:create')

    assert result is False


def test_create_project_client_wires_public_api():
    with (
        pytest.MonkeyPatch.context() as monkeypatch,
    ):
        api = Mock()
        api_factory = Mock(return_value=api)
        dependency_factories = {
            'create_project_repository': Mock(),
            'create_member_repository': Mock(),
            'create_document_repository': Mock(),
            'create_asset_repository': Mock(),
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
            project_repository_factory=dependency_factories[
                'create_project_repository'
            ],
            member_repository_factory=dependency_factories[
                'create_member_repository'
            ],
            document_repository_factory=dependency_factories[
                'create_document_repository'
            ],
            asset_repository_factory=dependency_factories[
                'create_asset_repository'
            ],
            storage_factory=dependency_factories['create_storage'],
        ),
    )
