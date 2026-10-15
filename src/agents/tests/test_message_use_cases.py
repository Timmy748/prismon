from datetime import UTC, datetime

import pytest

from agents.dtos.chat import ChatDTO
from agents.dtos.message import CreateMessageDTO, MessageDTO
from agents.dtos.page import CursorPage, PaginationDTO
from agents.entities.message import SenderType
from agents.exceptions import (
    ChatNotFoundException,
    ChatOwnerException,
    EmptyMessageException,
    InsufficientProjectPermissionException,
    MultipleSubmitError,
)
from agents.use_cases.chats import send_ai_message, send_human_message


def _message_dto(sender_type: SenderType) -> MessageDTO:
    now = datetime.now(UTC)
    return MessageDTO(5, 3, None, sender_type, 'hello', {}, {}, now, now)


@pytest.mark.asyncio
async def test_send_human_message_returns_created_message(
    chat_repository, message_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = True
    message_repository.get_messages_by_chat.return_value = CursorPage(
        [], PaginationDTO()
    )
    message_repository.create_human_message.return_value = _message_dto(
        SenderType.USER
    )
    data = CreateMessageDTO(None, SenderType.USER, 'hello', {}, {})

    result = await send_human_message(
        chat_repository, message_repository, project_client, 3, 9, data
    )

    assert result is message_repository.create_human_message.return_value


@pytest.mark.asyncio
async def test_send_human_message_passes_chat_and_text(
    chat_repository, message_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = True
    message_repository.get_messages_by_chat.return_value = CursorPage(
        [], PaginationDTO()
    )
    data = CreateMessageDTO(None, SenderType.USER, 'hello', {}, {})

    await send_human_message(
        chat_repository, message_repository, project_client, 3, 9, data
    )

    message_repository.create_human_message.assert_awaited_once_with(3, 'hello')


@pytest.mark.asyncio
async def test_send_human_message_rejects_blank_text(
    chat_repository, message_repository, project_client
):
    data = CreateMessageDTO(None, SenderType.USER, '  ', {}, {})

    with pytest.raises(EmptyMessageException):
        await send_human_message(
            chat_repository, message_repository, project_client, 3, 9, data
        )


@pytest.mark.asyncio
async def test_send_human_message_rejects_missing_chat(
    chat_repository, message_repository, project_client
):
    chat_repository.get_chat.return_value = None
    data = CreateMessageDTO(None, SenderType.USER, 'hello', {}, {})

    with pytest.raises(ChatNotFoundException):
        await send_human_message(
            chat_repository, message_repository, project_client, 3, 9, data
        )


@pytest.mark.asyncio
async def test_send_human_message_rejects_non_owner(
    chat_repository, message_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 12, datetime.now(UTC), datetime.now(UTC)
    )
    data = CreateMessageDTO(None, SenderType.USER, 'hello', {}, {})

    with pytest.raises(ChatOwnerException):
        await send_human_message(
            chat_repository, message_repository, project_client, 3, 9, data
        )


@pytest.mark.asyncio
async def test_send_human_message_rejects_missing_permission(
    chat_repository, message_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = False
    data = CreateMessageDTO(None, SenderType.USER, 'hello', {}, {})

    with pytest.raises(InsufficientProjectPermissionException):
        await send_human_message(
            chat_repository, message_repository, project_client, 3, 9, data
        )


@pytest.mark.asyncio
async def test_send_human_message_rejects_consecutive_user_message(
    chat_repository, message_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = True
    message_repository.get_messages_by_chat.return_value = CursorPage(
        [_message_dto(SenderType.USER)], PaginationDTO()
    )
    data = CreateMessageDTO(None, SenderType.USER, 'hello again', {}, {})

    with pytest.raises(MultipleSubmitError):
        await send_human_message(
            chat_repository, message_repository, project_client, 3, 9, data
        )


@pytest.mark.asyncio
async def test_send_human_message_uses_latest_message_limit(
    chat_repository, message_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = True
    message_repository.get_messages_by_chat.return_value = CursorPage(
        [_message_dto(SenderType.ASSISTANT)], PaginationDTO()
    )
    data = CreateMessageDTO(None, SenderType.USER, 'hello', {}, {})

    await send_human_message(
        chat_repository, message_repository, project_client, 3, 9, data
    )

    message_repository.get_messages_by_chat.assert_awaited_once_with(
        chat_id=3, pagination=PaginationDTO(limit=1)
    )


@pytest.mark.asyncio
async def test_send_ai_message_returns_created_message(
    chat_repository, message_repository
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    expected = _message_dto(SenderType.ASSISTANT)
    message_repository.create_ai_message.return_value = expected
    data = CreateMessageDTO(
        2, SenderType.ASSISTANT, 'answer', {'a': 1}, {'b': 2}
    )

    result = await send_ai_message(chat_repository, message_repository, 3, data)

    assert result is expected


@pytest.mark.asyncio
async def test_send_ai_message_forwards_message_fields(
    chat_repository, message_repository
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    data = CreateMessageDTO(
        2, SenderType.ASSISTANT, 'answer', {'a': 1}, {'b': 2}
    )

    await send_ai_message(chat_repository, message_repository, 3, data)

    message_repository.create_ai_message.assert_awaited_once_with(
        chat_id=3,
        parent_id=2,
        text='answer',
        payload={'a': 1},
        meta_data={'b': 2},
    )


@pytest.mark.asyncio
async def test_send_ai_message_rejects_blank_text(
    chat_repository, message_repository
):
    data = CreateMessageDTO(None, SenderType.ASSISTANT, ' ', {}, {})

    with pytest.raises(EmptyMessageException):
        await send_ai_message(chat_repository, message_repository, 3, data)


@pytest.mark.asyncio
async def test_send_ai_message_rejects_missing_chat(
    chat_repository, message_repository
):
    chat_repository.get_chat.return_value = None
    data = CreateMessageDTO(None, SenderType.ASSISTANT, 'answer', {}, {})

    with pytest.raises(ChatNotFoundException):
        await send_ai_message(chat_repository, message_repository, 3, data)
