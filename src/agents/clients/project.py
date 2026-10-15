"""Adapter exposing Project's public API to the Agents domain."""

from collections.abc import Awaitable, Callable
from typing import Protocol

from project.dtos.page import PaginationDTO
from project.entities.member import MemberRole, MemberStatus
from project.permissions import ProjectPermission
from project.public_api import ProjectPublicAPI
from project.repositories.asset import create_asset_repository
from project.repositories.document import create_document_repository
from project.repositories.member import (
    IMemberRepository,
    create_member_repository,
)
from project.repositories.project import create_project_repository
from project.storage import create_storage


class IProjectClient(Protocol):
    async def has_permission(
        self, project_id: int, user_id: int, permission: ProjectPermission
    ) -> bool: ...


class ProjectClient:
    def __init__(
        self,
        project_api: ProjectPublicAPI,
        member_repository_factory: Callable[
            [], Awaitable[IMemberRepository]
        ] = create_member_repository,
    ) -> None:
        self._project_api = project_api
        self._member_repository_factory = member_repository_factory

    async def has_permission(
        self, project_id: int, user_id: int, permission: ProjectPermission
    ) -> bool:
        member_repo = await self._member_repository_factory()
        members = await member_repo.get_members(
            project_id,
            pagination=PaginationDTO(limit=1),
            user_id=user_id,
            status=MemberStatus.ACTIVE,
        )
        if not members.items:
            return False
        return self._project_api.has_permission(
            MemberRole(members.items[0].role), permission
        )


def create_project_client() -> ProjectClient:
    api = ProjectPublicAPI(
        project_repository_factory=create_project_repository,
        member_repository_factory=create_member_repository,
        document_repository_factory=create_document_repository,
        asset_repository_factory=create_asset_repository,
        storage_factory=create_storage,
    )
    return ProjectClient(api)
