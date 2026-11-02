from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from project.dtos.document import DocumentDTO
from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.project import ProjectDTO
from project.dtos.upload_intent import UploadIntentDTO
from project.entities.document import DocumentStatus
from project.entities.member import MemberRole, MemberStatus
from project.repositories.document import IDocumentRepository
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository
from project.repositories.resource_event import IProjectResourceEventRepository
from project.repositories.upload_intent import IUploadIntentRepository
from project.storage import IStorage
from project.tests.fixtures.mock import make_unit_of_work


@pytest.fixture
def document_upload_dependencies():
    now = datetime.now(timezone.utc)
    project = ProjectDTO(2, 'Project', 7, now, now)
    member = MemberDTO(
        11, 2, MemberRole.OWNER, MemberStatus.ACTIVE, 7, now, now
    )
    document = DocumentDTO(
        4,
        2,
        member.id,
        'projects/2/documents/original',
        'Brief',
        'Overview',
        DocumentStatus.PUBLISHED,
        now,
        now,
    )
    project_repo = AsyncMock(spec=IProjectRepository)
    project_repo.get_project.return_value = project
    member_repo = AsyncMock(spec=IMemberRepository)
    member_repo.get_members.return_value = CursorPage(
        [member], PaginationDTO(limit=100)
    )
    document_repo = AsyncMock(spec=IDocumentRepository)
    document_repo.get_document.return_value = document
    document_repo.create_document.return_value = replace(
        document, file=None, status=DocumentStatus.UPLOADING
    )
    document_repo.update_document.return_value = replace(
        document, status=DocumentStatus.UPLOADING
    )
    storage = AsyncMock(spec=IStorage)
    storage.generate_presigned_put_url.return_value = (
        'https://rustfs.test/signed-put'
    )
    upload_intent_repo = AsyncMock(spec=IUploadIntentRepository)
    resource_event_repo = AsyncMock(spec=IProjectResourceEventRepository)
    uow = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    uow.upload_intent_repository = upload_intent_repo
    uow.resource_event_repository = resource_event_repo
    return SimpleNamespace(
        uow=uow,
        project=project,
        member=member,
        document=document,
        project_repo=project_repo,
        member_repo=member_repo,
        document_repo=document_repo,
        storage=storage,
        upload_intent_repo=upload_intent_repo,
        resource_event_repo=resource_event_repo,
        now=now,
    )


def make_document_upload_intent(
    dependencies,
    *,
    object_key='uploads/projects/2/documents/upload-uuid',
    final_file_key='projects/2/documents/upload-uuid',
    previous_file_key=None,
    target_status=DocumentStatus.PUBLISHED.value,
):
    return UploadIntentDTO(
        id=uuid4(),
        project_id=2,
        asset_id=None,
        document_id=dependencies.document.id,
        object_key=object_key,
        final_file_key=final_file_key,
        started_by_member_id=dependencies.member.id,
        target_status=target_status,
        expires_at=dependencies.now,
        previous_file_key=previous_file_key,
        created_at=dependencies.now,
        file_extension='md',
        content_type='text/markdown',
    )
