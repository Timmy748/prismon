# ruff: noqa: F811
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from project.dtos.asset import (
    ApproveAssetDTO,
    AssetDTO,
    CreateAssetDTO,
    StartAssetUploadDTO,
    UpdateAssetDTO,
)
from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.resource_event import ResourceEventDTO
from project.entities.asset import AssetStatus
from project.entities.member import MemberRole, MemberStatus
from project.exceptions import (
    AssetNotFoundException,
    InsufficientProjectPermissionException,
    InvalidAssetStateException,
    ProjectNotFoundException,
)
from project.tests.fixtures.asset_uploads import (
    asset_upload_dependencies,  # noqa: F401,F811
    make_asset_upload_intent,
)
from project.tests.fixtures.mock import make_unit_of_work
from project.use_cases.assets import (
    add_asset,
    complete_asset_upload,
    delete_asset,
    download_asset,
    get_asset_events,
    get_asset_file_url,
    get_assets,
    review_asset,
    start_asset_replacement,
    start_asset_upload,
    update_asset,
)


@pytest.mark.asyncio
async def test_get_assets_checks_read_permission_and_forwards_filters(
    asset_dependencies,
):
    project_repo, member_repo, asset_repo, storage, _ = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    page = await get_assets(
        uow,
        storage,
        8,
        12,
        PaginationDTO(limit=5),
        'logo',
        AssetStatus.ACTIVE,
    )
    assert page == asset_repo.get_assets.return_value
    asset_repo.get_assets.assert_awaited_once_with(
        8, PaginationDTO(limit=5), 'logo', AssetStatus.ACTIVE
    )
    member_repo.get_members.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_asset_file_url_returns_signed_url_after_read_authorization(
    asset_dependencies,
):
    project_repo, member_repo, asset_repo, storage, asset = asset_dependencies
    asset = replace(asset, content_type='image/svg+xml')
    asset_repo.get_asset.return_value = asset
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)

    result = await get_asset_file_url(uow, storage, 8, 12, asset.id)

    assert result == 'https://rustfs.test/signed'
    storage.get_presigned_url.assert_awaited_once_with(
        asset.file,
        download_filename=f'asset-{asset.id}',
        disposition='inline',
        content_type='image/svg+xml',
    )


