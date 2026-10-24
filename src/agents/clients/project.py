"""Adapter exposing Project's public API to the Agents domain."""

from collections.abc import Callable
from typing import Protocol

from core.logs import get_logger
from project.dtos.page import PaginationDTO
from project.entities.member import MemberRole, MemberStatus
from project.permissions import ProjectPermission
from project.public_api import ProjectPublicAPI
from project.storage import create_storage
from project.unit_of_work import (
    IProjectUnitOfWork,
    create_project_unit_of_work,
)

logger = get_logger(__name__)


class IProjectClient(Protocol):
    async def has_permission(
        self, project_id: int, user_id: int, permission: ProjectPermission
    ) -> bool: ...


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


def create_project_client() -> ProjectClient:
    api = ProjectPublicAPI(
        unit_of_work_factory=create_project_unit_of_work,
        storage_factory=create_storage,
    )
    return ProjectClient(api)
