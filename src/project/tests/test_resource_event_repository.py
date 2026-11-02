# ruff: noqa: PLR2004

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.exc import IntegrityError

from project.dtos.page import PaginationDTO
from project.entities.resource_event import ProjectResourceEvent
from project.repositories.resource_event import ProjectResourceEventRepository


class Savepoint:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _session():
    session = Mock()
    session.scalar = AsyncMock(return_value=None)
    session.scalars = AsyncMock()
    session.add = Mock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.begin_nested = Mock(return_value=Savepoint())
    return session


def _row(index=1, **overrides):
    values = {
        'id': index,
        'project_id': 3,
        'resource_type': 'asset',
        'resource_id': 21,
        'author_member_id': 11,
        'event_type': 'metadata_changed',
        'data': {'title': 'new title'},
        'idempotency_key': 'uploads/staging',
        'created_at': datetime(2025, 1, 1, tzinfo=UTC)
        + timedelta(minutes=index),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_create_event_saves_and_maps_event():
    session = _session()
    repository = ProjectResourceEventRepository(session)

    event = await repository.create_event(
        3, 'asset', 21, 11, 'metadata_changed', {'title': 'new title'}, 'key'
    )

    row = session.add.call_args.args[0]
    assert isinstance(row, ProjectResourceEvent)
    assert event.project_id == 3
    assert event.data == {'title': 'new title'}
    assert event.idempotency_key == 'key'
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(row)


@pytest.mark.asyncio
async def test_create_event_returns_existing_idempotency_record():
    session = _session()
    existing_row = _row()
    session.scalar.return_value = existing_row
    repository = ProjectResourceEventRepository(session)

    result = await repository.create_event(
        3, 'asset', 21, 12, 'other', {}, 'key'
    )

    assert result.id == existing_row.id
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_lookup_aliases_return_event_and_unknown_key_none():
    session = _session()
    row = _row()
    session.scalar.side_effect = [row, row, None]
    repository = ProjectResourceEventRepository(session)

    assert (await repository.get_event_by_idempotency_key('key')).id == row.id
    assert (await repository.get_by_idempotency_key('key')).id == row.id
    assert await repository.get_by_idempotency_key('unknown') is None


@pytest.mark.asyncio
async def test_create_event_race_returns_record_found_after_integrity_error(
    monkeypatch,
):
    session = _session()
    session.scalar.side_effect = [None, _row()]
    error = IntegrityError('insert', {}, Exception('duplicate'))

    class FailingSavepoint:
        async def __aenter__(self):
            raise error

        async def __aexit__(self, *args):
            return False

    session.begin_nested.return_value = FailingSavepoint()
    repository = ProjectResourceEventRepository(session)

    result = await repository.create_event(
        3, 'asset', 21, 11, 'changed', {}, 'key'
    )

    assert result.id == 1
    assert session.scalar.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('idempotency_key', [None, 'key'])
async def test_create_event_propagates_integrity_error_without_race_record(
    idempotency_key,
):
    session = _session()
    error = IntegrityError('insert', {}, Exception('bad insert'))

    class FailingSavepoint:
        async def __aenter__(self):
            raise error

        async def __aexit__(self, *args):
            return False

    session.begin_nested.return_value = FailingSavepoint()
    repository = ProjectResourceEventRepository(session)

    with pytest.raises(IntegrityError) as raised:
        await repository.create_event(
            3, 'asset', 21, 11, 'changed', {}, idempotency_key
        )

    assert raised.value is error


@pytest.mark.asyncio
async def test_get_events_orders_and_returns_next_cursor():
    session = _session()
    rows = [_row(3), _row(2), _row(1)]
    result = Mock()
    result.all.return_value = rows
    session.scalars.return_value = result
    repository = ProjectResourceEventRepository(session)

    page = await repository.get_events(3, 'asset', 21, PaginationDTO(limit=2))

    assert [event.id for event in page.items] == [3, 2]
    assert page.pagination.more is True
    assert page.pagination.cursor == (rows[1].created_at, rows[1].id)
    assert session.scalars.await_args.args[0]._limit_clause.value == 3


@pytest.mark.asyncio
async def test_get_events_applies_cursor_and_clamps_limit():
    session = _session()
    rows = [_row()]
    result = Mock()
    result.all.return_value = rows
    session.scalars.return_value = result
    repository = ProjectResourceEventRepository(session)
    cursor = (datetime(2025, 1, 2, tzinfo=UTC), 8)

    page = await repository.get_events(
        3, 'asset', 21, PaginationDTO(cursor=cursor, limit=500)
    )

    statement = session.scalars.await_args.args[0]
    assert statement._limit_clause.value == 101
    assert len(statement._where_criteria) == 4
    assert page.pagination.limit == 100
    assert page.pagination.more is False
    assert page.pagination.cursor is None


@pytest.mark.asyncio
async def test_get_events_returns_empty_page_with_lower_clamped_limit():
    session = _session()
    result = Mock()
    result.all.return_value = []
    session.scalars.return_value = result
    repository = ProjectResourceEventRepository(session)

    page = await repository.get_events(3, 'document', 4, PaginationDTO(limit=0))

    assert page.items == []
    assert page.pagination.limit == 1
    assert page.pagination.more is False
