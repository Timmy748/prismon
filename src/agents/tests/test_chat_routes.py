# ruff: noqa: PLR0913, PLR0917
import json
from datetime import UTC, datetime
from http import HTTPStatus
from inspect import signature

import pytest
from fastapi import HTTPException, Request

import agents.routes.chats as chat_routes
from agents.dtos.chat import ChatDTO
from agents.dtos.message import MessageDTO
from agents.dtos.page import CursorPage, PaginationDTO
from agents.dtos.user import UserDTO
from agents.entities.message import SenderType
from agents.exceptions import ChatNotFoundException
from agents.routes.chats import create_chat_routes
from agents.schemas.chat import UpdateChatTitleSchema
from agents.schemas.message import CreateMessageSchema
from agents.utils.pagination import encode_cursor
from project.permissions import ProjectPermission

CHAT_ID = 3
PROJECT_ID = 7
MESSAGE_ID = 5
MESSAGE_PAGE_LIMIT = 8
CHAT_PAGE_LIMIT = 4
MAX_PAGE_LIMIT = 100


def _chat(chat_id: int = 3, title: str = 'Research') -> ChatDTO:
    now = datetime(2025, 1, 2, tzinfo=UTC)
    return ChatDTO(chat_id, title, 7, 11, now, now)


def _message(
    message_id: int = 5,
    chat_id: int = 3,
    parent_id: int | None = None,
    sender_type: SenderType = SenderType.USER,
    text: str = 'hello',
) -> MessageDTO:
    now = datetime(2025, 1, 2, tzinfo=UTC)
    return MessageDTO(
        message_id,
        chat_id,
        parent_id,
        sender_type,
        text,
        {},
        {},
        now,
        now,
    )


def _sse_events(body):
    events = []
    for block in body.strip().split('\n\n'):
        lines = block.splitlines()
        event_name = next(
            line[7:] for line in lines if line.startswith('event: ')
        )
        data = next(line[6:] for line in lines if line.startswith('data: '))
        events.append((event_name, json.loads(data)))
    return events


async def _post_message_stream(router, data):
    endpoint = next(
        route.endpoint
        for route in router.routes
        if route.path == '/chats/messages'
    )
    request = Request(
        {
            'type': 'http',
            'method': 'POST',
            'path': '/chats/messages',
            'headers': [(b'cookie', b'jwt=token')],
            'query_string': b'',
            'server': ('testserver', 80),
            'client': ('testclient', 50000),
            'scheme': 'http',
        }
    )
    response = await endpoint(request, data)
    body = ''.join([chunk async for chunk in response.body_iterator])
    return response, _sse_events(body)


def _endpoint(router, path, method):
    return next(
        route.endpoint
        for route in router.routes
        if route.path == path and method in route.methods
    )


def _request(cookies=None):
    cookie_header = '; '.join(
        f'{key}={value}' for key, value in (cookies or {}).items()
    ).encode()
    headers = [(b'cookie', cookie_header)] if cookie_header else []
    return Request(
        {
            'type': 'http',
            'method': 'GET',
            'path': '/',
            'headers': headers,
            'query_string': b'',
            'server': ('testserver', 80),
            'client': ('testclient', 50000),
            'scheme': 'http',
        }
    )


@pytest.mark.asyncio
async def test_list_chat_messages_returns_page_and_forwards_pagination(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
):
    cursor = (datetime(2025, 1, 2, tzinfo=UTC), 5)
    chat_repository.get_chat.return_value = _chat()
    message_repository.get_messages_by_chat.return_value = CursorPage(
        [_message()], PaginationDTO(cursor=cursor, limit=8, more=True)
    )
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )
    encoded_cursor = encode_cursor(cursor)

    result = await _endpoint(router, '/chats/{chat_id}/messages', 'GET')(
        _request({'jwt': 'token'}), 3, encoded_cursor, 8
    )

    assert (
        result.items[0].id == MESSAGE_ID
        and result.limit == MESSAGE_PAGE_LIMIT
        and result.more is True
        and result.cursor == encoded_cursor
        and message_repository.get_messages_by_chat.await_args.args[1]
        == PaginationDTO(cursor=cursor, limit=MESSAGE_PAGE_LIMIT)
    )