@pytest.mark.asyncio
async def test_download_asset_requests_attachment_url_with_asset_name(
    asset_dependencies,
):
    project_repo, member_repo, asset_repo, storage, asset = asset_dependencies
    asset = replace(
        asset,
        name='texto',
        file_extension='md',
        content_type='text/markdown',
    )
    asset_repo.get_asset.return_value = asset
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)

    result = await download_asset(uow, storage, 8, 12, asset.id)

    assert result == 'https://rustfs.test/signed'
    storage.get_presigned_url.assert_awaited_once_with(
        asset.file,
        download_filename='texto.md',
        content_type='text/markdown',
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', [get_asset_file_url, download_asset])
async def test_asset_download_rejects_asset_without_file(
    asset_upload_dependencies, operation
):
    deps = asset_upload_dependencies
    deps.asset_repo.get_asset.return_value = replace(deps.asset, file=None)

    with pytest.raises(InvalidAssetStateException):
        await operation(deps.uow, deps.storage, 8, 12, deps.asset.id)

    deps.storage.get_presigned_url.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('asset_state', ['missing', 'foreign_project'])
async def test_asset_file_url_rejects_missing_or_foreign_asset(
    asset_dependencies, asset_state
):
    project_repo, member_repo, asset_repo, storage, asset = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    asset_repo.get_asset.return_value = (
        None
        if asset_state == 'missing'
        else AssetDTO(
            asset.id,
            99,
            asset.created_by_member_id,
            asset.file,
            asset.type,
            asset.description,
            asset.status,
            asset.created_at,
            asset.updated_at,
        )
    )

    with pytest.raises(AssetNotFoundException):
        await get_asset_file_url(uow, storage, 8, 12, asset.id)

    storage.get_presigned_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_asset_access_rejects_missing_project(asset_dependencies):
    project_repo, member_repo, asset_repo, storage, _ = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    project_repo.get_project.return_value = None
    with pytest.raises(ProjectNotFoundException):
        await get_assets(uow, storage, 8, 12)
    member_repo.get_members.assert_not_awaited()


@pytest.mark.asyncio
async def test_asset_access_rejects_non_member(asset_dependencies):
    project_repo, member_repo, asset_repo, storage, _ = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    member_repo.get_members.return_value = CursorPage([], PaginationDTO())
    with pytest.raises(ProjectNotFoundException):
        await get_assets(uow, storage, 8, 12)


@pytest.mark.asyncio
async def test_asset_access_rejects_missing_permission(asset_dependencies):
    project_repo, member_repo, asset_repo, storage, _ = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    member_repo.get_members.return_value.items[0] = MemberDTO(
        1,
        8,
        MemberRole.COLLABORATOR,
        MemberStatus.ACTIVE,
        12,
        datetime.now(timezone.utc),
        datetime.now(timezone.utc),
    )
    with pytest.raises(InsufficientProjectPermissionException):
        await add_asset(
            uow,
            storage,
            8,
            12,
            CreateAssetDTO('', '', 'logo', '', ''),
            b'bytes',
        )
    storage.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_asset_owner_is_active_and_stores_content(asset_dependencies):
    project_repo, member_repo, asset_repo, storage, asset = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    result = await add_asset(
        uow,
        storage,
        8,
        12,
        CreateAssetDTO('', '', 'logo', 'ignored name', 'description'),
        b'bytes',
    )
    assert result == asset
    key = storage.save.call_args.args[0]
    assert key.startswith('projects/8/assets/')
    storage.save.assert_awaited_once_with(key, b'bytes', None)
    asset_repo.create_asset.assert_awaited_once_with(
        project_id=8,
        file=key,
        asset_type='logo',
        created_by_member_id=1,
        description='description',
        status=AssetStatus.ACTIVE,
        name='ignored name',
        file_extension=None,
        content_type=None,
    )


@pytest.mark.asyncio
async def test_add_asset_regular_member_is_pending_and_empty_description_none(
    asset_dependencies,
):
    project_repo, member_repo, asset_repo, storage, _ = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    member_repo.get_members.return_value.items[0] = MemberDTO(
        1,
        8,
        MemberRole.MEMBER,
        MemberStatus.ACTIVE,
        12,
        datetime.now(timezone.utc),
        datetime.now(timezone.utc),
    )
    await add_asset(
        uow,
        storage,
        8,
        12,
        CreateAssetDTO('', '', 'photo', '', ''),
        b'x',
    )
    assert (
        asset_repo.create_asset.call_args.kwargs['status']
        is AssetStatus.PENDING
    )
    assert asset_repo.create_asset.call_args.kwargs['description'] is None


@pytest.mark.asyncio
async def test_add_asset_cleans_storage_if_repository_fails(asset_dependencies):
    project_repo, member_repo, asset_repo, storage, _ = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    asset_repo.create_asset.side_effect = RuntimeError
    with pytest.raises(RuntimeError):
        await add_asset(
            uow,
            storage,
            8,
            12,
            CreateAssetDTO('', '', 'photo', '', ''),
            b'x',
        )
    storage.delete.assert_awaited_once_with(storage.save.await_args.args[0])


@pytest.mark.asyncio
async def test_update_asset_replaces_storage_and_updates_metadata(
    asset_dependencies,
):
    project_repo, member_repo, asset_repo, storage, asset = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    result = await update_asset(
        uow,
        storage,
        8,
        12,
        3,
        UpdateAssetDTO(name='New icon', type='icon', description='new'),
        b'new bytes',
        'image/png',
    )
    assert result == asset
    key = storage.save.await_args.args[0]
    assert key.startswith('projects/8/assets/')
    storage.save.assert_awaited_once_with(key, b'new bytes', 'image/png')
    asset_repo.update_asset.assert_awaited_once_with(
        3,
        file=key,
        asset_type='icon',
        name='New icon',
        description='new',
        file_extension='png',
        content_type='image/png',
    )
    assert asset_repo.update_asset.await_args.kwargs['name'] == 'New icon'
    metadata_event = next(
        call
        for call in uow.resource_event_repository.create_event.await_args_list
        if call.args[4] == 'metadata_changed'
    )
    assert metadata_event.args[5]['changes']['name'] == {
        'old': '',
        'new': 'New icon',
    }
    storage.delete.assert_awaited_once_with(asset.file)


@pytest.mark.asyncio
async def test_update_asset_without_content_leaves_storage_unchanged(
    asset_dependencies,
):
    project_repo, member_repo, asset_repo, storage, _ = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    await update_asset(
        uow,
        storage,
        8,
        12,
        3,
        UpdateAssetDTO(type='icon'),
    )
    storage.save.assert_not_awaited()
    storage.delete.assert_not_awaited()
    asset_repo.update_asset.assert_awaited_once_with(
        3, file=None, asset_type='icon', description=None
    )


@pytest.mark.asyncio
async def test_update_asset_rejects_uploading_asset(asset_upload_dependencies):
    deps = asset_upload_dependencies
    deps.asset_repo.get_asset.return_value = replace(
        deps.asset, status=AssetStatus.UPLOADING
    )

    with pytest.raises(InvalidAssetStateException):
        await update_asset(
            deps.uow, deps.storage, 8, 12, deps.asset.id, UpdateAssetDTO()
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'missing_or_wrong_project', ['missing', 'wrong_project']
)
async def test_update_asset_rejects_missing_or_foreign_asset(
    asset_dependencies, missing_or_wrong_project
):
    project_repo, member_repo, asset_repo, storage, asset = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    asset_repo.get_asset.return_value = (
        None
        if missing_or_wrong_project == 'missing'
        else AssetDTO(
            3,
            99,
            asset.created_by_member_id,
            asset.file,
            asset.type,
            asset.description,
            asset.status,
            asset.created_at,
            asset.updated_at,
        )
    )
    with pytest.raises(AssetNotFoundException):
        await update_asset(
            uow,
            storage,
            8,
            12,
            3,
            UpdateAssetDTO(),
        )


@pytest.mark.asyncio
async def test_update_asset_cleans_new_file_when_repository_returns_none(
    asset_dependencies,
):
    project_repo, member_repo, asset_repo, storage, _ = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    asset_repo.update_asset.return_value = None
    with pytest.raises(AssetNotFoundException):
        await update_asset(
            uow,
            storage,
            8,
            12,
            3,
            UpdateAssetDTO(),
            b'new',
        )
    storage.delete.assert_awaited_once_with(storage.save.await_args.args[0])


@pytest.mark.asyncio
async def test_delete_asset_deletes_record_and_file(asset_dependencies):
    project_repo, member_repo, asset_repo, storage, asset = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    await delete_asset(uow, storage, 8, 12, 3)
    asset_repo.delete_asset.assert_awaited_once_with(3)
    storage.delete.assert_awaited_once_with(asset.file)


@pytest.mark.asyncio
async def test_delete_asset_rejects_uploading_asset(asset_upload_dependencies):
    deps = asset_upload_dependencies
    deps.asset_repo.get_asset.return_value = replace(
        deps.asset, status=AssetStatus.UPLOADING
    )

    with pytest.raises(InvalidAssetStateException):
        await delete_asset(deps.uow, deps.storage, 8, 12, deps.asset.id)

    deps.asset_repo.delete_asset.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'missing_or_wrong_project', ['missing', 'wrong_project']
)
async def test_delete_asset_rejects_missing_or_foreign_asset(
    asset_dependencies, missing_or_wrong_project
):
    project_repo, member_repo, asset_repo, storage, asset = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    asset_repo.get_asset.return_value = (
        None
        if missing_or_wrong_project == 'missing'
        else AssetDTO(
            3,
            99,
            asset.created_by_member_id,
            asset.file,
            asset.type,
            asset.description,
            asset.status,
            asset.created_at,
            asset.updated_at,
        )
    )
    with pytest.raises(AssetNotFoundException):
        await delete_asset(uow, storage, 8, 12, 3)
    asset_repo.delete_asset.assert_not_awaited()
    storage.delete.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('accept', 'expected'),
    [
        (True, AssetStatus.ACTIVE),
        (False, AssetStatus.ARCHIVED),
    ],
)
async def test_review_asset_changes_pending_status(
    asset_dependencies, accept, expected
):
    project_repo, member_repo, asset_repo, _, _ = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    await review_asset(uow, 8, 12, 3, ApproveAssetDTO(accept))
    asset_repo.update_asset.assert_awaited_once_with(3, status=expected)


