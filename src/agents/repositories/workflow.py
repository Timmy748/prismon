from typing import Protocol

from sqlalchemy import literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from agents.dtos.page import CursorPage, PaginationDTO
from agents.dtos.workflow import WorkflowDTO
from agents.entities.workflow import Workflow


class IWorkflowRepository(Protocol):
    async def get_workflows(
        self, pagination: PaginationDTO = PaginationDTO()
    ) -> CursorPage[WorkflowDTO]: ...


class WorkflowRepository(IWorkflowRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_dto(self, row: Workflow) -> WorkflowDTO:
        return WorkflowDTO(
            id=row.id,
            name=row.name,
            description=row.description,
            version=row.version,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get_workflows(
        self, pagination: PaginationDTO = PaginationDTO()
    ) -> CursorPage[WorkflowDTO]:
        limit = max(1, min(pagination.limit, 100))
        stmt = select(Workflow)
        if pagination.cursor is not None:
            stmt = stmt.where(
                tuple_(Workflow.updated_at, Workflow.id)
                < tuple_(
                    literal(pagination.cursor[0]), literal(pagination.cursor[1])
                )
            )
        rows = list(
            (
                await self._session.scalars(
                    stmt.order_by(
                        Workflow.updated_at.desc(), Workflow.id.desc()
                    ).limit(limit + 1)
                )
            ).all()
        )
        more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = (
            (rows[-1].updated_at, rows[-1].id) if more and rows else None
        )
        return CursorPage(
            [self._to_dto(row) for row in rows],
            PaginationDTO(cursor=next_cursor, limit=limit, more=more),
        )
