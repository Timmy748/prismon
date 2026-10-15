from datetime import UTC, datetime

import pytest

from agents.dtos.chat import (
    MAX_CHAT_TITLE_LENGTH,
    ChatDTO,
    CreateChatDTO,
    UpdateTitleChatDTO,
)
from agents.dtos.message import MessageDTO
from agents.dtos.page import CursorPage, PaginationDTO
from agents.entities.message import SenderType
from agents.exceptions import (
    ChatNotFoundException,
    ChatOwnerException,
    InsufficientProjectPermissionException,
    InvalidChatTitleException,
)
from agents.use_cases.chats import (
    create_chat,
    delete_chat,
    get_chat_messages,
    get_project_chats,
    update_chat_title,
)
from project.permissions import ProjectPermission


@pytest.mark.asyncio
async def test_create_chat_returns_created_chat(
    chat_repository, project_client
):
    data = CreateChatDTO(project_id=4, owner=9, title='Research')
    expected = ChatDTO(
        1, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    chat_repository.create_chat.return_value = expected
    project_client.has_permission.return_value = True

    result = await create_chat(chat_repository, project_client, data)

    assert result is expected


@pytest.mark.asyncio
async def test_create_chat_forwards_chat_fields(
    chat_repository, project_client
):
    data = CreateChatDTO(project_id=4, owner=9, title='Research')
    project_client.has_permission.return_value = True

    await create_chat(chat_repository, project_client, data)

    chat_repository.create_chat.assert_awaited_once_with(
        title='Research', project_id=4, owner=9
    )


@pytest.mark.asyncio
async def test_create_chat_checks_create_permission(
    chat_repository, project_client
):
    data = CreateChatDTO(project_id=4, owner=9, title='Research')
    project_client.has_permission.return_value = True

    await create_chat(chat_repository, project_client, data)

    project_client.has_permission.assert_awaited_once_with(
        4, 9, ProjectPermission.CHAT_CREATE
    )


@pytest.mark.asyncio
async def test_create_chat_rejects_blank_title(chat_repository, project_client):
    data = CreateChatDTO(project_id=4, owner=9, title='  ')

    with pytest.raises(InvalidChatTitleException):
        await create_chat(chat_repository, project_client, data)


@pytest.mark.asyncio
async def test_create_chat_rejects_title_over_max_length(
    chat_repository, project_client
):
    data = CreateChatDTO(
        project_id=4, owner=9, title='x' * (MAX_CHAT_TITLE_LENGTH + 1)
    )

    with pytest.raises(InvalidChatTitleException):
        await create_chat(chat_repository, project_client, data)


@pytest.mark.asyncio
async def test_create_chat_rejects_missing_permission(
    chat_repository, project_client
):
    data = CreateChatDTO(project_id=4, owner=9, title='Research')
    project_client.has_permission.return_value = False

    with pytest.raises(InsufficientProjectPermissionException):
        await create_chat(chat_repository, project_client, data)


@pytest.mark.asyncio
async def test_get_chat_messages_returns_repository_page(
    chat_repository, message_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = True
    pagination = PaginationDTO(limit=7)
    expected = CursorPage([], pagination)
    message_repository.get_messages_by_chat.return_value = expected

    result = await get_chat_messages(
        chat_repository, message_repository, project_client, 3, 9, pagination
    )

    assert result is expected


@pytest.mark.asyncio
async def test_get_chat_messages_forwards_chat_and_pagination(
    chat_repository, message_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = True
    pagination = PaginationDTO(limit=7)

    await get_chat_messages(
        chat_repository, message_repository, project_client, 3, 9, pagination
    )

    message_repository.get_messages_by_chat.assert_awaited_once_with(
        3, pagination
    )


@pytest.mark.asyncio
async def test_get_chat_messages_rejects_missing_chat(
    chat_repository, message_repository, project_client
):
    chat_repository.get_chat.return_value = None

    with pytest.raises(ChatNotFoundException):
        await get_chat_messages(
            chat_repository,
            message_repository,
            project_client,
            3,
            9,
            PaginationDTO(),
        )


@pytest.mark.asyncio
async def test_get_chat_messages_rejects_missing_permission(
    chat_repository, message_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = False

    with pytest.raises(InsufficientProjectPermissionException):
        await get_chat_messages(
            chat_repository,
            message_repository,
            project_client,
            3,
            9,
            PaginationDTO(),
        )


@pytest.mark.asyncio
async def test_get_chat_messages_checks_read_permission(
    chat_repository, message_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = True

    await get_chat_messages(
        chat_repository,
        message_repository,
        project_client,
        3,
        9,
        PaginationDTO(),
    )

    project_client.has_permission.assert_awaited_once_with(
        4, 9, ProjectPermission.CHAT_READ
    )


def _message_dto(sender_type: SenderType) -> MessageDTO:
    now = datetime.now(UTC)
    return MessageDTO(5, 3, None, sender_type, 'hello', {}, {}, now, now)


@pytest.mark.asyncio
async def test_update_chat_title_returns_updated_chat(
    chat_repository, project_client
):
    expected = ChatDTO(3, 'Updated', 4, 9, datetime.now(UTC), datetime.now(UTC))
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    chat_repository.update_chat_title.return_value = expected
    project_client.has_permission.return_value = True

    result = await update_chat_title(
        chat_repository, project_client, 3, 9, UpdateTitleChatDTO('Updated')
    )

    assert result is expected


@pytest.mark.asyncio
async def test_update_chat_title_passes_chat_and_title(
    chat_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = True

    await update_chat_title(
        chat_repository, project_client, 3, 9, UpdateTitleChatDTO('Updated')
    )

    chat_repository.update_chat_title.assert_awaited_once_with(3, 'Updated')


@pytest.mark.asyncio
async def test_update_chat_title_rejects_blank_title(
    chat_repository, project_client
):
    data = UpdateTitleChatDTO('  ')

    with pytest.raises(InvalidChatTitleException):
        await update_chat_title(chat_repository, project_client, 3, 9, data)


@pytest.mark.asyncio
async def test_update_chat_title_rejects_title_over_max_length(
    chat_repository, project_client
):
    data = UpdateTitleChatDTO('x' * (MAX_CHAT_TITLE_LENGTH + 1))

    with pytest.raises(InvalidChatTitleException):
        await update_chat_title(chat_repository, project_client, 3, 9, data)


@pytest.mark.asyncio
async def test_update_chat_title_rejects_missing_chat(
    chat_repository, project_client
):
    chat_repository.get_chat.return_value = None

    with pytest.raises(ChatNotFoundException):
        await update_chat_title(
            chat_repository, project_client, 3, 9, UpdateTitleChatDTO('Updated')
        )


@pytest.mark.asyncio
async def test_update_chat_title_rejects_non_owner(
    chat_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 12, datetime.now(UTC), datetime.now(UTC)
    )

    with pytest.raises(ChatOwnerException):
        await update_chat_title(
            chat_repository, project_client, 3, 9, UpdateTitleChatDTO('Updated')
        )


@pytest.mark.asyncio
async def test_update_chat_title_rejects_missing_permission(
    chat_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = False

    with pytest.raises(InsufficientProjectPermissionException):
        await update_chat_title(
            chat_repository, project_client, 3, 9, UpdateTitleChatDTO('Updated')
        )


@pytest.mark.asyncio
async def test_update_chat_title_checks_update_permission(
    chat_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = True

    await update_chat_title(
        chat_repository, project_client, 3, 9, UpdateTitleChatDTO('Updated')
    )

    project_client.has_permission.assert_awaited_once_with(
        4, 9, ProjectPermission.CHAT_UPDATE
    )


@pytest.mark.asyncio
async def test_delete_chat_deletes_chat(chat_repository, project_client):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = True

    result = await delete_chat(chat_repository, project_client, 3, 9)

    assert result is None


@pytest.mark.asyncio
async def test_delete_chat_calls_repository(chat_repository, project_client):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = True

    await delete_chat(chat_repository, project_client, 3, 9)

    chat_repository.delete_chat.assert_awaited_once_with(3)


@pytest.mark.asyncio
async def test_delete_chat_rejects_missing_chat(
    chat_repository, project_client
):
    chat_repository.get_chat.return_value = None

    with pytest.raises(ChatNotFoundException):
        await delete_chat(chat_repository, project_client, 3, 9)


@pytest.mark.asyncio
async def test_delete_chat_rejects_non_owner(chat_repository, project_client):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 12, datetime.now(UTC), datetime.now(UTC)
    )

    with pytest.raises(ChatOwnerException):
        await delete_chat(chat_repository, project_client, 3, 9)


@pytest.mark.asyncio
async def test_delete_chat_rejects_missing_permission(
    chat_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = False

    with pytest.raises(InsufficientProjectPermissionException):
        await delete_chat(chat_repository, project_client, 3, 9)


@pytest.mark.asyncio
async def test_delete_chat_checks_delete_permission(
    chat_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = True

    await delete_chat(chat_repository, project_client, 3, 9)

    project_client.has_permission.assert_awaited_once_with(
        4, 9, ProjectPermission.CHAT_DELETE
    )


@pytest.mark.asyncio
async def test_get_project_chats_returns_repository_page(
    chat_repository, project_client
):
    project_client.has_permission.return_value = True
    pagination = PaginationDTO(limit=8)
    expected = CursorPage([], pagination)
    chat_repository.get_chats_by_project.return_value = expected

    result = await get_project_chats(
        chat_repository, project_client, 4, 9, pagination
    )

    assert result is expected


@pytest.mark.asyncio
async def test_get_project_chats_forwards_project_and_pagination(
    chat_repository, project_client
):
    project_client.has_permission.return_value = True
    pagination = PaginationDTO(limit=8)

    await get_project_chats(chat_repository, project_client, 4, 9, pagination)

    chat_repository.get_chats_by_project.assert_awaited_once_with(
        project_id=4, title=None, owner_id=None, pagination=pagination
    )


@pytest.mark.asyncio
async def test_get_project_chats_rejects_missing_permission(
    chat_repository, project_client
):
    project_client.has_permission.return_value = False

    with pytest.raises(InsufficientProjectPermissionException):
        await get_project_chats(
            chat_repository, project_client, 4, 9, PaginationDTO()
        )


@pytest.mark.asyncio
async def test_get_project_chats_checks_read_permission(
    chat_repository, project_client
):
    project_client.has_permission.return_value = True

    await get_project_chats(
        chat_repository, project_client, 4, 9, PaginationDTO()
    )

    project_client.has_permission.assert_awaited_once_with(
        4, 9, ProjectPermission.CHAT_READ
    )