@pytest.mark.asyncio
async def test_review_asset_rejects_non_pending_state(asset_dependencies):
    project_repo, member_repo, asset_repo, _, asset = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    asset_repo.get_asset.return_value = AssetDTO(
        asset.id,
        asset.project_id,
        asset.created_by_member_id,
        asset.file,
        asset.type,
        asset.description,
        AssetStatus.ACTIVE,
        asset.created_at,
        asset.updated_at,
    )
    with pytest.raises(InvalidAssetStateException):
        await review_asset(
            uow,
            8,
            12,
            3,
            ApproveAssetDTO(True),
        )
    asset_repo.update_asset.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'missing_or_wrong_project', ['missing', 'wrong_project']
)
async def test_review_asset_rejects_missing_or_foreign_asset(
    asset_dependencies, missing_or_wrong_project
):
    project_repo, member_repo, asset_repo, _, asset = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    asset_repo.get_asset.return_value = (
        None
        if missing_or_wrong_project == 'missing'
        else AssetDTO(
            3,
            99,
            asset.created_by_member_id,
            asset.file,
            asset.type,
            asset.description,
            asset.status,
            asset.created_at,
            asset.updated_at,
        )
    )
    with pytest.raises(AssetNotFoundException):
        await review_asset(
            uow,
            8,
            12,
            3,
            ApproveAssetDTO(True),
        )
    asset_repo.update_asset.assert_not_awaited()