@pytest.mark.asyncio
async def test_list_chat_messages_rejects_missing_authentication(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
):
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )
    response = await _endpoint(router, '/chats/{chat_id}/messages', 'GET')(
        _request(), 3, None, 50
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED and json.loads(
        response.body
    ) == {'detail': ''}


@pytest.mark.asyncio
async def test_list_chat_messages_maps_chat_not_found(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
):
    chat_repository.get_chat.side_effect = ChatNotFoundException(3)
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )
    response = await _endpoint(router, '/chats/{chat_id}/messages', 'GET')(
        _request({'jwt': 'token'}), 3, None, 50
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert json.loads(response.body) == {'detail': 'Chat 3 not found'}


@pytest.mark.asyncio
async def test_list_chat_messages_rejects_invalid_cursor(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
):
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )
    with pytest.raises(HTTPException) as error:
        await _endpoint(router, '/chats/{chat_id}/messages', 'GET')(
            _request({'jwt': 'token'}), 3, 'invalid', 50
        )

    assert error.value.status_code == HTTPStatus.BAD_REQUEST
    assert error.value.detail == 'Invalid cursor'


@pytest.mark.asyncio
async def test_post_message_to_existing_chat_streams_tokens_and_saved_message(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
    workflow_stub,
):
    chat_repository.get_chat.return_value = _chat()
    message_repository.get_messages_by_chat.return_value = CursorPage(
        [], PaginationDTO(limit=1)
    )
    message_repository.create_human_message.return_value = _message()
    message_repository.create_ai_message.return_value = _message(
        message_id=6,
        parent_id=None,
        sender_type=SenderType.ASSISTANT,
        text='answer',
    )
    project_client.has_permission.return_value = True
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )
    response, events = await _post_message_stream(
        router, CreateMessageSchema(chat_id=3, text='hello')
    )

    assert response.status_code == HTTPStatus.OK
    assert response.media_type == 'text/event-stream'
    assert response.headers['cache-control'] == 'no-cache'
    assert [name for name, _ in events] == ['token', 'token', 'done']
    assert [data for name, data in events if name == 'token'] == [
        'ans',
        'wer',
    ]
    assert events[-1][1] == {
        'id': 6,
        'chat_id': 3,
        'parent_id': None,
        'sender_type': 'assistant',
        'text': 'answer',
        'payload': {},
        'meta_data': {},
        'created_at': '2025-01-02T00:00:00Z',
        'updated_at': '2025-01-02T00:00:00Z',
    }


@pytest.mark.asyncio
async def test_post_message_without_chat_streams_created_chat_event(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
    workflow_stub,
):
    chat_repository.create_chat.return_value = _chat()
    chat_repository.get_chat.return_value = _chat()
    message_repository.get_messages_by_chat.return_value = CursorPage(
        [], PaginationDTO(limit=1)
    )
    message_repository.create_human_message.return_value = _message()
    message_repository.create_ai_message.return_value = _message(
        message_id=6,
        parent_id=None,
        sender_type=SenderType.ASSISTANT,
        text='answer',
    )
    project_client.has_permission.return_value = True
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )
    response, events = await _post_message_stream(
        router, CreateMessageSchema(project_id=PROJECT_ID, text='hello')
    )

    assert response.status_code == HTTPStatus.OK
    assert [name for name, _ in events] == ['chat', 'token', 'token', 'done']
    assert events[0][1]['id'] == CHAT_ID
    assert events[0][1]['project_id'] == PROJECT_ID


