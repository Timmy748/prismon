from datetime import UTC, datetime

import pytest

from agents.dtos.chat import ChatDTO, CreateChatDTO, UpdateTitleChatDTO
from agents.dtos.message import CreateMessageDTO, MessageDTO
from agents.dtos.page import CursorPage, PaginationDTO
from agents.entities.message import SenderType
from agents.exceptions import (
    ChatNotFoundException,
    ChatOwnerException,
    EmptyMessageException,
    InsufficientProjectPermissionException,
    InvalidChatTitleException,
    MultipleSubmitError,
)
from agents.llm_engine.base import (
    GenerationChunk,
    GenerationFinal,
    GenerationMetadata,
)
from agents.use_cases.chats import (
    create_chat,
    delete_chat,
    get_chat_messages,
    get_project_chats,
    send_message,
    update_chat_title,
)
from project.permissions import ProjectPermission


def _message_dto(
    sender_type: SenderType,
    message_id: int = 5,
    parent_id: int | None = None,
    text: str = 'hello',
) -> MessageDTO:
    now = datetime.now(UTC)
    return MessageDTO(
        message_id, 3, parent_id, sender_type, text, {}, {}, now, now
    )


def _configure_valid_send(
    chat_repository,
    message_repository,
    project_client,
    user_message: MessageDTO | None = None,
    history: list[MessageDTO] | None = None,
) -> None:
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = True
    message_repository.get_messages_by_chat.side_effect = [
        CursorPage([], PaginationDTO(limit=1)),
        CursorPage(
            (
                history
                if history is not None
                else [user_message or _message_dto(SenderType.USER)]
            ),
            PaginationDTO(limit=100),
        ),
    ]
    message_repository.create_human_message.return_value = (
        user_message or _message_dto(SenderType.USER, message_id=6)
    )