@pytest.mark.asyncio
async def test_review_asset_raises_not_found_if_update_disappears(
    asset_dependencies,
):
    project_repo, member_repo, asset_repo, _, _ = asset_dependencies
    uow = make_unit_of_work(project_repo, member_repo, asset_repo=asset_repo)
    asset_repo.update_asset.return_value = None
    with pytest.raises(AssetNotFoundException):
        await review_asset(
            uow,
            8,
            12,
            3,
            ApproveAssetDTO(True),
        )


@pytest.mark.asyncio
async def test_start_asset_upload_creates_intent_and_auditable_events(
    asset_upload_dependencies,
):
    deps = asset_upload_dependencies

    result = await start_asset_upload(
        deps.uow,
        deps.storage,
        8,
        12,
        StartAssetUploadDTO(
            type='logo',
            name='Logo',
            description='cover',
            content_type='image/png',
            original_filename='logo.svg',
        ),
    )

    assert result.asset.file is None
    assert result.asset.status is AssetStatus.UPLOADING
    assert result.asset.created_by_member_id == deps.member.id
    assert result.upload_url == 'https://rustfs.test/signed-put'
    assert result.required_headers == {'Content-Type': 'image/png'}
    deps.asset_repo.create_asset.assert_awaited_once_with(
        project_id=8,
        file=None,
        asset_type='logo',
        created_by_member_id=deps.member.id,
        name='Logo',
        description='cover',
        status=AssetStatus.UPLOADING,
    )
    deps.upload_intent_repo.create_upload_intent.assert_awaited_once()
    intent_args = deps.upload_intent_repo.create_upload_intent.await_args
    assert intent_args.kwargs['file_extension'] == 'svg'
    assert intent_args.kwargs['content_type'] == 'image/png'
    event_types = [
        call.args[4]
        for call in deps.resource_event_repo.create_event.await_args_list
    ]
    assert event_types == ['resource_created', 'upload_started']
    deps.uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_asset_upload_denies_permission_before_presigning(
    asset_upload_dependencies,
):
    deps = asset_upload_dependencies
    deps.member_repo.get_members.return_value.items[0] = replace(
        deps.member, role=MemberRole.COLLABORATOR
    )

    with pytest.raises(InsufficientProjectPermissionException):
        await start_asset_upload(
            deps.uow,
            deps.storage,
            8,
            12,
            StartAssetUploadDTO(type='logo', name='Logo'),
        )

    deps.storage.generate_presigned_put_url.assert_not_awaited()
    deps.asset_repo.create_asset.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_asset_replacement_preserves_existing_file_and_status(
    asset_upload_dependencies,
):
    deps = asset_upload_dependencies

    result = await start_asset_replacement(
        deps.uow, deps.storage, 8, 12, deps.asset.id, 'image/png'
    )

    assert result.asset.status is AssetStatus.UPLOADING
    deps.upload_intent_repo.create_upload_intent.assert_awaited_once()
    kwargs = deps.upload_intent_repo.create_upload_intent.await_args.kwargs
    assert kwargs['previous_file_key'] == deps.asset.file
    assert kwargs['target_status'] == deps.asset.status.value
    deps.storage.generate_presigned_put_url.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_asset_replacement_rejects_asset_already_uploading(
    asset_upload_dependencies,
):
    deps = asset_upload_dependencies
    deps.asset_repo.get_asset.return_value = replace(
        deps.asset, status=AssetStatus.UPLOADING
    )

    with pytest.raises(InvalidAssetStateException):
        await start_asset_replacement(
            deps.uow, deps.storage, 8, 12, deps.asset.id
        )

    deps.storage.generate_presigned_put_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_asset_replacement_rejects_missing_asset(
    asset_upload_dependencies,
):
    deps = asset_upload_dependencies
    deps.asset_repo.get_asset.return_value = None

    with pytest.raises(AssetNotFoundException):
        await start_asset_replacement(deps.uow, deps.storage, 8, 12, 404)


