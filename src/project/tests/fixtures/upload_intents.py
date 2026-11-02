from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from project.dtos.upload_intent import UploadIntentDTO
from project.repositories.resource_event import IProjectResourceEventRepository
from project.repositories.upload_intent import IUploadIntentRepository
from project.unit_of_work import IProjectUnitOfWork


@pytest.fixture
def shared_uow():
    unit_of_work = MagicMock(spec=IProjectUnitOfWork)
    unit_of_work.upload_intent_repository = AsyncMock(
        spec=IUploadIntentRepository
    )
    unit_of_work.resource_event_repository = AsyncMock(
        spec=IProjectResourceEventRepository
    )
    unit_of_work.asset_repository = AsyncMock()
    unit_of_work.document_repository = AsyncMock()
    unit_of_work.commit = AsyncMock()
    unit_of_work.rollback = AsyncMock()
    unit_of_work.__aenter__ = AsyncMock(return_value=unit_of_work)
    unit_of_work.__aexit__ = AsyncMock(return_value=False)
    return unit_of_work


@pytest.fixture
def upload_intent_dto():
    return UploadIntentDTO(
        id=1,
        project_id=3,
        asset_id=7,
        document_id=None,
        object_key='uploads/projects/3/assets/incoming',
        final_file_key='projects/3/assets/complete',
        started_by_member_id=11,
        target_status='active',
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        previous_file_key=None,
        created_at=datetime.now(UTC),
    )
