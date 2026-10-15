from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from agents.dtos.page import PaginationDTO
from agents.entities.chat import Chat
from agents.exceptions import ChatNotFoundException
from agents.repositories.chat import ChatRepository


@pytest.mark.asyncio
async def test_create_chat_returns_chat_dto(session: AsyncSession) -> None:
    repository = ChatRepository(session)

    chat = await repository.create_chat('Support', 11, 22)

    assert (
        chat.id > 0,
        chat.title,
        chat.project_id,
        chat.owner,
        isinstance(chat.created_at, datetime),
        isinstance(chat.updated_at, datetime),
    ) == (True, 'Support', 11, 22, True, True)


@pytest.mark.asyncio
async def test_get_chat_returns_none_when_chat_does_not_exist(
    session: AsyncSession,
) -> None:
    repository = ChatRepository(session)

    chat = await repository.get_chat(9999)

    assert chat is None


@pytest.mark.asyncio
async def test_get_chat_returns_existing_chat(session: AsyncSession) -> None:
    repository = ChatRepository(session)
    created = await repository.create_chat('Support', 11, 22)

    chat = await repository.get_chat(created.id)

    assert chat == created


@pytest.mark.asyncio
async def test_update_chat_title_changes_title(session: AsyncSession) -> None:
    repository = ChatRepository(session)
    created = await repository.create_chat('Old title', 11, 22)

    updated = await repository.update_chat_title(created.id, 'New title')

    assert (updated.id, updated.title, updated.project_id, updated.owner) == (
        created.id,
        'New title',
        11,
        22,
    )


@pytest.mark.asyncio
async def test_update_chat_title_raises_when_chat_is_missing(
    session: AsyncSession,
) -> None:
    repository = ChatRepository(session)

    with pytest.raises(ChatNotFoundException):
        await repository.update_chat_title(9999, 'New title')


@pytest.mark.asyncio
async def test_delete_chat_removes_existing_chat(session: AsyncSession) -> None:
    repository = ChatRepository(session)
    created = await repository.create_chat('Support', 11, 22)

    await repository.delete_chat(created.id)
    deleted = await repository.get_chat(created.id)

    assert deleted is None


@pytest.mark.asyncio
async def test_delete_chat_raises_when_chat_is_missing(
    session: AsyncSession,
) -> None:
    repository = ChatRepository(session)

    with pytest.raises(ChatNotFoundException):
        await repository.delete_chat(9999)


@pytest.mark.asyncio
async def test_get_chats_by_project_filters_project_and_orders_desc(
    session: AsyncSession,
) -> None:
    repository = ChatRepository(session)
    first = await repository.create_chat('First', 11, 22)
    second = await repository.create_chat('Second', 11, 22)
    await repository.create_chat('Other project', 12, 22)
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    await session.execute(
        update(Chat)
        .where(Chat.id == first.id)
        .values(updated_at=base + timedelta(seconds=1))
    )
    await session.execute(
        update(Chat)
        .where(Chat.id == second.id)
        .values(updated_at=base + timedelta(seconds=2))
    )
    await session.commit()

    page = await repository.get_chats_by_project(
        11, None, None, PaginationDTO(limit=10)
    )

    assert [chat.id for chat in page.items] == [second.id, first.id]


@pytest.mark.asyncio
async def test_get_chats_by_project_filters_title_substring(
    session: AsyncSession,
) -> None:
    repository = ChatRepository(session)
    matching = await repository.create_chat('Billing question', 11, 22)
    await repository.create_chat('Technical support', 11, 22)

    page = await repository.get_chats_by_project(
        11, 'Billing', None, PaginationDTO()
    )

    assert [chat.id for chat in page.items] == [matching.id]


@pytest.mark.asyncio
async def test_get_chats_by_project_filters_owner(
    session: AsyncSession,
) -> None:
    repository = ChatRepository(session)
    matching = await repository.create_chat('Owned', 11, 22)
    await repository.create_chat('Other owner', 11, 33)

    page = await repository.get_chats_by_project(11, None, 22, PaginationDTO())

    assert [chat.id for chat in page.items] == [matching.id]


@pytest.mark.asyncio
async def test_get_chats_by_project_returns_empty_page_without_matches(
    session: AsyncSession,
) -> None:
    repository = ChatRepository(session)

    page = await repository.get_chats_by_project(
        11, None, None, PaginationDTO()
    )

    assert (page.items, page.pagination.more, page.pagination.cursor) == (
        [],
        False,
        None,
    )


@pytest.mark.asyncio
async def test_get_chats_by_project_returns_next_cursor_when_more_results(
    session: AsyncSession,
) -> None:
    repository = ChatRepository(session)
    chats = [
        await repository.create_chat(f'Chat {index}', 11, 22)
        for index in range(3)
    ]
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for index, chat in enumerate(chats):
        await session.execute(
            update(Chat)
            .where(Chat.id == chat.id)
            .values(updated_at=base + timedelta(seconds=index))
        )
    await session.commit()

    page = await repository.get_chats_by_project(
        11, None, None, PaginationDTO(limit=2)
    )

    assert (
        [chat.id for chat in page.items],
        page.pagination.more,
        page.pagination.cursor,
    ) == (
        [chats[2].id, chats[1].id],
        True,
        (base + timedelta(seconds=1), chats[1].id),
    )


@pytest.mark.asyncio
async def test_get_chats_by_project_cursor_returns_following_page(
    session: AsyncSession,
) -> None:
    repository = ChatRepository(session)
    chats = [
        await repository.create_chat(f'Chat {index}', 11, 22)
        for index in range(3)
    ]
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for index, chat in enumerate(chats):
        await session.execute(
            update(Chat)
            .where(Chat.id == chat.id)
            .values(updated_at=base + timedelta(seconds=index))
        )
    await session.commit()
    cursor = (base + timedelta(seconds=1), chats[1].id)

    page = await repository.get_chats_by_project(
        11, None, None, PaginationDTO(cursor=cursor, limit=2)
    )

    assert ([chat.id for chat in page.items], page.pagination.more) == (
        [chats[0].id],
        False,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('requested_limit', 'expected_limit'), [(0, 1), (-5, 1), (101, 100)]
)
async def test_get_chats_by_project_clamps_limit(
    session: AsyncSession, requested_limit: int, expected_limit: int
) -> None:
    repository = ChatRepository(session)
    await repository.create_chat('Only chat', 11, 22)

    page = await repository.get_chats_by_project(
        11, None, None, PaginationDTO(limit=requested_limit)
    )

    assert page.pagination.limit == expected_limit