@pytest.mark.asyncio
async def test_post_message_streams_generation_error_as_sse(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
    workflow_stub,
):
    async def failing_generation(*args, **kwargs):
        raise RuntimeError('generation failed')
        yield  # Make this an async generator that fails when consumed.

    workflow_stub.workflow.stream.side_effect = failing_generation
    chat_repository.get_chat.return_value = _chat()
    message_repository.get_messages_by_chat.return_value = CursorPage(
        [], PaginationDTO(limit=1)
    )
    message_repository.create_human_message.return_value = _message()
    project_client.has_permission.return_value = True
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )

    response, events = await _post_message_stream(
        router, CreateMessageSchema(chat_id=3, text='hello')
    )

    assert response.status_code == HTTPStatus.OK
    assert events == [('error', {'message': 'generation failed'})]


@pytest.mark.asyncio
async def test_post_message_stream_converts_chat_dto_event(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
    workflow_stub,
    monkeypatch,
):
    chat_repository.get_chat.return_value = _chat()
    project_client.has_permission.return_value = True
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )

    async def message_events(*args, **kwargs):
        async def events():
            yield {'event': 'chat', 'data': _chat()}

        return events()

    monkeypatch.setattr(chat_routes, 'send_message', message_events)
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )

    response, events = await _post_message_stream(
        router, CreateMessageSchema(chat_id=3, text='hello')
    )

    assert response.status_code == HTTPStatus.OK
    assert events == [
        (
            'chat',
            {
                'id': 3,
                'title': 'Research',
                'project_id': 7,
                'owner': 11,
                'created_at': '2025-01-02T00:00:00Z',
                'updated_at': '2025-01-02T00:00:00Z',
            },
        )
    ]


@pytest.mark.parametrize(
    ('failure', 'expected'),
    [
        (ChatNotFoundException(3), {'detail': 'Chat 3 not found'}),
        (RuntimeError('stream failed'), {'detail': 'stream failed'}),
    ],
)
@pytest.mark.asyncio
async def test_post_message_stream_converts_iteration_exception_to_sse(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
    monkeypatch,
    failure,
    expected,
):
    chat_repository.get_chat.return_value = _chat()
    project_client.has_permission.return_value = True
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )

    async def message_events(*args, **kwargs):
        async def events():
            raise failure
            yield

        return events()

    monkeypatch.setattr(chat_routes, 'send_message', message_events)
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )

    response, events = await _post_message_stream(
        router, CreateMessageSchema(chat_id=3, text='hello')
    )

    assert response.status_code == HTTPStatus.OK
    assert events == [('error', expected)]


@pytest.mark.asyncio
async def test_list_chat_messages_endpoint_returns_page_directly(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
):
    chat_repository.get_chat.return_value = _chat()
    message_repository.get_messages_by_chat.return_value = CursorPage(
        [_message()], PaginationDTO(limit=1)
    )
    project_client.has_permission.return_value = True
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )

    result = await _endpoint(router, '/chats/{chat_id}/messages', 'GET')(
        _request({'jwt': 'token'}), 3, None, 1
    )

    assert result.items[0].id == MESSAGE_ID
    assert result.limit == 1
    assert result.cursor is None


@pytest.mark.asyncio
async def test_patch_chat_endpoint_returns_updated_chat_directly(
    chat_repository,
    identity_client,
    project_client,
):
    chat_repository.get_chat.return_value = _chat()
    chat_repository.update_chat_title.return_value = _chat(title='Updated')
    project_client.has_permission.return_value = True
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(None),
        lambda: identity_client,
        lambda: project_client,
    )

    result = await _endpoint(router, '/chats/{chat_id}', 'PATCH')(
        _request({'jwt': 'token'}), 3, UpdateChatTitleSchema(title='Updated')
    )

    assert result.title == 'Updated'


@pytest.mark.asyncio
async def test_delete_chat_endpoint_returns_no_content_directly(
    chat_repository,
    identity_client,
    project_client,
):
    chat_repository.get_chat.return_value = _chat()
    project_client.has_permission.return_value = True
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(None),
        lambda: identity_client,
        lambda: project_client,
    )

    result = await _endpoint(router, '/chats/{chat_id}', 'DELETE')(
        _request({'jwt': 'token'}), 3
    )

    assert result.status_code == HTTPStatus.NO_CONTENT


