from collections.abc import Callable

from project.dtos.asset import AssetDTO
from project.dtos.document import DocumentDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.asset import AssetStatus
from project.entities.document import DocumentStatus
from project.entities.member import MemberRole
from project.permissions import ProjectPermission, has_permission
from project.storage import IStorage
from project.unit_of_work import (
    IProjectUnitOfWork,
    create_project_unit_of_work,
)
from project.use_cases.assets import get_assets
from project.use_cases.documents import get_documents


class ProjectPublicAPI:
    def __init__(
        self,
        storage_factory: Callable[[], IStorage],
        unit_of_work_factory: Callable[[], IProjectUnitOfWork] = (
            create_project_unit_of_work
        ),
    ) -> None:
        self.storage_factory = storage_factory
        self.unit_of_work_factory = unit_of_work_factory

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
        async with self.unit_of_work_factory() as unit_of_work:
            return await get_documents(
                uow=unit_of_work,
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
        async with self.unit_of_work_factory() as unit_of_work:
            return await get_assets(
                uow=unit_of_work,
                storage=self.storage_factory(),
                project_id=project_id,
                user_id=user_id,
                asset_type=asset_type,
                status=AssetStatus.ACTIVE,
                pagination=pagination,
            )