@pytest.mark.asyncio
async def test_start_asset_replacement_rejects_failed_record_update(
    asset_upload_dependencies,
):
    deps = asset_upload_dependencies
    deps.asset_repo.update_asset.return_value = None

    with pytest.raises(AssetNotFoundException):
        await start_asset_replacement(
            deps.uow, deps.storage, 8, 12, deps.asset.id
        )


@pytest.mark.asyncio
async def test_complete_asset_upload_promotes_staging_object_and_removes_intent(
    asset_upload_dependencies,
):
    deps = asset_upload_dependencies
    intent = make_asset_upload_intent(deps)
    deps.resource_event_repo.get_by_idempotency_key.return_value = None
    deps.upload_intent_repo.get_by_object_key_for_update.return_value = intent
    deps.asset_repo.get_asset.return_value = replace(
        deps.asset, file=None, status=AssetStatus.UPLOADING
    )
    deps.asset_repo.update_asset.return_value = replace(
        deps.asset, file=intent.final_file_key, status=AssetStatus.ACTIVE
    )

    result = await complete_asset_upload(deps.uow, intent.object_key)

    assert result.asset_id == deps.asset.id
    assert result.already_completed is False
    deps.asset_repo.update_asset.assert_awaited_once_with(
        deps.asset.id,
        file=intent.final_file_key,
        status=AssetStatus.ACTIVE,
        file_extension=intent.file_extension,
        content_type=intent.content_type,
    )
    deps.upload_intent_repo.delete_upload_intent.assert_awaited_once_with(
        intent.id
    )
    deps.resource_event_repo.create_event.assert_awaited_once()
    assert (
        deps.resource_event_repo.create_event.await_args.kwargs[
            'idempotency_key'
        ]
        == intent.object_key
    )
    deps.uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_complete_asset_upload_is_idempotent_after_event_exists(
    asset_upload_dependencies,
):
    deps = asset_upload_dependencies
    intent = make_asset_upload_intent(deps, previous_file_key='old-file')
    deps.resource_event_repo.get_by_idempotency_key.return_value = (
        ResourceEventDTO(
            1,
            8,
            'asset',
            deps.asset.id,
            deps.member.id,
            'file_changed',
            {'obsolete_file_key': 'old-file'},
            intent.object_key,
            deps.now,
        )
    )

    result = await complete_asset_upload(deps.uow, intent.object_key)

    assert result.already_completed is True
    assert result.obsolete_file_key == 'old-file'
    deps.upload_intent_repo.get_by_object_key_for_update.assert_awaited_once_with(
        intent.object_key
    )
    deps.uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_asset_upload_ignores_unknown_staging_key(
    asset_upload_dependencies,
):
    deps = asset_upload_dependencies
    deps.resource_event_repo.get_by_idempotency_key.return_value = None
    deps.upload_intent_repo.get_by_object_key_for_update.return_value = None

    result = await complete_asset_upload(
        deps.uow, 'uploads/projects/8/assets/unknown'
    )

    assert result.ignored is True
    assert result.asset_id is None