@pytest.mark.asyncio
async def test_list_project_chats_endpoint_returns_page_directly(
    chat_repository, identity_client, project_client
):
    chat_repository.get_chats_by_project.return_value = CursorPage(
        [_chat()], PaginationDTO(limit=1)
    )
    project_client.has_permission.return_value = True
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(None),
        lambda: identity_client,
        lambda: project_client,
    )

    result = await _endpoint(router, '/projects/{project_id}/chats', 'GET')(
        _request({'jwt': 'token'}), 7, None, 1
    )

    assert result.items[0].id == CHAT_ID
    assert result.cursor is None


@pytest.mark.asyncio
async def test_list_chat_messages_endpoint_maps_missing_auth_directly(
    chat_repository, message_repository, identity_client, project_client
):
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )

    result = await _endpoint(router, '/chats/{chat_id}/messages', 'GET')(
        _request(), 3, None, 50
    )

    assert result.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize(
    ('path', 'method', 'function_name', 'args'),
    [
        (
            '/chats/{chat_id}/messages',
            'GET',
            'get_chat_messages',
            (3, None, 50),
        ),
        ('/chats/{chat_id}', 'PATCH', 'update_chat_title', (3,)),
        ('/chats/{chat_id}', 'DELETE', 'delete_chat', (3,)),
        (
            '/projects/{project_id}/chats',
            'GET',
            'get_project_chats',
            (7, None, 50),
        ),
    ],
)
@pytest.mark.asyncio
async def test_chat_routes_map_use_case_errors_directly(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
    monkeypatch,
    path,
    method,
    function_name,
    args,
):
    async def fail(*call_args, **call_kwargs):
        raise ChatNotFoundException(3)

    monkeypatch.setattr(chat_routes, function_name, fail)
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )
    endpoint = _endpoint(router, path, method)
    payload = (
        UpdateChatTitleSchema(title='Updated') if method == 'PATCH' else None
    )
    result = await endpoint(
        _request({'jwt': 'token'}),
        *args[:1],
        *(tuple([payload]) if method == 'PATCH' else ()),
        *args[1:],
    )

    assert result.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_post_message_endpoint_maps_setup_error_directly(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
    monkeypatch,
):
    async def fail(*args, **kwargs):
        raise ChatNotFoundException(CHAT_ID)

    monkeypatch.setattr(chat_routes, 'send_message', fail)
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )

    result = await _endpoint(router, '/chats/messages', 'POST')(
        _request({'jwt': 'token'}),
        CreateMessageSchema(chat_id=CHAT_ID, text='x'),
    )

    assert result.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_post_message_defensive_project_id_check(
    chat_repository, message_repository, identity_client, project_client
):
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )
    endpoint = next(
        route.endpoint
        for route in router.routes
        if route.path == '/chats/messages'
    )
    data = CreateMessageSchema.model_construct(
        chat_id=None, project_id=None, text='hello'
    )

    with pytest.raises(HTTPException, match='project_id is required'):
        await endpoint(_request({'jwt': 'token'}), data)


@pytest.mark.asyncio
async def test_post_message_maps_permission_error(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
):
    chat_repository.get_chat.return_value = _chat()
    project_client.has_permission.return_value = False
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )
    response = await _endpoint(router, '/chats/messages', 'POST')(
        _request({'jwt': 'token'}),
        CreateMessageSchema(chat_id=3, text='hello'),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert json.loads(response.body) == {
        'detail': (
            'Missing project permission: '
            f'{ProjectPermission.CHAT_SEND_MESSAGE.value}'
        )
    }


@pytest.mark.asyncio
async def test_patch_chat_returns_updated_chat(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
):
    chat_repository.get_chat.return_value = _chat()
    chat_repository.update_chat_title.return_value = _chat(title='Updated')
    project_client.has_permission.return_value = True
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )
    response = await _endpoint(router, '/chats/{chat_id}', 'PATCH')(
        _request({'jwt': 'token'}), 3, UpdateChatTitleSchema(title='Updated')
    )

    assert response.title == 'Updated'


