from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from project.dtos.asset import AssetDTO
from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.project import ProjectDTO
from project.entities.asset import AssetStatus
from project.entities.member import MemberRole, MemberStatus


class MemoryStorage:
    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.presigned: list[tuple[str, str | None]] = []
        self.saved: list[tuple[str, bytes | None, str | None]] = []

    async def save(
        self, key: str, content: bytes | None, content_type: str | None = None
    ) -> None:
        self.saved.append((key, content, content_type))
        if content is None:
            return
        self.files[key] = content

    async def update(
        self, key: str, content: bytes, content_type: str | None = None
    ) -> None:
        del content_type
        self.files[key] = content

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.files.pop(key, None)

    async def get_presigned_url(
        self, key: str, download_filename: str | None = None
    ) -> str:
        self.presigned.append((key, download_filename))
        return (
            'https://rustfs.test/signed-download'
            if download_filename is not None
            else 'https://rustfs.test/signed-view'
        )


@pytest.fixture
def storage():
    return MemoryStorage()


@pytest.fixture
def repos():
    now = datetime.now(timezone.utc)
    project = ProjectDTO(1, 'Project', 10, now, now)
    owner = MemberDTO(1, 1, MemberRole.OWNER, MemberStatus.ACTIVE, 10, now, now)
    member = MemberDTO(
        2, 1, MemberRole.MEMBER, MemberStatus.ACTIVE, 20, now, now
    )
    project_repo = AsyncMock()
    member_repo = AsyncMock()
    document_repo = AsyncMock()
    project_repo.get_project.return_value = project

    async def get_members(project_id, **kwargs):
        return CursorPage(
            [owner if kwargs.get('user_id') == owner.user_id else member],
            PaginationDTO(),
        )

    member_repo.get_members.side_effect = get_members
    return project_repo, member_repo, document_repo


@pytest.fixture
def asset_dependencies():
    now = datetime.now(timezone.utc)
    project = Mock()
    project.id = 8
    project_repo = Mock()
    project_repo.get_project = AsyncMock(return_value=project)
    member_repo = Mock()
    member_repo.get_members = AsyncMock(
        return_value=CursorPage(
            [
                MemberDTO(
                    1, 8, MemberRole.OWNER, MemberStatus.ACTIVE, 12, now, now
                )
            ],
            PaginationDTO(),
        )
    )
    asset = AssetDTO(
        3,
        8,
        'projects/8/assets/original',
        'logo',
        None,
        AssetStatus.PENDING,
        now,
        now,
    )
    asset_repo = Mock()
    asset_repo.get_assets = AsyncMock(
        return_value=CursorPage([], PaginationDTO())
    )
    asset_repo.get_asset = AsyncMock(return_value=asset)
    asset_repo.create_asset = AsyncMock(return_value=asset)
    asset_repo.update_asset = AsyncMock(return_value=asset)
    asset_repo.delete_asset = AsyncMock()
    storage = Mock()
    storage.save = AsyncMock()
    storage.update = AsyncMock()
    storage.delete = AsyncMock()
    storage.get_presigned_url = AsyncMock(
        return_value='https://rustfs.test/signed'
    )
    return project_repo, member_repo, asset_repo, storage, asset