@pytest.mark.asyncio
async def test_send_message_stream_persists_unlinked_assistant_message(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    user_message = _message_dto(SenderType.USER, message_id=6)
    previous_user = _message_dto(SenderType.USER, message_id=2)
    previous_assistant = _message_dto(
        SenderType.ASSISTANT, message_id=3, parent_id=2
    )
    assistant_message = _message_dto(
        SenderType.ASSISTANT,
        message_id=7,
        parent_id=None,
        text='answer',
    )
    _configure_valid_send(
        chat_repository,
        message_repository,
        project_client,
        user_message,
        [user_message, previous_assistant, previous_user],
    )
    message_repository.create_ai_message.return_value = assistant_message
    data = CreateMessageDTO(None, SenderType.USER, 'hello', {}, {})

    events = await send_message(
        chat_repository,
        project_client,
        3,
        9,
        data,
    )
    received = [event async for event in events]

    assert received == [
        {'event': 'token', 'data': 'ans'},
        {'event': 'token', 'data': 'wer'},
        {'event': 'done', 'data': assistant_message},
    ]
    project_client.has_permission.assert_awaited_once_with(
        4, 9, ProjectPermission.CHAT_SEND_MESSAGE
    )
    message_repository.create_human_message.assert_awaited_once_with(3, 'hello')
    workflow_stub.registry.get_workflow.assert_called_once_with(
        'chat', engine=workflow_stub.engine
    )
    workflow_stub.workflow.stream.assert_called_once_with(
        '3', {'messages': [previous_user, previous_assistant, user_message]}
    )
    message_repository.create_ai_message.assert_awaited_once_with(
        chat_id=3,
        parent_id=None,
        text='answer',
        payload={},
        meta_data={
            'workflow': 'chat',
            'version': '1',
            'generation': {
                'model': 'test-model',
                'input_tokens': None,
                'output_tokens': None,
                'total_tokens': None,
                'elapsed_seconds': None,
                'tokens_per_second': None,
                'finish_reason': None,
            },
        },
    )


@pytest.mark.asyncio
async def test_send_message_rejects_blank_user_text(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    data = CreateMessageDTO(None, SenderType.USER, '  ', {}, {})

    with pytest.raises(EmptyMessageException):
        await send_message(
            chat_repository,
            project_client,
            3,
            9,
            data,
        )


@pytest.mark.asyncio
async def test_send_message_rejects_missing_chat(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    chat_repository.get_chat.return_value = None
    data = CreateMessageDTO(None, SenderType.USER, 'hello', {}, {})

    with pytest.raises(ChatNotFoundException):
        await send_message(
            chat_repository,
            project_client,
            3,
            9,
            data,
        )


@pytest.mark.asyncio
async def test_send_message_rejects_non_owner(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 12, datetime.now(UTC), datetime.now(UTC)
    )
    data = CreateMessageDTO(None, SenderType.USER, 'hello', {}, {})

    with pytest.raises(ChatOwnerException):
        await send_message(
            chat_repository,
            project_client,
            3,
            9,
            data,
        )


@pytest.mark.asyncio
async def test_send_message_rejects_missing_project_permission(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = False
    data = CreateMessageDTO(None, SenderType.USER, 'hello', {}, {})

    with pytest.raises(InsufficientProjectPermissionException):
        await send_message(
            chat_repository,
            project_client,
            3,
            9,
            data,
        )


@pytest.mark.asyncio
async def test_send_message_rejects_consecutive_user_message(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = True
    message_repository.get_messages_by_chat.return_value = CursorPage(
        [_message_dto(SenderType.USER)], PaginationDTO(limit=1)
    )
    data = CreateMessageDTO(None, SenderType.USER, 'hello again', {}, {})

    with pytest.raises(MultipleSubmitError):
        await send_message(
            chat_repository,
            project_client,
            3,
            9,
            data,
        )


@pytest.mark.asyncio
async def test_send_message_checks_latest_message_with_limit_one(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    _configure_valid_send(chat_repository, message_repository, project_client)
    data = CreateMessageDTO(None, SenderType.USER, 'hello', {}, {})

    await send_message(
        chat_repository,
        project_client,
        3,
        9,
        data,
    )

    assert message_repository.get_messages_by_chat.await_args_list[
        0
    ].kwargs == {
        'chat_id': 3,
        'pagination': PaginationDTO(limit=1),
    }


@pytest.mark.asyncio
async def test_send_message_rejects_blank_workflow_response(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    _configure_valid_send(chat_repository, message_repository, project_client)

    async def blank_response(*args, **kwargs):
        yield GenerationFinal('  ', [], GenerationMetadata())

    workflow_stub.workflow.stream.side_effect = blank_response
    data = CreateMessageDTO(None, SenderType.USER, 'hello', {}, {})

    events = await send_message(
        chat_repository,
        project_client,
        3,
        9,
        data,
    )

    received = [event async for event in events]

    assert len(received) == 1 and received[0]['event'] == 'error'
    message_repository.create_ai_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_message_stream_converts_generation_failure_to_error_event(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    _configure_valid_send(chat_repository, message_repository, project_client)

    async def failing_stream(*args, **kwargs):
        yield {'unexpected': 'event'}
        raise RuntimeError('generation failed')

    workflow_stub.workflow.stream.side_effect = failing_stream
    data = CreateMessageDTO(None, SenderType.USER, 'hello', {}, {})

    events = await send_message(
        chat_repository,
        project_client,
        3,
        9,
        data,
    )
    received = [event async for event in events]

    assert received == [
        {'event': 'error', 'data': {'message': 'generation failed'}}
    ]
    message_repository.create_ai_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_message_ignores_empty_chunks_and_unknown_events(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    _configure_valid_send(chat_repository, message_repository, project_client)

    async def stream_with_empty_chunk(*args, **kwargs):
        yield GenerationChunk(text_delta='')
        yield {'ignored': 'event'}
        yield GenerationFinal('answer', [], GenerationMetadata())

    workflow_stub.workflow.stream.side_effect = stream_with_empty_chunk
    assistant = _message_dto(SenderType.ASSISTANT, text='answer')
    message_repository.create_ai_message.return_value = assistant
    events = await send_message(
        chat_repository,
        project_client,
        3,
        9,
        CreateMessageDTO(None, SenderType.USER, 'hello', {}, {}),
    )

    assert [event async for event in events] == [
        {'event': 'done', 'data': assistant}
    ]


@pytest.mark.asyncio
async def test_send_message_emits_error_when_workflow_has_no_final_event(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    _configure_valid_send(chat_repository, message_repository, project_client)

    async def no_final(*args, **kwargs):
        yield GenerationChunk(text_delta='partial')

    workflow_stub.workflow.stream.side_effect = no_final
    events = await send_message(
        chat_repository,
        project_client,
        3,
        9,
        CreateMessageDTO(None, SenderType.USER, 'hello', {}, {}),
    )

    assert [event async for event in events] == [
        {'event': 'token', 'data': 'partial'},
        {
            'event': 'error',
            'data': {'message': 'O workflow terminou sem evento final.'},
        },
    ]
    message_repository.create_ai_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_message_emits_error_if_chat_disappears_before_save(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    chat_repository.get_chat.side_effect = [
        ChatDTO(3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)),
        None,
    ]
    project_client.has_permission.return_value = True
    message_repository.get_messages_by_chat.side_effect = [
        CursorPage([], PaginationDTO(limit=1)),
        CursorPage([_message_dto(SenderType.USER)], PaginationDTO(limit=100)),
    ]
    events = await send_message(
        chat_repository,
        project_client,
        3,
        9,
        CreateMessageDTO(None, SenderType.USER, 'hello', {}, {}),
    )

    received = [event async for event in events]

    assert received[-1] == {
        'event': 'error',
        'data': {'message': 'Chat 3 not found'},
    }
    message_repository.create_ai_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_chat_rejects_blank_title(chat_repository, project_client):
    with pytest.raises(InvalidChatTitleException):
        await create_chat(
            chat_repository,
            project_client,
            CreateChatDTO(project_id=4, owner=9, title='  '),
        )


@pytest.mark.asyncio
async def test_create_chat_persists_title_after_permission_check(
    chat_repository, project_client
):
    created = ChatDTO(3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC))
    chat_repository.create_chat.return_value = created
    project_client.has_permission.return_value = True

    result = await create_chat(
        chat_repository,
        project_client,
        CreateChatDTO(project_id=4, owner=9, title='Research'),
    )

    assert result == created
    chat_repository.create_chat.assert_awaited_once_with(
        title='Research', project_id=4, owner=9
    )


@pytest.mark.asyncio
async def test_get_chat_messages_returns_page_after_authorization(
    chat_repository, message_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = True
    page = CursorPage([], PaginationDTO(limit=12))
    message_repository.get_messages_by_chat.return_value = page

    result = await get_chat_messages(
        chat_repository,
        project_client,
        3,
        9,
        PaginationDTO(limit=12),
    )

    assert result == page


@pytest.mark.asyncio
async def test_update_chat_title_persists_after_authorization(
    chat_repository, project_client
):
    updated = ChatDTO(3, 'Updated', 4, 9, datetime.now(UTC), datetime.now(UTC))
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    chat_repository.update_chat_title.return_value = updated
    project_client.has_permission.return_value = True

    result = await update_chat_title(
        chat_repository,
        project_client,
        3,
        9,
        UpdateTitleChatDTO('Updated'),
    )

    assert result == updated
    chat_repository.update_chat_title.assert_awaited_once_with(3, 'Updated')


@pytest.mark.asyncio
async def test_update_chat_title_rejects_blank_title(
    chat_repository, project_client
):
    with pytest.raises(InvalidChatTitleException):
        await update_chat_title(
            chat_repository,
            project_client,
            3,
            9,
            UpdateTitleChatDTO(' '),
        )


@pytest.mark.asyncio
async def test_delete_chat_deletes_after_authorization(
    chat_repository, project_client
):
    chat_repository.get_chat.return_value = ChatDTO(
        3, 'Research', 4, 9, datetime.now(UTC), datetime.now(UTC)
    )
    project_client.has_permission.return_value = True

    await delete_chat(chat_repository, project_client, 3, 9)

    chat_repository.delete_chat.assert_awaited_once_with(3)


@pytest.mark.asyncio
async def test_get_project_chats_returns_repository_page(
    chat_repository, project_client
):
    page = CursorPage([], PaginationDTO(limit=10))
    chat_repository.get_chats_by_project.return_value = page
    project_client.has_permission.return_value = True

    result = await get_project_chats(
        chat_repository, project_client, 4, 9, PaginationDTO(limit=10)
    )

    assert result == page
