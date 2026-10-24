from typing import Protocol

from sqlalchemy import literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from agents.dtos.chat import ChatDTO
from agents.dtos.page import CursorPage, PaginationDTO
from agents.entities.chat import Chat
from agents.exceptions import ChatNotFoundException
from core.logs import get_logger

logger = get_logger(__name__)


class IChatRepository(Protocol):
    async def get_chat(self, chat_id: int) -> ChatDTO | None: ...

    async def create_chat(
        self, title: str, project_id: int, owner: int
    ) -> ChatDTO: ...

    async def delete_chat(self, chat_id: int) -> None: ...

    async def get_chats_by_project(
        self,
        project_id: int,
        title: str | None,
        owner_id: int | None,
        pagination: PaginationDTO,
    ) -> CursorPage[ChatDTO]: ...

    async def update_chat_title(self, chat_id: int, title: str) -> ChatDTO: ...


class ChatRepository(IChatRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_dto(self, row: Chat) -> ChatDTO:
        return ChatDTO(
            id=row.id,
            title=row.title,
            project_id=row.project_id,
            owner=row.owner,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get_chat(self, chat_id: int) -> ChatDTO | None:
        row = await self._session.get(Chat, chat_id)
        logger.debug(
            'Loaded chat: chat_id=%d found=%s', chat_id, row is not None
        )
        return self._to_dto(row) if row is not None else None

    async def create_chat(
        self, title: str, project_id: int, owner: int
    ) -> ChatDTO:
        row = Chat(title=title, project_id=project_id, owner=owner)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        logger.info(
            'Created chat: chat_id=%d project_id=%d', row.id, project_id
        )
        return self._to_dto(row)

    async def delete_chat(self, chat_id: int) -> None:
        row = await self._session.get(Chat, chat_id)
        if row is None:
            logger.warning('Cannot delete missing chat: chat_id=%d', chat_id)
            raise ChatNotFoundException(chat_id)
        await self._session.delete(row)
        await self._session.flush()
        logger.info('Deleted chat: chat_id=%d', chat_id)

    async def get_chats_by_project(
        self,
        project_id: int,
        title: str | None,
        owner_id: int | None,
        pagination: PaginationDTO,
    ) -> CursorPage[ChatDTO]:
        limit = max(1, min(pagination.limit, 100))
        stmt = select(Chat).where(Chat.project_id == project_id)
        if title:
            stmt = stmt.where(Chat.title.contains(title))
        if owner_id is not None:
            stmt = stmt.where(Chat.owner == owner_id)
        if pagination.cursor is not None:
            stmt = stmt.where(
                tuple_(Chat.updated_at, Chat.id)
                < tuple_(
                    literal(pagination.cursor[0]), literal(pagination.cursor[1])
                )
            )
        rows = list(
            (
                await self._session.scalars(
                    stmt.order_by(Chat.updated_at.desc(), Chat.id.desc()).limit(
                        limit + 1
                    )
                )
            ).all()
        )
        more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = (
            (rows[-1].updated_at, rows[-1].id) if more and rows else None
        )
        logger.debug(
            'Listed project chats: project_id=%d count=%d more=%s',
            project_id,
            len(rows),
            more,
        )
        return CursorPage(
            [self._to_dto(row) for row in rows],
            PaginationDTO(cursor=next_cursor, limit=limit, more=more),
        )

    async def update_chat_title(self, chat_id: int, title: str) -> ChatDTO:
        row = await self._session.get(Chat, chat_id)
        if row is None:
            logger.warning('Cannot update missing chat: chat_id=%d', chat_id)
            raise ChatNotFoundException(chat_id)
        row.title = title
        await self._session.flush()
        await self._session.refresh(row)
        logger.info('Updated chat title: chat_id=%d', chat_id)
        return self._to_dto(row)
