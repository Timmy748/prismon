from datetime import UTC, datetime
from http import HTTPStatus
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from agents.dtos.chat import ChatDTO
from agents.dtos.message import MessageDTO
from agents.dtos.page import CursorPage, PaginationDTO
from agents.dtos.user import UserDTO
from agents.entities.message import SenderType
from agents.exceptions import ChatNotFoundException
from agents.routes.chats import create_chat_routes
from agents.schemas.message import CreateMessageSchema
from agents.utils.pagination import encode_cursor
from project.permissions import ProjectPermission

CHAT_ID = 3


def _chat(chat_id: int = 3, title: str = 'Research') -> ChatDTO:
    now = datetime(2025, 1, 2, tzinfo=UTC)
    return ChatDTO(chat_id, title, 7, 11, now, now)


def _message(message_id: int = 5, chat_id: int = 3) -> MessageDTO:
    now = datetime(2025, 1, 2, tzinfo=UTC)
    return MessageDTO(
        message_id,
        chat_id,
        None,
        SenderType.USER,
        'hello',
        {},
        {},
        now,
        now,
    )


def test_list_chat_messages_returns_page_and_forwards_pagination(
    api_client,
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
    client = api_client(router)
    encoded_cursor = encode_cursor(cursor)

    response = client.get(
        '/chats/3/messages?limit=8&cursor=' + encoded_cursor,
        cookies={'jwt': 'token'},
    )

    assert (
        response.status_code == HTTPStatus.OK
        and response.json()
        == {
            'items': [
                {
                    'id': 5,
                    'chat_id': 3,
                    'parent_id': None,
                    'sender_type': 'user',
                    'text': 'hello',
                    'payload': {},
                    'meta_data': {},
                    'created_at': '2025-01-02T00:00:00Z',
                    'updated_at': '2025-01-02T00:00:00Z',
                }
            ],
            'limit': 8,
            'more': True,
            'cursor': encoded_cursor,
        }
        and message_repository.get_messages_by_chat.await_args.args[1]
        == PaginationDTO(cursor=cursor, limit=8)
    )


def test_list_chat_messages_rejects_missing_authentication(
    api_client,
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
    client = api_client(router)

    response = client.get('/chats/3/messages')

    assert (
        response.status_code == HTTPStatus.UNAUTHORIZED
        and response.json() == {'detail': ''}
    )


def test_list_chat_messages_maps_chat_not_found(
    api_client,
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
    client = api_client(router)

    response = client.get('/chats/3/messages', cookies={'jwt': 'token'})

    assert response.status_code == HTTPStatus.NOT_FOUND and response.json() == {
        'detail': 'Chat 3 not found'
    }


def test_list_chat_messages_rejects_invalid_cursor(
    api_client,
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
    client = api_client(router)

    response = client.get(
        '/chats/3/messages?cursor=invalid',
        cookies={'jwt': 'token'},
    )

    assert (
        response.status_code == HTTPStatus.BAD_REQUEST
        and response.json() == {'detail': 'Invalid cursor'}
    )


def test_post_message_to_existing_chat_returns_created_message(
    api_client,
    chat_repository,
    message_repository,
    identity_client,
    project_client,
):
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
    client = api_client(router)

    response = client.post(
        '/chats/messages',
        json={'chat_id': 3, 'text': 'hello'},
        cookies={'jwt': 'token'},
    )

    assert response.status_code == HTTPStatus.CREATED and response.json() == {
        'id': 5,
        'chat_id': 3,
        'parent_id': None,
        'sender_type': 'user',
        'text': 'hello',
        'payload': {},
        'meta_data': {},
        'created_at': '2025-01-02T00:00:00Z',
        'updated_at': '2025-01-02T00:00:00Z',
    }


def test_post_message_without_chat_creates_chat_and_message(
    api_client,
    chat_repository,
    message_repository,
    identity_client,
    project_client,
):
    chat_repository.create_chat.return_value = _chat()
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
    client = api_client(router)

    response = client.post(
        '/chats/messages',
        json={'project_id': 7, 'text': 'hello'},
        cookies={'jwt': 'token'},
    )

    assert (
        response.status_code == HTTPStatus.CREATED
        and response.json()['chat_id'] == CHAT_ID
    )


def test_post_message_requires_project_id_when_chat_is_omitted(
    api_client,
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
    client = api_client(router)

    response = client.post(
        '/chats/messages',
        json={'text': 'hello'},
        cookies={'jwt': 'token'},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


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
        await endpoint(
            SimpleNamespace(cookies={'jwt': 'token'}),
            data,
        )


def test_post_message_rejects_blank_text(
    api_client,
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
    client = api_client(router)

    response = client.post(
        '/chats/messages',
        json={'chat_id': 3, 'text': '  '},
        cookies={'jwt': 'token'},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_post_message_maps_permission_error(
    api_client,
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
    client = api_client(router)

    response = client.post(
        '/chats/messages',
        json={'chat_id': 3, 'text': 'hello'},
        cookies={'jwt': 'token'},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN and response.json() == {
        'detail': (
            'Missing project permission: '
            f'{ProjectPermission.CHAT_SEND_MESSAGE.value}'
        )
    }


def test_patch_chat_returns_updated_chat(
    api_client,
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
    client = api_client(router)

    response = client.patch(
        '/chats/3',
        json={'title': 'Updated'},
        cookies={'jwt': 'token'},
    )

    assert (
        response.status_code == HTTPStatus.OK
        and response.json()['title'] == 'Updated'
    )


def test_patch_chat_rejects_title_over_limit(
    api_client,
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
    client = api_client(router)

    response = client.patch(
        '/chats/3',
        json={'title': 'x' * 257},
        cookies={'jwt': 'token'},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_patch_chat_maps_missing_permission(
    api_client,
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
    client = api_client(router)

    response = client.patch(
        '/chats/3',
        json={'title': 'Updated'},
        cookies={'jwt': 'token'},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_delete_chat_returns_no_content(
    api_client,
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
    client = api_client(router)

    response = client.delete('/chats/3', cookies={'jwt': 'token'})

    assert (
        response.status_code == HTTPStatus.NO_CONTENT
        and response.content == b''
    )


def test_delete_chat_maps_chat_not_found(
    api_client,
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
    client = api_client(router)

    response = client.delete('/chats/3', cookies={'jwt': 'token'})

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_list_project_chats_returns_page(
    api_client,
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
    client = api_client(router)
    encoded_cursor = encode_cursor(cursor)

    response = client.get(
        '/projects/7/chats?cursor=' + encoded_cursor + '&limit=4',
        cookies={'jwt': 'token'},
    )

    assert response.status_code == HTTPStatus.OK and response.json() == {
        'items': [
            {
                'id': 3,
                'title': 'Research',
                'project_id': 7,
                'owner': 11,
                'created_at': '2025-01-02T00:00:00Z',
                'updated_at': '2025-01-02T00:00:00Z',
            }
        ],
        'limit': 4,
        'more': False,
        'cursor': encoded_cursor,
    }


def test_list_project_chats_maps_permission_error(
    api_client,
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
    client = api_client(router)

    response = client.get('/projects/7/chats', cookies={'jwt': 'token'})

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_list_project_chats_rejects_limit_out_of_range(
    api_client,
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
    client = api_client(router)

    response = client.get('/projects/7/chats?limit=101')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def _async_value(value):
    return value
