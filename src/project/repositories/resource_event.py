# ruff: noqa: PLR0913, PLR0917
from typing import Any, Protocol

from sqlalchemy import literal, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from infra.logs import get_logger
from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.resource_event import ResourceEventDTO
from project.entities.resource_event import ProjectResourceEvent

logger = get_logger(__name__)


class IProjectResourceEventRepository(Protocol):
    async def create_event(
        self,
        project_id: int,
        resource_type: str,
        resource_id: int,
        author_member_id: int,
        event_type: str,
        data: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> ResourceEventDTO: ...

    async def get_event_by_idempotency_key(
        self, idempotency_key: str
    ) -> ResourceEventDTO | None: ...

    async def get_by_idempotency_key(
        self, idempotency_key: str
    ) -> ResourceEventDTO | None: ...

    async def get_events(
        self,
        project_id: int,
        resource_type: str,
        resource_id: int,
        pagination: PaginationDTO = PaginationDTO(),
    ) -> CursorPage[ResourceEventDTO]: ...


class ProjectResourceEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_dto(row: ProjectResourceEvent) -> ResourceEventDTO:
        return ResourceEventDTO(
            id=row.id,
            project_id=row.project_id,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            author_member_id=row.author_member_id,
            event_type=row.event_type,
            data=row.data,
            idempotency_key=row.idempotency_key,
            created_at=row.created_at,
        )

    async def create_event(
        self,
        project_id: int,
        resource_type: str,
        resource_id: int,
        author_member_id: int,
        event_type: str,
        data: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> ResourceEventDTO:
        if idempotency_key is not None:
            existing = await self.get_event_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing

        logger.debug(
            'Creating resource event: resource_type=%s resource_id=%s '
            'event_type=%s',
            resource_type,
            resource_id,
            event_type,
        )
        row = ProjectResourceEvent(
            project_id=project_id,
            resource_type=resource_type,
            resource_id=resource_id,
            author_member_id=author_member_id,
            event_type=event_type,
            data=data,
            idempotency_key=idempotency_key,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(row)
                await self._session.flush()
                await self._session.refresh(row)
        except IntegrityError:
            if idempotency_key is None:
                raise
            existing = await self.get_by_idempotency_key(idempotency_key)
            if existing is None:
                raise
            return existing
        return self._to_dto(row)

    async def get_event_by_idempotency_key(
        self, idempotency_key: str
    ) -> ResourceEventDTO | None:
        row = await self._session.scalar(
            select(ProjectResourceEvent).where(
                ProjectResourceEvent.idempotency_key == idempotency_key
            )
        )
        return self._to_dto(row) if row is not None else None

    async def get_by_idempotency_key(
        self, idempotency_key: str
    ) -> ResourceEventDTO | None:
        return await self.get_event_by_idempotency_key(idempotency_key)

    async def get_events(
        self,
        project_id: int,
        resource_type: str,
        resource_id: int,
        pagination: PaginationDTO = PaginationDTO(),
    ) -> CursorPage[ResourceEventDTO]:
        limit = max(1, min(pagination.limit, 100))
        stmt = select(ProjectResourceEvent).where(
            ProjectResourceEvent.project_id == project_id,
            ProjectResourceEvent.resource_type == resource_type,
            ProjectResourceEvent.resource_id == resource_id,
        )
        if pagination.cursor is not None:
            stmt = stmt.where(
                tuple_(
                    ProjectResourceEvent.created_at,
                    ProjectResourceEvent.id,
                )
                < tuple_(
                    literal(pagination.cursor[0]),
                    literal(pagination.cursor[1]),
                )
            )
        rows = list(
            (
                await self._session.scalars(
                    stmt.order_by(
                        ProjectResourceEvent.created_at.desc(),
                        ProjectResourceEvent.id.desc(),
                    ).limit(limit + 1)
                )
            ).all()
        )
        more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = (
            (rows[-1].created_at, rows[-1].id) if more and rows else None
        )
        return CursorPage(
            [self._to_dto(row) for row in rows],
            PaginationDTO(cursor=next_cursor, limit=limit, more=more),
        )
