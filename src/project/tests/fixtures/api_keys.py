import base64
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.project import ProjectDTO
from project.entities.member import MemberRole, MemberStatus
from project.repositories.api_key import ApiKeyRepository, IApiKeyRepository
from project.security.api_key import ApiKeyEncryption
from project.tests.fixtures.mock import make_unit_of_work


@pytest.fixture
def key_encryptor():
    return ApiKeyEncryption(base64.b64encode(b'k' * 32).decode())


@pytest_asyncio.fixture
async def api_key_repo(session):
    return ApiKeyRepository(session)


@pytest_asyncio.fixture
async def api_key_context(
    unit_of_work, api_key_repo, project_repo, member_repo
):
    unit_of_work.api_key_repository = api_key_repo
    project = await project_repo.create_project('Project', 1)
    owner = await member_repo.create_member(
        project.id, 1, MemberRole.OWNER, MemberStatus.ACTIVE
    )
    member = await member_repo.create_member(
        project.id, 2, MemberRole.MEMBER, MemberStatus.ACTIVE
    )
    return unit_of_work, project, owner, member


@pytest.fixture
def api_key_use_case_context():
    unit_of_work = make_unit_of_work()
    unit_of_work.api_key_repository = AsyncMock(spec=IApiKeyRepository)
    now = datetime.now(UTC)
    project = ProjectDTO(12, 'Project', 1, now, now)
    members = {
        1: MemberDTO(
            101,
            project.id,
            MemberRole.OWNER,
            MemberStatus.ACTIVE,
            1,
            now,
            now,
        ),
        2: MemberDTO(
            102,
            project.id,
            MemberRole.MEMBER,
            MemberStatus.ACTIVE,
            2,
            now,
            now,
        ),
        3: MemberDTO(
            103,
            project.id,
            MemberRole.MEMBER,
            MemberStatus.PENDING,
            3,
            now,
            now,
        ),
    }
    unit_of_work.project_repository.get_project.return_value = project

    async def get_members(
        project_id, pagination, user_id, role=None, status=None
    ):
        member = members.get(user_id)
        items = (
            [member] if member is not None and member.status is status else []
        )
        return CursorPage(items, PaginationDTO())

    unit_of_work.member_repository.get_members.side_effect = get_members
    return unit_of_work, project, members
