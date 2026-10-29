from datetime import UTC, datetime

import pytest

from project.dtos.api_key import ApiKeyDTO
from project.dtos.page import PaginationDTO
from project.entities.api_key import ApiKeyProvider
from project.entities.member import MemberRole, MemberStatus
from project.exceptions import (
    ApiKeyNotFoundException,
    InsufficientProjectPermissionException,
    ProjectNotFoundException,
)
from project.use_cases.api_key import (
    create_member_api_key,
    create_project_api_key,
    delete_api_key,
    get_api_key,
    list_member_api_keys,
    list_project_api_keys,
)


def _encrypted_api_key(
    key_encryptor, secret, *, member_id=None, project_id=None
):
    encrypted = key_encryptor.encrypt(secret)
    return ApiKeyDTO(
        id=56,
        provider=ApiKeyProvider.OPENROUTER,
        api_hint='****',
        encrypted_api_key=encrypted.encrypted_api_key,
        encrypted_dek=encrypted.encrypted_dek,
        api_key_nonce=encrypted.api_key_nonce,
        dek_nonce=encrypted.dek_nonce,
        member_id=member_id,
        project_id=project_id,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('secret', 'hint'), [('secret-1234', '****1234'), ('abc', '****')]
)
async def test_member_create_returns_masked_hint(
    api_key_context, key_encryptor, secret, hint
):
    uow, project, member, _ = api_key_context
    result = await create_member_api_key(
        uow, project.id, 1, ApiKeyProvider.OPENROUTER, secret, key_encryptor
    )
    stored = await uow.api_key_repository.get_api_key(result.id)
    assert result.api_hint == hint
    assert stored.member_id == member.id
    assert secret.encode() not in stored.encrypted_api_key


@pytest.mark.asyncio
async def test_owner_can_create_project_key(api_key_context, key_encryptor):
    uow, project, _, _ = api_key_context
    result = await create_project_api_key(
        uow, project.id, 1, ApiKeyProvider.OPENROUTER, 'secret', key_encryptor
    )
    assert (
        await uow.api_key_repository.get_api_key(result.id)
    ).project_id == project.id


