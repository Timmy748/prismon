from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from project.dtos.tag import TagDTO
from project.entities.tag import Tag, asset_tags, document_tags
from project.repositories.tag import TagRepository


def _row(
    tag_id=9,
    project_id=2,
    label='Brand',
    description='Branding',
    color='#AABBCC',
):
    return SimpleNamespace(
        id=tag_id,
        project_id=project_id,
        label=label,
        description=description,
        color=color,
    )


def _session(rows=()):
    session = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = list(rows)
    session.scalars = AsyncMock(return_value=scalars_result)
    session.get = AsyncMock()
    session.get.return_value = None
    session.scalar = AsyncMock()
    session.scalar.return_value = None
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_get_tag_returns_dto_when_row_exists():
    session = _session()
    session.get.return_value = _row()

    result = await TagRepository(session).get_tag(9)

    assert result == TagDTO(9, 2, 'Brand', 'Branding', '#AABBCC')


@pytest.mark.asyncio
async def test_get_tag_returns_none_when_row_is_missing():
    session = _session()

    result = await TagRepository(session).get_tag(404)

    assert result is None


@pytest.mark.asyncio
async def test_get_tags_returns_project_tags_in_repository_results():
    session = _session([_row(), _row(10, label='Logo')])

    result = await TagRepository(session).get_tags(2)

    assert result == [
        TagDTO(9, 2, 'Brand', 'Branding', '#AABBCC'),
        TagDTO(10, 2, 'Logo', 'Branding', '#AABBCC'),
    ]
    session.scalars.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_tag_persists_and_returns_saved_dto():
    session = _session()
    session.refresh.side_effect = lambda row: setattr(row, 'id', 9)

    result = await TagRepository(session).create_tag(
        2, 'Brand', 'Branding', '#AABBCC'
    )

    assert result == TagDTO(9, 2, 'Brand', 'Branding', '#AABBCC')
    added = session.add.call_args.args[0]
    assert isinstance(added, Tag)
    assert (added.project_id, added.label, added.description, added.color) == (
        2,
        'Brand',
        'Branding',
        '#AABBCC',
    )
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(added)


@pytest.mark.asyncio
async def test_update_tag_changes_provided_fields_and_returns_dto():
    session = _session()
    row = _row()
    session.get.return_value = row

    result = await TagRepository(session).update_tag(
        9,
        label='Brand system',
        description='New description',
        color='#112233',
    )

    assert result == TagDTO(9, 2, 'Brand system', 'New description', '#112233')
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(row)


@pytest.mark.asyncio
async def test_update_tag_returns_none_when_tag_is_missing():
    session = _session()

    result = await TagRepository(session).update_tag(404)

    assert result is None
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_tag_removes_existing_row():
    session = _session()
    row = _row()
    session.get.return_value = row

    await TagRepository(session).delete_tag(9)

    session.delete.assert_awaited_once_with(row)
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_tag_is_safe_when_row_is_missing():
    session = _session()

    await TagRepository(session).delete_tag(404)

    session.delete.assert_not_awaited()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_asset_tags_returns_linked_tag_dtos():
    session = _session([_row()])

    result = await TagRepository(session).get_asset_tags(4)

    assert result == [TagDTO(9, 2, 'Brand', 'Branding', '#AABBCC')]


@pytest.mark.asyncio
async def test_attach_asset_tag_inserts_missing_link():
    session = _session()

    await TagRepository(session).attach_asset_tag(4, 9)

    session.execute.assert_awaited_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_attach_asset_tag_does_not_duplicate_existing_link():
    session = _session()
    session.scalar.return_value = 9

    await TagRepository(session).attach_asset_tag(4, 9)

    session.execute.assert_not_awaited()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_detach_asset_tag_deletes_link():
    session = _session()

    await TagRepository(session).detach_asset_tag(4, 9)

    session.execute.assert_awaited_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_document_tags_returns_linked_tag_dtos():
    session = _session([_row()])

    result = await TagRepository(session).get_document_tags(5)

    assert result == [TagDTO(9, 2, 'Brand', 'Branding', '#AABBCC')]


@pytest.mark.asyncio
async def test_attach_document_tag_inserts_missing_link():
    session = _session()

    await TagRepository(session).attach_document_tag(5, 9)

    session.execute.assert_awaited_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_attach_document_tag_does_not_duplicate_existing_link():
    session = _session()
    session.scalar.return_value = 9

    await TagRepository(session).attach_document_tag(5, 9)

    session.execute.assert_not_awaited()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_detach_document_tag_deletes_link():
    session = _session()

    await TagRepository(session).detach_document_tag(5, 9)

    session.execute.assert_awaited_once()
    session.flush.assert_awaited_once()


def test_tag_association_foreign_keys_cascade_on_parent_deletion():
    assert {fk.ondelete for fk in asset_tags.foreign_keys} == {'CASCADE'}
    assert {fk.ondelete for fk in document_tags.foreign_keys} == {'CASCADE'}
