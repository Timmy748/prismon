from datetime import datetime, timezone

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from project.dtos.api_key import CreateApiKeyDTO
from project.dtos.page import PaginationDTO
from project.entities.api_key import ApiKey, ApiKeyProvider
from project.unit_of_work import UnitOfWork


@pytest.mark.asyncio
@pytest.mark.parametrize(('member_id', 'project_id'), [(None, None), (1, 1)])
async def test_repository_rejects_invalid_owner_scope(
    api_key_repo, member_id, project_id
):
    data = CreateApiKeyDTO(
        provider=ApiKeyProvider.OPENROUTER,
        api_hint='****',
        encrypted_api_key=b'ciphertext',
        encrypted_dek=b'wrapped',
        api_key_nonce=b'nonce',
        dek_nonce=b'nonce',
        member_id=member_id,
        project_id=project_id,
    )
    with pytest.raises(IntegrityError):
        await api_key_repo.create_api_key(data)


@pytest.mark.asyncio
async def test_unit_of_work_exposes_api_key_repository(uow_dependencies):
    async with UnitOfWork() as uow:
        assert uow.api_key_repository is not None


def test_unit_of_work_hides_api_key_repository_outside_context():
    with pytest.raises(RuntimeError, match='context is not active'):
        UnitOfWork().api_key_repository


@pytest.mark.asyncio
@pytest.mark.parametrize('scope', ['member', 'project'])
async def test_cursor_paginates_equal_timestamps_and_isolates_scope(
    api_key_context, session, project_repo, scope
):
    uow, project, owner, other_member = api_key_context
    repo = uow.api_key_repository
    other_project = await project_repo.create_project('Other', 1)
    owner_args = (
        {'member_id': owner.id}
        if scope == 'member'
        else {'project_id': project.id}
    )
    other_args = (
        {'member_id': other_member.id}
        if scope == 'member'
        else {'project_id': other_project.id}
    )

    def data(**kwargs):
        return CreateApiKeyDTO(
            provider=ApiKeyProvider.OPENROUTER,
            api_hint='****',
            encrypted_api_key=b'x',
            encrypted_dek=b'x',
            api_key_nonce=b'x',
            dek_nonce=b'x',
            **kwargs,
        )

    first = await repo.create_api_key(data(**owner_args))
    second = await repo.create_api_key(data(**owner_args))
    await repo.create_api_key(data(**other_args))
    await session.execute(
        update(ApiKey).values(
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc)
        )
    )
    listing = (
        repo.list_member_api_keys
        if scope == 'member'
        else repo.list_project_api_keys
    )
    owner_id = owner.id if scope == 'member' else project.id
    page = await listing(owner_id, PaginationDTO(limit=1))
    next_page = await listing(
        owner_id, PaginationDTO(limit=1, cursor=page.pagination.cursor)
    )
    assert [key.id for key in page.items + next_page.items] == [
        second.id,
        first.id,
    ]
    assert page.pagination.more is True
    assert next_page.pagination.more is False
    assert next_page.pagination.cursor is None


@pytest.mark.asyncio
@pytest.mark.parametrize(('limit', 'expected'), [(0, 1), (101, 100)])
async def test_repository_clamps_page_size(api_key_context, limit, expected):
    uow, project, _, _ = api_key_context
    page = await uow.api_key_repository.list_project_api_keys(
        project.id, PaginationDTO(limit=limit)
    )
    assert page.pagination.limit == expected
