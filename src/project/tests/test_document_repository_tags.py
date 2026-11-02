# ruff: noqa: PLR2004
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from project.dtos.page import PaginationDTO
from project.dtos.tag import TagDTO
from project.entities.document import Document, DocumentStatus
from project.repositories.document import DocumentRepository

NOW = datetime.now(timezone.utc)


def _tag():
    return SimpleNamespace(
        id=9,
        project_id=2,
        label='Brand',
        description='Branding',
        color='#AABBCC',
    )


def _document(document_id=5, tags=None):
    return SimpleNamespace(
        id=document_id,
        project_id=2,
        created_by_member_id=1,
        file='document-key',
        name='Brief',
        file_extension=None,
        content_type=None,
        description='overview',
        status=DocumentStatus.DRAFT,
        created_at=NOW,
        updated_at=NOW,
        tags=list(tags or []),
    )


def _session(rows=()):
    session = MagicMock()
    result = MagicMock()
    result.all.return_value = list(rows)
    session.scalars = AsyncMock(return_value=result)
    session.get = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_document_repository_maps_attached_tags_on_get():
    session = _session()
    session.get.return_value = _document(tags=[_tag()])

    result = await DocumentRepository(session).get_document(5)

    assert result.tags == [TagDTO(9, 2, 'Brand', 'Branding', '#AABBCC')]


@pytest.mark.asyncio
async def test_document_repository_get_returns_none_for_missing_row():
    session = _session()

    result = await DocumentRepository(session).get_document(404)

    assert result is None


@pytest.mark.asyncio
async def test_document_repository_list_maps_tags_and_cursor():
    session = _session([_document(5, [_tag()]), _document(4)])

    result = await DocumentRepository(session).get_documents(
        2,
        PaginationDTO(limit=1, cursor=(NOW, 6)),
        name='Brief',
        status=DocumentStatus.DRAFT,
    )

    assert result.items[0].tags == [
        TagDTO(9, 2, 'Brand', 'Branding', '#AABBCC')
    ]
    assert result.pagination.more is True
    assert result.pagination.cursor == (NOW, 5)


@pytest.mark.asyncio
async def test_document_repository_list_returns_empty_page_without_cursor():
    session = _session()

    result = await DocumentRepository(session).get_documents(2)

    assert result.items == []
    assert result.pagination.cursor is None
    assert result.pagination.more is False


@pytest.mark.asyncio
async def test_document_repository_create_returns_empty_tag_list():
    session = _session()

    def refresh(row):
        row.id = 5
        row.created_at = NOW
        row.updated_at = NOW

    session.refresh.side_effect = refresh

    result = await DocumentRepository(session).create_document(
        2, 1, 'document-key', 'Brief', 'overview'
    )

    assert result.id == 5
    assert result.tags == []
    assert isinstance(session.add.call_args.args[0], Document)


@pytest.mark.asyncio
async def test_document_repository_update_keeps_and_maps_tags():
    session = _session()
    row = _document(tags=[_tag()])
    session.get.return_value = row

    result = await DocumentRepository(session).update_document(
        5,
        file='new-key',
        name='Updated brief',
        description='New description',
        status=DocumentStatus.PUBLISHED,
    )

    assert result.file == 'new-key'
    assert result.name == 'Updated brief'
    assert result.description == 'New description'
    assert result.status is DocumentStatus.PUBLISHED
    assert result.tags == [TagDTO(9, 2, 'Brand', 'Branding', '#AABBCC')]


@pytest.mark.asyncio
async def test_document_repository_update_returns_none_for_missing_row():
    session = _session()

    result = await DocumentRepository(session).update_document(404)

    assert result is None


@pytest.mark.asyncio
async def test_document_repository_delete_removes_existing_row():
    session = _session()
    row = _document()
    session.get.return_value = row

    await DocumentRepository(session).delete_document(5)

    session.delete.assert_awaited_once_with(row)


@pytest.mark.asyncio
async def test_document_repository_delete_ignores_missing_row():
    session = _session()

    await DocumentRepository(session).delete_document(404)

    session.delete.assert_not_awaited()
