from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from project.dtos.asset import AssetDTO
from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.project import ProjectDTO
from project.dtos.upload_intent import UploadIntentDTO
from project.entities.asset import AssetStatus
from project.entities.member import MemberRole, MemberStatus
from project.repositories.asset import IAssetRepository
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository
from project.repositories.resource_event import IProjectResourceEventRepository
from project.repositories.upload_intent import IUploadIntentRepository
from project.storage import IStorage
from project.tests.fixtures.mock import make_unit_of_work


@pytest.fixture
def asset_upload_dependencies():
    now = datetime.now(timezone.utc)
    project = ProjectDTO(8, 'Project', 12, now, now)
    member = MemberDTO(
        101,
        8,
        MemberRole.OWNER,
        MemberStatus.ACTIVE,
        12,
        now,
        now,
    )
    asset = AssetDTO(
        3,
        8,
        member.id,
        'projects/8/assets/original',
        'logo',
        'Existing logo',
        AssetStatus.PENDING,
        now,
        now,
    )
    project_repo = AsyncMock(spec=IProjectRepository)
    project_repo.get_project.return_value = project
    member_repo = AsyncMock(spec=IMemberRepository)
    member_repo.get_members.return_value = CursorPage(
        [member], PaginationDTO(limit=100)
    )
    asset_repo = AsyncMock(spec=IAssetRepository)
    asset_repo.get_asset.return_value = asset
    asset_repo.create_asset.return_value = replace(
        asset, file=None, status=AssetStatus.UPLOADING
    )
    asset_repo.update_asset.return_value = replace(
        asset, status=AssetStatus.UPLOADING
    )
    storage = AsyncMock(spec=IStorage)
    storage.generate_presigned_put_url.return_value = (
        'https://rustfs.test/signed-put'
    )
    upload_intent_repo = AsyncMock(spec=IUploadIntentRepository)
    upload_intent_repo.get_by_object_key_for_update.return_value = None
    resource_event_repo = AsyncMock(spec=IProjectResourceEventRepository)
    resource_event_repo.get_by_idempotency_key.return_value = None
    uow = make_unit_of_work(
        project_repo,
        member_repo,
        asset_repo=asset_repo,
    )
    uow.upload_intent_repository = upload_intent_repo
    uow.resource_event_repository = resource_event_repo
    return SimpleNamespace(
        uow=uow,
        project=project,
        member=member,
        asset=asset,
        project_repo=project_repo,
        member_repo=member_repo,
        asset_repo=asset_repo,
        storage=storage,
        upload_intent_repo=upload_intent_repo,
        resource_event_repo=resource_event_repo,
        now=now,
    )


def make_asset_upload_intent(
    dependencies,
    *,
    object_key='uploads/projects/8/assets/upload-uuid',
    final_file_key='projects/8/assets/upload-uuid',
    previous_file_key=None,
    target_status=AssetStatus.ACTIVE.value,
):
    return UploadIntentDTO(
        id=uuid4(),
        project_id=8,
        asset_id=dependencies.asset.id,
        document_id=None,
        object_key=object_key,
        final_file_key=final_file_key,
        started_by_member_id=dependencies.member.id,
        target_status=target_status,
        expires_at=dependencies.now,
        previous_file_key=previous_file_key,
        created_at=dependencies.now,
        file_extension='svg',
        content_type='image/svg+xml',
    )
