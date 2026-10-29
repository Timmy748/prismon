import base64

import pytest
import pytest_asyncio

from project.entities.member import MemberRole, MemberStatus
from project.repositories.api_key import ApiKeyRepository
from project.security.api_key import ApiKeyEncryption


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
