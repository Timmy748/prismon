# ruff: noqa: PLR0913, PLR0917
from typing import Protocol

from sqlalchemy import literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from project.database import get_session_factory
from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.project import ProjectDTO
from project.entities.member import Member, MemberStatus
from project.entities.project import Project


class IProjectRepository(Protocol):
    async def get_project(self, project_id: int) -> ProjectDTO | None: ...
    async def get_projects_for_member(
        self,
        user_id: int,
        name: str | None = None,
        pagination: PaginationDTO = PaginationDTO(),
    ) -> CursorPage[ProjectDTO]: ...
    async def create_project(self, name: str, owner_id: int) -> ProjectDTO: ...
    async def update_project(
        self,
        project_id: int,
        name: str | None = None,
        owner_id: int | None = None,
    ) -> ProjectDTO | None: ...
    async def delete_project(self, project_id: int) -> None: ...


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_dto(self, row: Project) -> ProjectDTO:
        return ProjectDTO(
            row.id, row.name, row.owner_id, row.created_at, row.updated_at
        )

    async def get_project(self, project_id: int) -> ProjectDTO | None:
        row = await self._session.get(Project, project_id)
        return self._to_dto(row) if row else None

    async def get_projects_for_member(
        self,
        user_id: int,
        name: str | None = None,
        pagination: PaginationDTO = PaginationDTO(),
    ) -> CursorPage[ProjectDTO]:
        limit = max(1, min(pagination.limit, 100))
        stmt = (
            select(Project)
            .join(Member, Member.project_id == Project.id)
            .where(
                Member.user_id == user_id, Member.status == MemberStatus.ACTIVE
            )
        )
        if name:
            stmt = stmt.where(Project.name.contains(name))
        if pagination.cursor is not None:
            stmt = stmt.where(
                tuple_(Project.updated_at, Project.id)
                < tuple_(
                    literal(pagination.cursor[0]), literal(pagination.cursor[1])
                )
            )
        rows = list(
            (
                await self._session.scalars(
                    stmt.order_by(
                        Project.updated_at.desc(), Project.id.desc()
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

    async def create_project(self, name: str, owner_id: int) -> ProjectDTO:
        row = Project(name=name, owner_id=owner_id)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_dto(row)

    async def update_project(
        self,
        project_id: int,
        name: str | None = None,
        owner_id: int | None = None,
    ) -> ProjectDTO | None:
        row = await self._session.get(Project, project_id)
        if row is None:
            return None
        if name is not None:
            row.name = name
        if owner_id is not None:
            row.owner_id = owner_id
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_dto(row)

    async def delete_project(self, project_id: int) -> None:
        row = await self._session.get(Project, project_id)
        if row is None:
            return
        await self._session.delete(row)
        await self._session.commit()


async def create_project_repository() -> IProjectRepository:  # pragma: no cover
    session_maker = get_session_factory()
    async with session_maker() as session:
        return ProjectRepository(session)
