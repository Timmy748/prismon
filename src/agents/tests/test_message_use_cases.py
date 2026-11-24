import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import call

import pytest

import agents.use_cases.chats as chat_use_cases
from agents.actions import ChatAction
from agents.dtos.chat import ChatDTO, CreateChatDTO, UpdateTitleChatDTO
from agents.dtos.message import CreateMessageDTO, MessageDTO
from agents.dtos.page import CursorPage, PaginationDTO
from agents.entities.message import SenderType
from agents.exceptions import (
    ApiKeyNotFoundException,
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
from agents.tests.fixtures.mocks import MockAgentsUnitOfWork
from agents.use_cases.chats import (
    create_chat,
    delete_chat,
    get_chat_messages,
    get_project_chats,
    send_message,
    update_chat_title,
)


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
    project_client.verify_resource_permission.return_value = True
    project_client.get_api_key.return_value = 'api-secret'
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
    monkeypatch,
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
    monkeypatch.setattr(
        chat_use_cases,
        'get_settings',
        lambda: SimpleNamespace(LLM_PROVIDER='openrouter'),
    )

    events = await send_message(
        chat_repository,
        project_client,
        3,
        9,
        123,
        data,
    )
    received = [event async for event in events]

    assert received == [
        {'event': 'token', 'data': 'ans'},
        {'event': 'token', 'data': 'wer'},
        {'event': 'done', 'data': assistant_message},
    ]
    project_client.verify_resource_permission.assert_awaited_once_with(
        4, 9, ChatAction.SEND_MESSAGE
    )
    project_client.get_api_key.assert_awaited_once_with(4, 9, 123)
    message_repository.create_human_message.assert_awaited_once_with(3, 'hello')
    workflow_call = workflow_stub.registry.get_workflow.call_args
    assert workflow_call.args == ('chat',)
    assert workflow_call.kwargs['engine'] is workflow_stub.engine
    assert callable(workflow_call.kwargs['rag_node'].run)
    assert chat_use_cases.create_llm_engine.call_args_list == [
        call(api_key='api-secret', provider='openrouter', model=None),
        call(api_key='api-secret', provider='openrouter', model=None),
    ]
    stream_call = workflow_stub.workflow.stream.call_args
    assert stream_call.args[0] == '3'
    assert stream_call.args[1] == {
        'messages': [previous_user, previous_assistant, user_message],
        'project_id': 4,
        'user_id': 9,
    }
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
async def test_send_message_forwards_workflow_config(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    _configure_valid_send(chat_repository, message_repository, project_client)
    config = {'respond': {'temperature': 0.2}}

    events = await send_message(
        chat_repository,
        project_client,
        3,
        9,
        123,
        CreateMessageDTO(None, SenderType.USER, 'hello', {}, {}),
        config=config,
    )
    [event async for event in events]

    assert workflow_stub.workflow.stream.call_args.args[1]['config'] == config


@pytest.mark.asyncio
async def test_send_message_routes_rag_and_chat_configs_to_separate_engines(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
    monkeypatch,
):
    _configure_valid_send(chat_repository, message_repository, project_client)
    rag_engine = object()
    chat_engine = object()
    create_engine = chat_use_cases.create_llm_engine
    create_engine.side_effect = [rag_engine, chat_engine]
    monkeypatch.setattr(
        chat_use_cases,
        'create_embedding_engine',
        object,
    )
    config = {
        'rag': {'provider': 'ollama', 'model': 'rag-model'},
        'chat': {'provider': 'openrouter', 'model': 'chat/model'},
    }

    events = await send_message(
        chat_repository,
        project_client,
        3,
        9,
        123,
        CreateMessageDTO(None, SenderType.USER, 'hello', {}, {}),
        config=config,
    )
    [event async for event in events]

    assert create_engine.call_args_list == [
        call(api_key='api-secret', provider='ollama', model='rag-model'),
        call(api_key='api-secret', provider='openrouter', model='chat/model'),
    ]
    workflow_call = workflow_stub.registry.get_workflow.call_args
    assert workflow_call.kwargs['engine'] is chat_engine
    assert workflow_call.kwargs['rag_node']._engine is rag_engine


@pytest.mark.parametrize('graph_name', ['rag', 'chat'])
@pytest.mark.asyncio
async def test_send_message_ignores_non_mapping_graph_config(  # noqa: PLR0913, PLR0917
    graph_name,
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
    monkeypatch,
):
    _configure_valid_send(chat_repository, message_repository, project_client)
    monkeypatch.setattr(
        chat_use_cases,
        'get_settings',
        lambda: SimpleNamespace(LLM_PROVIDER='ollama'),
    )
    config = {graph_name: ['invalid', 'graph', 'config']}

    events = await send_message(
        chat_repository,
        project_client,
        3,
        9,
        123,
        CreateMessageDTO(None, SenderType.USER, 'hello', {}, {}),
        config=config,
    )
    [event async for event in events]

    assert chat_use_cases.create_llm_engine.call_args_list == [
        call(api_key='api-secret', provider='ollama', model=None),
        call(api_key='api-secret', provider='ollama', model=None),
    ]


@pytest.mark.asyncio
async def test_send_message_forwards_generic_workflow_events(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    _configure_valid_send(chat_repository, message_repository, project_client)

    async def stream_with_node_event(*args, **kwargs):
        yield {'event': 'node_progress', 'data': {'node': 'retrieve'}}
        yield GenerationFinal('answer', [], GenerationMetadata())

    workflow_stub.workflow.stream.side_effect = stream_with_node_event
    assistant = _message_dto(SenderType.ASSISTANT, text='answer')
    message_repository.create_ai_message.return_value = assistant
    events = await send_message(
        chat_repository,
        project_client,
        3,
        9,
        123,
        CreateMessageDTO(None, SenderType.USER, 'hello', {}, {}),
    )

    received = [event async for event in events]

    assert received == [
        {'event': 'node_progress', 'data': {'node': 'retrieve'}},
        {'event': 'done', 'data': assistant},
    ]


@pytest.mark.asyncio
async def test_send_message_persists_after_sse_consumer_disconnects(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    _configure_valid_send(chat_repository, message_repository, project_client)
    release_generation = asyncio.Event()
    persisted = asyncio.Event()
    committed = asyncio.Event()
    worker_uow = MockAgentsUnitOfWork(
        chat_repository.chat_repository,
        message_repository,
        chat_repository.workflow_repository,
    )
    worker_uow.commit.side_effect = committed.set
    assistant = _message_dto(SenderType.ASSISTANT, text='answer')

    async def paused_stream(*args, **kwargs):
        yield GenerationChunk(text_delta='partial')
        await release_generation.wait()
        yield GenerationFinal('answer', [], GenerationMetadata())

    async def save_assistant(**kwargs):
        persisted.set()
        return assistant

    workflow_stub.workflow.stream.side_effect = paused_stream
    message_repository.create_ai_message.side_effect = save_assistant
    events = await send_message(
        chat_repository,
        project_client,
        3,
        9,
        123,
        CreateMessageDTO(None, SenderType.USER, 'hello', {}, {}),
        uow_factory=lambda: worker_uow,
    )
    assert await events.__anext__() == {'event': 'token', 'data': 'partial'}

    await events.aclose()
    release_generation.set()
    await asyncio.wait_for(persisted.wait(), timeout=1)
    await asyncio.wait_for(committed.wait(), timeout=1)

    worker_uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_message_rolls_back_worker_uow_on_generation_error(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    _configure_valid_send(chat_repository, message_repository, project_client)
    worker_uow = MockAgentsUnitOfWork(
        chat_repository.chat_repository,
        message_repository,
        chat_repository.workflow_repository,
    )

    async def failing_stream(*args, **kwargs):
        raise RuntimeError('generation failed')
        yield  # pragma: no cover

    workflow_stub.workflow.stream.side_effect = failing_stream
    events = await send_message(
        chat_repository,
        project_client,
        3,
        9,
        123,
        CreateMessageDTO(None, SenderType.USER, 'hello', {}, {}),
        uow_factory=lambda: worker_uow,
    )

    assert [event async for event in events] == [
        {'event': 'error', 'data': {'message': 'generation failed'}}
    ]
    worker_uow.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_message_rolls_back_worker_uow_on_producer_cancellation(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    _configure_valid_send(chat_repository, message_repository, project_client)
    worker_uow = MockAgentsUnitOfWork(
        chat_repository.chat_repository,
        message_repository,
        chat_repository.workflow_repository,
    )

    async def cancelled_stream(*args, **kwargs):
        raise asyncio.CancelledError()
        yield  # pragma: no cover

    workflow_stub.workflow.stream.side_effect = cancelled_stream
    events = await send_message(
        chat_repository,
        project_client,
        3,
        9,
        123,
        CreateMessageDTO(None, SenderType.USER, 'hello', {}, {}),
        uow_factory=lambda: worker_uow,
    )

    with pytest.raises(asyncio.CancelledError):
        [event async for event in events]

    worker_uow.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_message_does_not_rollback_request_uow_on_producer_cancel(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    _configure_valid_send(chat_repository, message_repository, project_client)

    async def cancelled_stream(*args, **kwargs):
        raise asyncio.CancelledError()
        yield  # pragma: no cover

    workflow_stub.workflow.stream.side_effect = cancelled_stream
    events = await send_message(
        chat_repository,
        project_client,
        3,
        9,
        123,
        CreateMessageDTO(None, SenderType.USER, 'hello', {}, {}),
    )

    with pytest.raises(asyncio.CancelledError):
        [event async for event in events]

    chat_repository.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_release_background_task_logs_unhandled_task_error(caplog):
    async def fail():
        raise RuntimeError('background task failed')

    task = asyncio.create_task(fail())
    with pytest.raises(RuntimeError, match='background task failed'):
        await task

    chat_use_cases._release_background_task(task)

    assert 'Background chat task failed: error_type=RuntimeError' in caplog.text


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
            123,
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
            123,
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
            123,
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
    project_client.verify_resource_permission.return_value = False
    data = CreateMessageDTO(None, SenderType.USER, 'hello', {}, {})

    with pytest.raises(InsufficientProjectPermissionException):
        await send_message(
            chat_repository,
            project_client,
            3,
            9,
            123,
            data,
        )

    project_client.get_api_key.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_message_rejects_missing_api_key_before_engine_or_persist(
    chat_repository,
    message_repository,
    project_client,
    workflow_stub,
):
    _configure_valid_send(chat_repository, message_repository, project_client)
    project_client.get_api_key.side_effect = ApiKeyNotFoundException(123)
    data = CreateMessageDTO(None, SenderType.USER, 'hello', {}, {})

    with pytest.raises(ApiKeyNotFoundException):
        await send_message(
            chat_repository,
            project_client,
            3,
            9,
            123,
            data,
        )

    project_client.get_api_key.assert_awaited_once_with(4, 9, 123)
    chat_use_cases.create_llm_engine.assert_not_called()
    message_repository.create_human_message.assert_not_awaited()


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
    project_client.verify_resource_permission.return_value = True
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
            123,
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
        123,
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
        123,
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
        123,
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
        123,
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
        123,
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
    project_client.verify_resource_permission.return_value = True
    message_repository.get_messages_by_chat.side_effect = [
        CursorPage([], PaginationDTO(limit=1)),
        CursorPage([_message_dto(SenderType.USER)], PaginationDTO(limit=100)),
    ]
    events = await send_message(
        chat_repository,
        project_client,
        3,
        9,
        123,
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
    project_client.verify_resource_permission.return_value = True

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
    project_client.verify_resource_permission.return_value = True
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
    project_client.verify_resource_permission.return_value = True

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
    project_client.verify_resource_permission.return_value = True

    await delete_chat(chat_repository, project_client, 3, 9)

    chat_repository.delete_chat.assert_awaited_once_with(3)


@pytest.mark.asyncio
async def test_get_project_chats_returns_repository_page(
    chat_repository, project_client
):
    page = CursorPage([], PaginationDTO(limit=10))
    chat_repository.get_chats_by_project.return_value = page
    project_client.verify_resource_permission.return_value = True

    result = await get_project_chats(
        chat_repository, project_client, 4, 9, PaginationDTO(limit=10)
    )

    assert result == page
