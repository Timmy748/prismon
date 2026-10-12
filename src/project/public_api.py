from typing import Awaitable, Callable

from project.dtos.asset import AssetDTO
from project.dtos.document import DocumentDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.asset import AssetStatus
from project.entities.document import DocumentStatus
from project.entities.member import MemberRole
from project.permissions import ProjectPermission, has_permission
from project.repositories.asset import IAssetRepository
from project.repositories.document import IDocumentRepository
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository
from project.storage import IStorage
from project.use_cases.assets import get_assets
from project.use_cases.documents import get_documents


class ProjectPublicAPI:
    def __init__(
        self,
        project_repository_factory: Callable[[], Awaitable[IProjectRepository]],
        member_repository_factory: Callable[[], Awaitable[IMemberRepository]],
        document_repository_factory: Callable[
            [], Awaitable[IDocumentRepository]
        ],
        asset_repository_factory: Callable[[], Awaitable[IAssetRepository]],
        storage_factory: Callable[[], IStorage],
    ) -> None:
        self.project_repository_factory = project_repository_factory
        self.member_repository_factory = member_repository_factory
        self.document_repository_factory = document_repository_factory
        self.asset_repository_factory = asset_repository_factory
        self.storage_factory = storage_factory

    def has_permission(
        self, role: MemberRole, permission: ProjectPermission
    ) -> bool:
        return has_permission(role=role, permission=permission)

    async def get_documents(
        self,
        project_id: int,
        user_id: int,
        pagination: PaginationDTO = PaginationDTO(),
        name: str | None = None,
    ) -> CursorPage[DocumentDTO]:
        return await get_documents(
            project_repo=await self.project_repository_factory(),
            member_repo=await self.member_repository_factory(),
            document_repo=await self.document_repository_factory(),
            storage=self.storage_factory(),
            project_id=project_id,
            user_id=user_id,
            name=name,
            status=DocumentStatus.PUBLISHED,
            pagination=pagination,
        )

    async def get_assets(
        self,
        project_id: int,
        user_id: int,
        pagination: PaginationDTO = PaginationDTO(),
        asset_type: str | None = None,
    ) -> CursorPage[AssetDTO]:
        return await get_assets(
            project_repo=await self.project_repository_factory(),
            member_repo=await self.member_repository_factory(),
            asset_repo=await self.asset_repository_factory(),
            storage=self.storage_factory(),
            project_id=project_id,
            user_id=user_id,
            asset_type=asset_type,
            status=AssetStatus.ACTIVE,
            pagination=pagination,
        )
