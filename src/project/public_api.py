from collections.abc import Callable

from infra.logs import get_logger
from project.dtos.asset import AssetDTO
from project.dtos.document import DocumentDTO
from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.asset import AssetStatus
from project.entities.document import DocumentStatus
from project.permissions.authorization import ResourceActions
from project.permissions.dispatcher import (
    verify_resource_permission as dispatch_permission,
)
from project.security.api_key import (
    IApiKeyEncryption,
    create_api_key_encryption,
)
from project.storage import IStorage
from project.unit_of_work import (
    IProjectUnitOfWork,
    create_project_unit_of_work,
)
from project.use_cases.api_key import get_api_key
from project.use_cases.assets import get_asset_file_url, get_assets
from project.use_cases.documents import get_document_file_url, get_documents

logger = get_logger(__name__)


class ProjectPublicAPI:
    def __init__(
        self,
        storage_factory: Callable[[], IStorage],
        unit_of_work_factory: Callable[[], IProjectUnitOfWork] = (
            create_project_unit_of_work
        ),
        encryption_factory: Callable[
            [], IApiKeyEncryption
        ] = create_api_key_encryption,
    ) -> None:
        self.storage_factory = storage_factory
        self.unit_of_work_factory = unit_of_work_factory
        self.encryption_factory = encryption_factory

    def verify_resource_permission(
        self,
        member: MemberDTO,
        resource: object,
        action: ResourceActions,
        **context: object,
    ) -> bool:
        return dispatch_permission(member, resource, action, **context)

    async def get_document_embedding_source(
        self, document_id: int
    ) -> DocumentDTO | None:
        async with self.unit_of_work_factory() as unit_of_work:
            return await unit_of_work.document_repository.get_document(
                document_id
            )

    async def get_asset_embedding_source(
        self, asset_id: int
    ) -> AssetDTO | None:
        async with self.unit_of_work_factory() as unit_of_work:
            return await unit_of_work.asset_repository.get_asset(asset_id)

    async def get_document_file_url(
        self,
        project_id: int,
        user_id: int,
        document_id: int,
        *,
        internal: bool = False,
    ) -> str:
        """Return an authorized, short-lived URL for a document file."""
        async with self.unit_of_work_factory() as unit_of_work:
            return await get_document_file_url(
                uow=unit_of_work,
                storage=self.storage_factory(),
                project_id=project_id,
                user_id=user_id,
                document_id=document_id,
                **({'internal': True} if internal else {}),
            )

    async def get_asset_file_url(
        self,
        project_id: int,
        user_id: int,
        asset_id: int,
        *,
        internal: bool = False,
    ) -> str:
        """Return an authorized, short-lived URL for an asset file."""
        async with self.unit_of_work_factory() as unit_of_work:
            return await get_asset_file_url(
                uow=unit_of_work,
                storage=self.storage_factory(),
                project_id=project_id,
                user_id=user_id,
                asset_id=asset_id,
                **({'internal': True} if internal else {}),
            )

    async def get_api_key(
        self, project_id: int, user_id: int, api_key_id: int
    ) -> str:
        logger.debug(
            'Public API key retrieval started: '
            'project_id=%s user_id=%s api_key_id=%s',
            project_id,
            user_id,
            api_key_id,
        )
        async with self.unit_of_work_factory() as unit_of_work:
            api_key = await get_api_key(
                uow=unit_of_work,
                project_id=project_id,
                user_id=user_id,
                api_key_id=api_key_id,
                encryptor=self.encryption_factory(),
            )
        logger.debug(
            'Public API key retrieval completed: project_id=%s api_key_id=%s',
            project_id,
            api_key_id,
        )
        return api_key

    async def get_documents(
        self,
        project_id: int,
        user_id: int,
        pagination: PaginationDTO = PaginationDTO(),
        name: str | None = None,
    ) -> CursorPage[DocumentDTO]:
        async with self.unit_of_work_factory() as unit_of_work:
            page = await get_documents(
                uow=unit_of_work,
                storage=self.storage_factory(),
                project_id=project_id,
                user_id=user_id,
                name=name,
                status=DocumentStatus.PUBLISHED,
                pagination=pagination,
            )
        logger.debug(
            'Public document listing completed: project_id=%s count=%s',
            project_id,
            len(page.items),
        )
        return page

    async def get_assets(
        self,
        project_id: int,
        user_id: int,
        pagination: PaginationDTO = PaginationDTO(),
        asset_type: str | None = None,
    ) -> CursorPage[AssetDTO]:
        async with self.unit_of_work_factory() as unit_of_work:
            page = await get_assets(
                uow=unit_of_work,
                storage=self.storage_factory(),
                project_id=project_id,
                user_id=user_id,
                asset_type=asset_type,
                status=AssetStatus.ACTIVE,
                pagination=pagination,
            )
        logger.debug(
            'Public asset listing completed: project_id=%s count=%s',
            project_id,
            len(page.items),
        )
        return page
