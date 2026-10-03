# ruff: noqa: PLR0913, PLR0917
from typing import Protocol

from sqlalchemy import literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from project.database import get_session_factory
from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.member import Member, MemberRole, MemberStatus


class IMemberRepository(Protocol):
    async def get_member(self, member_id: int) -> MemberDTO | None: ...
    async def get_members(
        self,
        project_id: int,
        pagination: PaginationDTO = PaginationDTO(),
        user_id: int | None = None,
        role: MemberRole | None = None,
        status: MemberStatus | None = None,
    ) -> CursorPage[MemberDTO]: ...
    async def create_member(
        self,
        project_id: int,
        user_id: int,
        role: MemberRole = MemberRole.MEMBER,
        status: MemberStatus = MemberStatus.PENDING,
    ) -> MemberDTO | None: ...
    async def update_member(
        self,
        member_id: int,
        role: MemberRole | None = None,
        status: MemberStatus | None = None,
    ) -> MemberDTO | None: ...
    async def delete_member(self, member_id: int) -> None: ...


class MemberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _dto(self, member: Member) -> MemberDTO:
        return MemberDTO(
            member.id,
            member.project_id,
            member.role,
            member.status,
            member.user_id,
            member.created_at,
            member.updated_at,
        )

    async def get_member(self, member_id: int) -> MemberDTO | None:
        row = await self._session.get(Member, member_id)
        return self._dto(row) if row else None

    async def get_members(
        self,
        project_id: int,
        pagination: PaginationDTO = PaginationDTO(),
        user_id: int | None = None,
        role: MemberRole | None = None,
        status: MemberStatus | None = None,
    ) -> CursorPage[MemberDTO]:
        limit = max(1, min(pagination.limit, 100))
        stmt = select(Member).where(Member.project_id == project_id)
        if pagination.cursor is not None:
            stmt = stmt.where(
                tuple_(Member.updated_at, Member.id)
                < tuple_(
                    literal(pagination.cursor[0]), literal(pagination.cursor[1])
                )
            )
        if user_id is not None:
            stmt = stmt.where(Member.user_id == user_id)
        if role is not None:
            stmt = stmt.where(Member.role == role)
        if status is not None:
            stmt = stmt.where(Member.status == status)
        rows = list(
            (
                await self._session.scalars(
                    stmt.order_by(
                        Member.updated_at.desc(), Member.id.desc()
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
            [self._dto(row) for row in rows],
            PaginationDTO(cursor=next_cursor, limit=limit, more=more),
        )

    async def create_member(
        self,
        project_id: int,
        user_id: int,
        role: MemberRole = MemberRole.MEMBER,
        status: MemberStatus = MemberStatus.PENDING,
    ) -> MemberDTO | None:
        row = Member(
            project_id=project_id, user_id=user_id, role=role, status=status
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._dto(row)

    async def update_member(
        self,
        member_id: int,
        role: MemberRole | None = None,
        status: MemberStatus | None = None,
    ) -> MemberDTO | None:
        row = await self._session.get(Member, member_id)
        if row is None:
            return None
        if role is not None:
            row.role = role
        if status is not None:
            row.status = status
        await self._session.commit()
        await self._session.refresh(row)
        return self._dto(row)

    async def delete_member(self, member_id: int) -> None:
        row = await self._session.get(Member, member_id)
        if row is None:
            return
        await self._session.delete(row)
        await self._session.commit()


async def create_member_repository() -> IMemberRepository:  # pragma: no cover
    session_maker = get_session_factory()
    async with session_maker() as session:
        return MemberRepository(session)
