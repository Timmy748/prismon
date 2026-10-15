from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from agents.dtos.chat import ChatDTO
from agents.dtos.page import PaginationDTO
from agents.entities.message import Message, SenderType
from agents.exceptions import MessageNotFoundException
from agents.repositories.chat import ChatRepository
from agents.repositories.message import MessageRepository


@pytest.mark.asyncio
async def test_create_human_message_sets_user_defaults(
    session: AsyncSession,
) -> None:
    repository = MessageRepository(session)
    chat = await _create_chat(session)

    message = await repository.create_human_message(chat.id, 'Hello')

    assert (
        message.id > 0,
        message.chat_id,
        message.parent_id,
        message.sender_type,
        message.text,
        message.payload,
        message.meta_data,
        isinstance(message.created_at, datetime),
        isinstance(message.updated_at, datetime),
    ) == (True, chat.id, None, SenderType.USER, 'Hello', {}, {}, True, True)


@pytest.mark.asyncio
async def test_create_ai_message_preserves_parent_payload_and_metadata(
    session: AsyncSession,
) -> None:
    repository = MessageRepository(session)
    chat = await _create_chat(session)
    parent = await repository.create_human_message(chat.id, 'Question')
    payload = {'answer': 42}
    meta_data = {'source': 'assistant'}

    message = await repository.create_ai_message(
        chat.id, parent.id, 'Response', payload, meta_data
    )

    assert (
        message.chat_id,
        message.parent_id,
        message.sender_type,
        message.text,
        message.payload,
        message.meta_data,
    ) == (
        chat.id,
        parent.id,
        SenderType.ASSISTANT,
        'Response',
        payload,
        meta_data,
    )


@pytest.mark.asyncio
async def test_get_messages_by_chat_returns_empty_page_for_unknown_chat(
    session: AsyncSession,
) -> None:
    repository = MessageRepository(session)

    page = await repository.get_messages_by_chat(9999, PaginationDTO())

    assert (page.items, page.pagination.more, page.pagination.cursor) == (
        [],
        False,
        None,
    )


@pytest.mark.asyncio
async def test_get_messages_by_chat_orders_desc_and_filters_chat(
    session: AsyncSession,
) -> None:
    repository = MessageRepository(session)
    chat = await _create_chat(session)
    other_chat = await _create_chat(session)
    first = await repository.create_human_message(chat.id, 'First')
    second = await repository.create_human_message(chat.id, 'Second')
    await repository.create_human_message(other_chat.id, 'Other chat')
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    await session.execute(
        update(Message)
        .where(Message.id == first.id)
        .values(created_at=base + timedelta(seconds=1))
    )
    await session.execute(
        update(Message)
        .where(Message.id == second.id)
        .values(created_at=base + timedelta(seconds=2))
    )
    await session.commit()

    page = await repository.get_messages_by_chat(chat.id, PaginationDTO())

    assert [message.id for message in page.items] == [second.id, first.id]


@pytest.mark.asyncio
async def test_get_messages_by_chat_returns_cursor_when_more_results(
    session: AsyncSession,
) -> None:
    repository = MessageRepository(session)
    chat = await _create_chat(session)
    messages = [
        await repository.create_human_message(chat.id, f'Message {index}')
        for index in range(3)
    ]
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for index, message in enumerate(messages):
        await session.execute(
            update(Message)
            .where(Message.id == message.id)
            .values(created_at=base + timedelta(seconds=index))
        )
    await session.commit()

    page = await repository.get_messages_by_chat(
        chat.id, PaginationDTO(limit=2)
    )

    assert (
        [message.id for message in page.items],
        page.pagination.more,
        page.pagination.cursor,
    ) == (
        [messages[2].id, messages[1].id],
        True,
        (base + timedelta(seconds=1), messages[1].id),
    )


@pytest.mark.asyncio
async def test_get_messages_by_chat_cursor_returns_following_page(
    session: AsyncSession,
) -> None:
    repository = MessageRepository(session)
    chat = await _create_chat(session)
    messages = [
        await repository.create_human_message(chat.id, f'Message {index}')
        for index in range(3)
    ]
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for index, message in enumerate(messages):
        await session.execute(
            update(Message)
            .where(Message.id == message.id)
            .values(created_at=base + timedelta(seconds=index))
        )
    await session.commit()

    page = await repository.get_messages_by_chat(
        chat.id,
        PaginationDTO(
            cursor=(base + timedelta(seconds=1), messages[1].id), limit=2
        ),
    )

    assert ([message.id for message in page.items], page.pagination.more) == (
        [messages[0].id],
        False,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('requested_limit', 'expected_limit'), [(0, 1), (-5, 1), (101, 100)]
)
async def test_get_messages_by_chat_clamps_limit(
    session: AsyncSession, requested_limit: int, expected_limit: int
) -> None:
    repository = MessageRepository(session)
    chat = await _create_chat(session)
    await repository.create_human_message(chat.id, 'Only message')

    page = await repository.get_messages_by_chat(
        chat.id, PaginationDTO(limit=requested_limit)
    )

    assert page.pagination.limit == expected_limit


@pytest.mark.asyncio
async def test_update_message_changes_text_payload_and_metadata(
    session: AsyncSession,
) -> None:
    repository = MessageRepository(session)
    chat = await _create_chat(session)
    created = await repository.create_human_message(chat.id, 'Old text')

    updated = await repository.update_message(
        created.id, 'New text', {'answer': 42}, {'edited': True}
    )

    assert (
        updated.id,
        updated.text,
        updated.payload,
        updated.meta_data,
    ) == (created.id, 'New text', {'answer': 42}, {'edited': True})


@pytest.mark.asyncio
async def test_update_message_raises_when_message_is_missing(
    session: AsyncSession,
) -> None:
    repository = MessageRepository(session)

    with pytest.raises(MessageNotFoundException):
        await repository.update_message(9999, 'Text', {}, {})


async def _create_chat(session: AsyncSession) -> ChatDTO:
    return await ChatRepository(session).create_chat('Chat', 11, 22)
