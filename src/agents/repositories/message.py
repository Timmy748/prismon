from typing import Any, Protocol

from sqlalchemy import literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from agents.dtos.message import MessageDTO
from agents.dtos.page import CursorPage, PaginationDTO
from agents.entities.message import Message, SenderType
from agents.exceptions import MessageNotFoundException
from infra.logs import get_logger

logger = get_logger(__name__)


class IMessageRepository(Protocol):
    async def create_ai_message(
        self,
        chat_id: int,
        parent_id: int | None,
        text: str,
        payload: dict[str, Any],
        meta_data: dict[str, Any],
    ) -> MessageDTO: ...

    async def create_human_message(
        self, chat_id: int, text: str
    ) -> MessageDTO: ...

    async def get_messages_by_chat(
        self, chat_id: int, pagination: PaginationDTO
    ) -> CursorPage[MessageDTO]: ...

    async def update_message(
        self,
        message_id: int,
        text: str,
        payload: dict[str, Any],
        meta_data: dict[str, Any],
    ) -> MessageDTO: ...


class MessageRepository(IMessageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_dto(self, row: Message) -> MessageDTO:
        return MessageDTO(
            id=row.id,
            chat_id=row.chat_id,
            parent_id=row.parent_id,
            sender_type=row.sender_type,
            text=row.text,
            payload=row.payload,
            meta_data=row.meta_data,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def create_ai_message(
        self,
        chat_id: int,
        parent_id: int | None,
        text: str,
        payload: dict[str, Any],
        meta_data: dict[str, Any],
    ) -> MessageDTO:
        row = Message(
            chat_id=chat_id,
            parent_id=parent_id,
            sender_type=SenderType.ASSISTANT,
            text=text,
            payload=payload,
            meta_data=meta_data,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        logger.info(
            'Created assistant message: chat_id=%d message_id=%d',
            chat_id,
            row.id,
        )
        return self._to_dto(row)

    async def create_human_message(self, chat_id: int, text: str) -> MessageDTO:
        row = Message(
            chat_id=chat_id,
            parent_id=None,
            sender_type=SenderType.USER,
            text=text,
            payload={},
            meta_data={},
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        logger.info(
            'Created user message: chat_id=%d message_id=%d', chat_id, row.id
        )
        return self._to_dto(row)

    async def get_messages_by_chat(
        self, chat_id: int, pagination: PaginationDTO
    ) -> CursorPage[MessageDTO]:
        limit = max(1, min(pagination.limit, 100))
        stmt = select(Message).where(Message.chat_id == chat_id)
        if pagination.cursor is not None:
            stmt = stmt.where(
                tuple_(Message.created_at, Message.id)
                < tuple_(
                    literal(pagination.cursor[0]), literal(pagination.cursor[1])
                )
            )
        rows = list(
            (
                await self._session.scalars(
                    stmt.order_by(
                        Message.created_at.desc(), Message.id.desc()
                    ).limit(limit + 1)
                )
            ).all()
        )
        more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = (
            (rows[-1].created_at, rows[-1].id) if more and rows else None
        )
        logger.debug(
            'Listed chat messages: chat_id=%d count=%d more=%s',
            chat_id,
            len(rows),
            more,
        )
        return CursorPage(
            [self._to_dto(row) for row in rows],
            PaginationDTO(cursor=next_cursor, limit=limit, more=more),
        )

    async def update_message(
        self,
        message_id: int,
        text: str,
        payload: dict[str, Any],
        meta_data: dict[str, Any],
    ) -> MessageDTO:
        row = await self._session.get(Message, message_id)
        if row is None:
            logger.warning(
                'Cannot update missing message: message_id=%d', message_id
            )
            raise MessageNotFoundException(message_id)
        row.text = text
        row.payload = payload
        row.meta_data = meta_data
        await self._session.flush()
        await self._session.refresh(row)
        logger.info('Updated message: message_id=%d', message_id)
        return self._to_dto(row)