@pytest.mark.asyncio
async def test_patch_chat_rejects_title_over_limit(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
):
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )
    response = await _endpoint(router, '/chats/{chat_id}', 'PATCH')(
        _request({'jwt': 'token'}),
        3,
        UpdateChatTitleSchema.model_construct(title='x' * 257),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert json.loads(response.body) == {
        'detail': 'Chat title must contain 1 to 256 characters'
    }


@pytest.mark.asyncio
async def test_patch_chat_maps_missing_permission(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
):
    chat_repository.get_chat.return_value = _chat()
    project_client.has_permission.return_value = False
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )
    response = await _endpoint(router, '/chats/{chat_id}', 'PATCH')(
        _request({'jwt': 'token'}), 3, UpdateChatTitleSchema(title='Updated')
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_delete_chat_returns_no_content(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
):
    chat_repository.get_chat.return_value = _chat()
    project_client.has_permission.return_value = True
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )
    response = await _endpoint(router, '/chats/{chat_id}', 'DELETE')(
        _request({'jwt': 'token'}), 3
    )

    assert (
        response.status_code == HTTPStatus.NO_CONTENT and response.body == b''
    )


@pytest.mark.asyncio
async def test_delete_chat_maps_chat_not_found(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
):
    chat_repository.get_chat.side_effect = ChatNotFoundException(3)
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )
    response = await _endpoint(router, '/chats/{chat_id}', 'DELETE')(
        _request({'jwt': 'token'}), 3
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_list_project_chats_returns_page(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
):
    cursor = (datetime(2025, 1, 2, tzinfo=UTC), 3)
    chat_repository.get_chats_by_project.return_value = CursorPage(
        [_chat()], PaginationDTO(cursor=cursor, limit=4, more=False)
    )
    project_client.has_permission.return_value = True
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )
    encoded_cursor = encode_cursor(cursor)

    result = await _endpoint(router, '/projects/{project_id}/chats', 'GET')(
        _request({'jwt': 'token'}), 7, encoded_cursor, 4
    )

    assert result.items[0].id == CHAT_ID
    assert result.limit == CHAT_PAGE_LIMIT
    assert result.cursor == encoded_cursor


@pytest.mark.asyncio
async def test_list_project_chats_maps_permission_error(
    chat_repository,
    message_repository,
    identity_client,
    project_client,
):
    project_client.has_permission.return_value = False
    identity_client.get_current_user.return_value = UserDTO(
        11, 'ana', 'a@example.com'
    )
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )
    response = await _endpoint(router, '/projects/{project_id}/chats', 'GET')(
        _request({'jwt': 'token'}), 7, None, 50
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_list_project_chats_rejects_limit_out_of_range(
    chat_repository, message_repository, identity_client, project_client
):
    router = create_chat_routes(
        lambda: _async_value(chat_repository),
        lambda: _async_value(message_repository),
        lambda: identity_client,
        lambda: project_client,
    )
    endpoint = _endpoint(router, '/projects/{project_id}/chats', 'GET')
    limit_parameter = next(
        parameter
        for parameter in signature(endpoint).parameters.values()
        if parameter.name == 'limit'
    )

    lower_bounds = [
        constraint.ge
        for constraint in limit_parameter.default.metadata
        if hasattr(constraint, 'ge')
    ]
    upper_bounds = [
        constraint.le
        for constraint in limit_parameter.default.metadata
        if hasattr(constraint, 'le')
    ]

    assert lower_bounds == [1]
    assert upper_bounds == [MAX_PAGE_LIMIT]


async def _async_value(value):
    return value
