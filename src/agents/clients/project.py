"""Adapter exposing Project's public API to the Agents domain."""

from collections.abc import Callable
from typing import Protocol

from agents.dtos.project_resource import EmbeddingSourceDTO
from agents.exceptions import ApiKeyNotFoundException
from infra.logs import get_logger
from project.dtos.page import PaginationDTO
from project.entities.member import MemberRole, MemberStatus
from project.exceptions import (
    ApiKeyNotFoundException as ProjectApiKeyNotFoundException,
)
from project.permissions import ProjectPermission
from project.public_api import ProjectPublicAPI
from project.storage import create_storage
from project.unit_of_work import (
    IProjectUnitOfWork,
    create_project_unit_of_work,
)

logger = get_logger(__name__)


class IProjectClient(Protocol):
    async def get_document_embedding_source(
        self, document_id: int
    ) -> EmbeddingSourceDTO | None: ...

    async def get_document_file_url(
        self,
        project_id: int,
        user_id: int,
        document_id: int,
        *,
        internal: bool = False,
    ) -> str: ...

    async def get_asset_embedding_source(
        self, asset_id: int
    ) -> EmbeddingSourceDTO | None: ...

    async def get_asset_file_url(
        self,
        project_id: int,
        user_id: int,
        asset_id: int,
        *,
        internal: bool = False,
    ) -> str: ...

    async def has_permission(
        self, project_id: int, user_id: int, permission: ProjectPermission
    ) -> bool: ...

    async def get_api_key(
        self, project_id: int, user_id: int, api_key_id: int
    ) -> str: ...


class ProjectClient:
    def __init__(
        self,
        project_api: ProjectPublicAPI,
        unit_of_work_factory: Callable[[], IProjectUnitOfWork] = (
            create_project_unit_of_work
        ),
    ) -> None:
        self._project_api = project_api
        self._unit_of_work_factory = unit_of_work_factory

    async def get_document_embedding_source(
        self, document_id: int
    ) -> EmbeddingSourceDTO | None:
        document = await self._project_api.get_document_embedding_source(
            document_id
        )
        if document is None:
            return None
        return EmbeddingSourceDTO(
            document.name,
            document.description,
            document.project_id,
            document.status.value,
        )

    async def get_document_file_url(
        self,
        project_id: int,
        user_id: int,
        document_id: int,
        *,
        internal: bool = False,
    ) -> str:
        return await self._project_api.get_document_file_url(
            project_id,
            user_id,
            document_id,
            **({'internal': True} if internal else {}),
        )

    async def get_asset_embedding_source(
        self, asset_id: int
    ) -> EmbeddingSourceDTO | None:
        asset = await self._project_api.get_asset_embedding_source(asset_id)
        if asset is None:
            return None
        return EmbeddingSourceDTO(
            asset.name,
            asset.description,
            asset.project_id,
            asset.status.value,
        )

    async def get_asset_file_url(
        self,
        project_id: int,
        user_id: int,
        asset_id: int,
        *,
        internal: bool = False,
    ) -> str:
        return await self._project_api.get_asset_file_url(
            project_id,
            user_id,
            asset_id,
            **({'internal': True} if internal else {}),
        )

    async def has_permission(
        self, project_id: int, user_id: int, permission: ProjectPermission
    ) -> bool:
        async with self._unit_of_work_factory() as uow:
            members = await uow.member_repository.get_members(
                project_id,
                pagination=PaginationDTO(limit=1),
                user_id=user_id,
                status=MemberStatus.ACTIVE,
            )
        if not members.items:
            logger.debug(
                'Project permission denied: project_id=%d user_id=%d '
                'permission=%s',
                project_id,
                user_id,
                getattr(permission, 'value', permission),
            )
            return False
        allowed = self._project_api.has_permission(
            MemberRole(members.items[0].role), permission
        )
        logger.debug(
            'Project permission checked: project_id=%d user_id=%d '
            'permission=%s allowed=%s',
            project_id,
            user_id,
            getattr(permission, 'value', permission),
            allowed,
        )
        return allowed

    async def get_api_key(
        self, project_id: int, user_id: int, api_key_id: int
    ) -> str:
        try:
            return await self._project_api.get_api_key(
                project_id, user_id, api_key_id
            )
        except ProjectApiKeyNotFoundException as error:
            raise ApiKeyNotFoundException(api_key_id) from error


def create_project_client() -> ProjectClient:
    api = ProjectPublicAPI(
        unit_of_work_factory=create_project_unit_of_work,
        storage_factory=create_storage,
    )
    return ProjectClient(api)