@pytest.mark.asyncio
async def test_complete_upload_rechecks_event_after_intent_disappears(
    asset_upload_dependencies,
):
    deps = asset_upload_dependencies
    intent = make_asset_upload_intent(deps)
    existing_event = ResourceEventDTO(
        1,
        8,
        'asset',
        deps.asset.id,
        deps.member.id,
        'upload_failed',
        {},
        intent.object_key,
        deps.now,
    )
    deps.upload_intent_repo.get_by_object_key_for_update.return_value = None
    deps.resource_event_repo.get_by_idempotency_key.return_value = (
        existing_event
    )

    result = await complete_asset_upload(deps.uow, intent.object_key)

    assert result.already_completed is True
    assert result.asset_id == deps.asset.id
    assert result.obsolete_file_key is None


@pytest.mark.asyncio
async def test_complete_asset_upload_rejects_invalid_object_prefix(
    asset_upload_dependencies,
):
    deps = asset_upload_dependencies
    intent = make_asset_upload_intent(deps, object_key='wrong-prefix/object')
    deps.resource_event_repo.get_by_idempotency_key.return_value = None
    deps.upload_intent_repo.get_by_object_key_for_update.return_value = intent
    deps.asset_repo.get_asset.return_value = replace(
        deps.asset, file=None, status=AssetStatus.UPLOADING
    )

    with pytest.raises(InvalidAssetStateException):
        await complete_asset_upload(deps.uow, intent.object_key)


@pytest.mark.asyncio
async def test_complete_upload_rejects_missing_asset(asset_upload_dependencies):
    deps = asset_upload_dependencies
    intent = make_asset_upload_intent(deps)
    deps.resource_event_repo.get_by_idempotency_key.return_value = None
    deps.upload_intent_repo.get_by_object_key_for_update.return_value = intent
    deps.asset_repo.get_asset.return_value = None

    with pytest.raises(AssetNotFoundException):
        await complete_asset_upload(deps.uow, intent.object_key)


@pytest.mark.asyncio
async def test_complete_upload_rejects_asset_not_in_uploading_state(
    asset_upload_dependencies,
):
    deps = asset_upload_dependencies
    intent = make_asset_upload_intent(deps)
    deps.resource_event_repo.get_by_idempotency_key.return_value = None
    deps.upload_intent_repo.get_by_object_key_for_update.return_value = intent
    deps.asset_repo.get_asset.return_value = deps.asset

    with pytest.raises(InvalidAssetStateException):
        await complete_asset_upload(deps.uow, intent.object_key)


@pytest.mark.asyncio
async def test_complete_upload_raises_when_asset_update_returns_none(
    asset_upload_dependencies,
):
    deps = asset_upload_dependencies
    intent = make_asset_upload_intent(deps)
    deps.resource_event_repo.get_by_idempotency_key.return_value = None
    deps.upload_intent_repo.get_by_object_key_for_update.return_value = intent
    deps.asset_repo.get_asset.return_value = replace(
        deps.asset, status=AssetStatus.UPLOADING
    )
    deps.asset_repo.update_asset.return_value = None

    with pytest.raises(AssetNotFoundException):
        await complete_asset_upload(deps.uow, intent.object_key)


@pytest.mark.asyncio
async def test_get_asset_events_returns_history_even_when_asset_was_deleted(
    asset_upload_dependencies,
):
    deps = asset_upload_dependencies
    event_page = CursorPage([], PaginationDTO(limit=20))
    deps.resource_event_repo.get_events.return_value = event_page

    result = await get_asset_events(
        deps.uow, 8, 12, 404, PaginationDTO(limit=20)
    )

    assert result is event_page
    deps.resource_event_repo.get_events.assert_awaited_once_with(
        8, 'asset', 404, PaginationDTO(limit=20)
    )
