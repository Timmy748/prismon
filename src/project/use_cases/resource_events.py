from typing import Any

from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.resource_event import ResourceEventDTO
from project.unit_of_work import IProjectUnitOfWork


# ruff: noqa: PLR0913, PLR0917
async def record_resource_event(
    uow: IProjectUnitOfWork,
    project_id: int,
    resource_type: str,
    resource_id: int,
    author_member_id: int,
    event_type: str,
    data: dict[str, Any],
    idempotency_key: str | None = None,
) -> ResourceEventDTO:
    return await uow.resource_event_repository.create_event(
        project_id,
        resource_type,
        resource_id,
        author_member_id,
        event_type,
        data,
        idempotency_key=idempotency_key,
    )


async def get_resource_events(
    uow: IProjectUnitOfWork,
    project_id: int,
    resource_type: str,
    resource_id: int,
    pagination: PaginationDTO,
) -> CursorPage[ResourceEventDTO]:
    return await uow.resource_event_repository.get_events(
        project_id, resource_type, resource_id, pagination
    )