@pytest.mark.asyncio
async def test_nonowner_cannot_create_project_key(
    api_key_context, key_encryptor
):
    uow, project, _, _ = api_key_context
    with pytest.raises(InsufficientProjectPermissionException):
        await create_project_api_key(
            uow,
            project.id,
            2,
            ApiKeyProvider.OPENROUTER,
            'secret',
            key_encryptor,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize('scope', ['member', 'project'])
async def test_list_only_own_scope_hints(api_key_context, key_encryptor, scope):
    uow, project, _, _ = api_key_context
    member_key = await create_member_api_key(
        uow, project.id, 1, ApiKeyProvider.OPENROUTER, 'personal', key_encryptor
    )
    project_key = await create_project_api_key(
        uow, project.id, 1, ApiKeyProvider.OPENROUTER, 'project', key_encryptor
    )
    if scope == 'member':
        result = await list_member_api_keys(uow, project.id, 1)
        expected = member_key
    else:
        result = await list_project_api_keys(uow, project.id, 2)
        expected = project_key
    assert result.items == [expected]


@pytest.mark.asyncio
@pytest.mark.parametrize('scope', ['member', 'project'])
async def test_authorized_delete_removes_key(
    api_key_context, key_encryptor, scope
):
    uow, project, _, _ = api_key_context
    create = (
        create_member_api_key if scope == 'member' else create_project_api_key
    )
    key = await create(
        uow, project.id, 1, ApiKeyProvider.OPENROUTER, 'secret', key_encryptor
    )
    await delete_api_key(uow, project.id, 1, key.id)
    assert await uow.api_key_repository.get_api_key(key.id) is None


@pytest.mark.asyncio
async def test_other_members_key_is_hidden(api_key_context, key_encryptor):
    uow, project, _, _ = api_key_context
    key = await create_member_api_key(
        uow, project.id, 1, ApiKeyProvider.OPENROUTER, 'secret', key_encryptor
    )
    with pytest.raises(ApiKeyNotFoundException):
        await delete_api_key(uow, project.id, 2, key.id)


@pytest.mark.asyncio
async def test_nonowner_cannot_delete_project_key(
    api_key_context, key_encryptor
):
    uow, project, _, _ = api_key_context
    key = await create_project_api_key(
        uow, project.id, 1, ApiKeyProvider.OPENROUTER, 'secret', key_encryptor
    )
    with pytest.raises(InsufficientProjectPermissionException):
        await delete_api_key(uow, project.id, 2, key.id)


@pytest.mark.asyncio
async def test_missing_key_is_hidden(api_key_context):
    uow, project, _, _ = api_key_context
    with pytest.raises(ApiKeyNotFoundException):
        await delete_api_key(uow, project.id, 1, 999)


@pytest.mark.asyncio
async def test_get_api_key_decrypts_own_member_key(
    api_key_use_case_context, key_encryptor
):
    uow, project, members = api_key_use_case_context
    secret = 'member-secret'
    key = _encrypted_api_key(key_encryptor, secret, member_id=members[1].id)
    uow.api_key_repository.get_api_key.return_value = key

    result = await get_api_key(uow, project.id, 1, key.id, key_encryptor)

    assert result == secret


@pytest.mark.asyncio
async def test_project_key_is_readable_by_active_project_member(
    api_key_use_case_context, key_encryptor
):
    uow, project, _ = api_key_use_case_context
    secret = 'shared-project-secret'
    key = _encrypted_api_key(key_encryptor, secret, project_id=project.id)
    uow.api_key_repository.get_api_key.return_value = key

    result = await get_api_key(uow, project.id, 2, key.id, key_encryptor)

    assert result == secret


@pytest.mark.asyncio
async def test_get_api_key_hides_another_members_key(
    api_key_use_case_context, key_encryptor
):
    uow, project, members = api_key_use_case_context
    key = _encrypted_api_key(
        key_encryptor, 'private-secret', member_id=members[1].id
    )
    uow.api_key_repository.get_api_key.return_value = key

    with pytest.raises(ApiKeyNotFoundException):
        await get_api_key(uow, project.id, 2, key.id, key_encryptor)


@pytest.mark.asyncio
async def test_get_api_key_hides_key_from_another_project(
    api_key_use_case_context, key_encryptor
):
    uow, project, _ = api_key_use_case_context
    key = _encrypted_api_key(
        key_encryptor, 'other-project-secret', project_id=project.id + 1
    )
    uow.api_key_repository.get_api_key.return_value = key

    with pytest.raises(ApiKeyNotFoundException):
        await get_api_key(uow, project.id, 1, key.id, key_encryptor)


@pytest.mark.asyncio
async def test_get_api_key_hides_missing_key(
    api_key_use_case_context, key_encryptor
):
    uow, project, _ = api_key_use_case_context
    uow.api_key_repository.get_api_key.return_value = None

    with pytest.raises(ApiKeyNotFoundException):
        await get_api_key(uow, project.id, 1, 999, key_encryptor)


@pytest.mark.asyncio
@pytest.mark.parametrize('user_id', [3, 4])
async def test_get_api_key_requires_active_project_membership(
    api_key_use_case_context, key_encryptor, user_id
):
    uow, project, _ = api_key_use_case_context

    with pytest.raises(ProjectNotFoundException):
        await get_api_key(uow, project.id, user_id, 999, key_encryptor)


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [None, MemberStatus.PENDING])
async def test_list_requires_active_member(
    api_key_context, member_repo, status
):
    uow, project, _, _ = api_key_context
    if status:
        await member_repo.create_member(
            project.id, 3, MemberRole.MEMBER, status
        )
    with pytest.raises(ProjectNotFoundException):
        await list_project_api_keys(uow, project.id, 3)


@pytest.mark.asyncio
@pytest.mark.parametrize('scope', ['member', 'project'])
async def test_list_use_case_preserves_page_metadata(
    api_key_context, key_encryptor, scope
):
    uow, project, _, _ = api_key_context
    create = (
        create_member_api_key if scope == 'member' else create_project_api_key
    )
    listing = (
        list_member_api_keys if scope == 'member' else list_project_api_keys
    )
    for value in ('first', 'second'):
        await create(
            uow, project.id, 1, ApiKeyProvider.OPENROUTER, value, key_encryptor
        )
    page = await listing(uow, project.id, 1, PaginationDTO(limit=1))
    assert len(page.items) == 1
    assert page.pagination.limit == 1
    assert page.pagination.more is True
    assert page.pagination.cursor is not None
