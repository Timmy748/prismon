# ruff: noqa: E501, PLR2004

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.dialects import postgresql

from project.entities.upload_intent import UploadIntent
from project.repositories.upload_intent import UploadIntentRepository


def _row(**overrides):
    values = {
        'id': 42,
        'project_id': 3,
        'asset_id': 7,
        'document_id': None,
        'object_key': 'uploads/staging',
        'final_file_key': 'projects/final',
        'started_by_member_id': 11,
        'target_status': 'active',
        'file_extension': 'svg',
        'content_type': 'image/svg+xml',
        'expires_at': datetime.now(UTC) + timedelta(minutes=5),
        'previous_file_key': 'projects/old',
        'created_at': datetime.now(UTC),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _session():
    session = Mock()
    session.add = Mock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.scalar = AsyncMock()
    session.scalars = AsyncMock()
    session.get = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_create_upload_intent_persists_and_returns_dto():
    session = _session()
    repository = UploadIntentRepository(session)

    result = await repository.create_upload_intent(
        3,
        asset_id=7,
        object_key='uploads/staging',
        final_file_key='projects/final',
        started_by_member_id=11,
        target_status='active',
        expires_at=datetime.now(UTC),
        file_extension='svg',
        content_type='image/svg+xml',
        previous_file_key='projects/old',
    )

    row = session.add.call_args.args[0]
    assert isinstance(row, UploadIntent)
    assert result.asset_id == 7
    assert result.document_id is None
    assert result.previous_file_key == 'projects/old'
    assert result.file_extension == 'svg'
    assert result.content_type == 'image/svg+xml'
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(row)


@pytest.mark.asyncio
async def test_get_by_object_key_maps_found_row_and_missing_row():
    session = _session()
    session.scalar.side_effect = [_row(), None]
    repository = UploadIntentRepository(session)

    found = await repository.get_by_object_key('uploads/staging')
    missing = await repository.get_by_object_key('missing')

    assert found is not None and found.object_key == 'uploads/staging'
    assert missing is None
    assert session.scalar.await_count == 2


@pytest.mark.asyncio
async def test_get_by_object_key_for_update_adds_row_lock():
    session = _session()
    session.scalar.return_value = _row()
    repository = UploadIntentRepository(session)

    result = await repository.get_by_object_key_for_update('uploads/staging')

    statement = session.scalar.await_args.args[0]
    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert result is not None
    assert 'FOR UPDATE' in compiled


@pytest.mark.asyncio
async def test_get_expired_intents_filters_cutoff_and_bounds_limit():
    session = _session()
    rows = [_row(), _row(object_key='uploads/second')]
    scalar_result = Mock()
    scalar_result.all.return_value = rows
    session.scalars.return_value = scalar_result
    repository = UploadIntentRepository(session)

    result = await repository.get_expired_upload_intents(
        datetime.now(UTC), limit=1000
    )

    statement = session.scalars.await_args.args[0]
    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert len(result) == 2
    assert result[0].object_key == 'uploads/staging'
    assert 'FOR UPDATE SKIP LOCKED' in compiled
    assert statement._limit_clause.value == 500


@pytest.mark.asyncio
async def test_expiration_limit_has_lower_bound():
    session = _session()
    scalar_result = Mock()
    scalar_result.all.return_value = []
    session.scalars.return_value = scalar_result
    repository = UploadIntentRepository(session)

    await repository.get_expired_upload_intents(datetime.now(UTC), limit=0)

    statement = session.scalars.await_args.args[0]
    assert statement._limit_clause.value == 1


@pytest.mark.asyncio
async def test_delete_removes_existing_intent_and_ignores_missing():
    session = _session()
    row = _row()
    session.get.side_effect = [row, None]
    repository = UploadIntentRepository(session)

    await repository.delete_upload_intent(row.id)
    await repository.delete_upload_intent(43)

    session.delete.assert_awaited_once_with(row)
    session.flush.assert_awaited_once()


def test_upload_intent_entity_has_single_resource_and_unique_pending_constraints():
    checks = [
        constraint.sqltext.text
        for constraint in UploadIntent.__table__.constraints
        if hasattr(constraint, 'sqltext')
    ]

    assert any(
        'asset_id IS NOT NULL' in sql and 'document_id IS NULL' in sql
        for sql in checks
    )
    assert UploadIntent.__table__.c.asset_id.unique is True
    assert UploadIntent.__table__.c.document_id.unique is True
    assert UploadIntent.__table__.c.object_key.unique is True
    assert UploadIntent.__table__.c.final_file_key.unique is True
