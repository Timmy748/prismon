# ruff: noqa: PLR2004
from datetime import datetime, timezone
from http import HTTPStatus

import pytest

from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.member import MemberRole, MemberStatus
from project.exceptions import TagNotFoundException

TAG_URL = '/projects/2/tags'
TAG_BODY = {
    'label': 'Brand',
    'description': 'Branding content',
    'color': '#AABBCC',
}


@pytest.mark.asyncio
async def test_list_tags_returns_tag_list(tag_client, tag_api):
    response = await tag_client.get(TAG_URL, cookies={'jwt': 'token'})

    assert response.status_code == HTTPStatus.OK
    assert response.json()['items'][0]['label'] == 'Brand'
    tag_api[5].get_tags.assert_awaited_once_with(2)


@pytest.mark.asyncio
async def test_create_tag_returns_created_tag(tag_client, tag_api):
    response = await tag_client.post(
        TAG_URL, json=TAG_BODY, cookies={'jwt': 'token'}
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['color'] == '#AABBCC'
    tag_api[5].create_tag.assert_awaited_once_with(
        2, 'Brand', 'Branding content', '#AABBCC'
    )


@pytest.mark.asyncio
async def test_update_tag_returns_updated_tag(tag_client, tag_api):
    response = await tag_client.put(
        f'{TAG_URL}/9',
        json={'label': 'Brand system'},
        cookies={'jwt': 'token'},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['id'] == 9
    tag_api[5].update_tag.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_tag_returns_no_content(tag_client, tag_api):
    response = await tag_client.delete(f'{TAG_URL}/9', cookies={'jwt': 'token'})

    assert response.status_code == HTTPStatus.NO_CONTENT
    tag_api[5].delete_tag.assert_awaited_once_with(9)


@pytest.mark.asyncio
async def test_list_asset_tags_returns_tag_list(tag_client, tag_api):
    response = await tag_client.get(
        '/projects/2/assets/4/tags', cookies={'jwt': 'token'}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['items'][0]['id'] == 9
    tag_api[5].get_asset_tags.assert_awaited_once_with(4)


@pytest.mark.asyncio
async def test_attach_tag_to_asset_returns_no_content(tag_client, tag_api):
    response = await tag_client.put(
        '/projects/2/assets/4/tags/9', cookies={'jwt': 'token'}
    )

    assert response.status_code == HTTPStatus.NO_CONTENT
    tag_api[5].attach_asset_tag.assert_awaited_once_with(4, 9)


@pytest.mark.asyncio
async def test_detach_tag_from_asset_returns_no_content(tag_client, tag_api):
    response = await tag_client.delete(
        '/projects/2/assets/4/tags/9', cookies={'jwt': 'token'}
    )

    assert response.status_code == HTTPStatus.NO_CONTENT
    tag_api[5].detach_asset_tag.assert_awaited_once_with(4, 9)


@pytest.mark.asyncio
async def test_list_document_tags_returns_tag_list(tag_client, tag_api):
    response = await tag_client.get(
        '/projects/2/documents/5/tags', cookies={'jwt': 'token'}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['items'][0]['id'] == 9
    tag_api[5].get_document_tags.assert_awaited_once_with(5)


@pytest.mark.asyncio
async def test_attach_tag_to_document_returns_no_content(tag_client, tag_api):
    response = await tag_client.put(
        '/projects/2/documents/5/tags/9', cookies={'jwt': 'token'}
    )

    assert response.status_code == HTTPStatus.NO_CONTENT
    tag_api[5].attach_document_tag.assert_awaited_once_with(5, 9)


@pytest.mark.asyncio
async def test_detach_tag_from_document_returns_no_content(tag_client, tag_api):
    response = await tag_client.delete(
        '/projects/2/documents/5/tags/9', cookies={'jwt': 'token'}
    )

    assert response.status_code == HTTPStatus.NO_CONTENT
    tag_api[5].detach_document_tag.assert_awaited_once_with(5, 9)


@pytest.mark.asyncio
async def test_tag_routes_require_authentication(tag_client, tag_api):
    response = await tag_client.get(TAG_URL)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    tag_api[6].get_current_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_tag_rejects_lower_rank_member(tag_client, tag_api):
    now = datetime.now(timezone.utc)
    tag_api[2].get_members.return_value = CursorPage(
        [MemberDTO(1, 2, MemberRole.MEMBER, MemberStatus.ACTIVE, 7, now, now)],
        PaginationDTO(limit=100),
    )

    response = await tag_client.post(
        TAG_URL, json=TAG_BODY, cookies={'jwt': 'token'}
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    tag_api[5].create_tag.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('method', 'path', 'body'),
    [
        ('get', TAG_URL, None),
        ('post', TAG_URL, TAG_BODY),
        ('put', f'{TAG_URL}/9', {'label': 'Changed'}),
        ('delete', f'{TAG_URL}/9', None),
        ('get', '/projects/2/assets/4/tags', None),
        ('put', '/projects/2/assets/4/tags/9', None),
        ('delete', '/projects/2/assets/4/tags/9', None),
        ('get', '/projects/2/documents/5/tags', None),
        ('put', '/projects/2/documents/5/tags/9', None),
        ('delete', '/projects/2/documents/5/tags/9', None),
    ],
)
async def test_tag_routes_map_domain_not_found_errors(
    tag_client, tag_api, method, path, body
):
    tag_api[1].get_project.return_value = None

    response = await tag_client.request(
        method.upper(), path, json=body, cookies={'jwt': 'token'}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_create_tag_rejects_invalid_hex_color(tag_client, tag_api):
    body = {**TAG_BODY, 'color': 'blue'}

    response = await tag_client.post(
        TAG_URL, json=body, cookies={'jwt': 'token'}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    tag_api[5].create_tag.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_tag_maps_missing_tag_to_not_found(tag_client, tag_api):
    tag_api[5].get_tag.return_value = None

    response = await tag_client.put(
        f'{TAG_URL}/404', json={'label': 'Changed'}, cookies={'jwt': 'token'}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail'] == str(TagNotFoundException(404))
