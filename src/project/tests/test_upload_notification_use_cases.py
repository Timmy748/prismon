from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from project.use_cases.upload_notifications import should_finalize_upload


def _unit_of_work(*, intent=None, event=None):
    return SimpleNamespace(
        upload_intent_repository=SimpleNamespace(
            get_by_object_key=AsyncMock(return_value=intent)
        ),
        resource_event_repository=SimpleNamespace(
            get_by_idempotency_key=AsyncMock(return_value=event)
        ),
    )


@pytest.mark.asyncio
async def test_known_intent_should_be_finalized_without_event_lookup():
    uow = _unit_of_work(intent=object())

    result = await should_finalize_upload(uow, 'uploads/staging-key')

    assert result is True
    uow.upload_intent_repository.get_by_object_key.assert_awaited_once_with(
        'uploads/staging-key'
    )
    uow.resource_event_repository.get_by_idempotency_key.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('event_type', ['file_changed', 'upload_failed'])
async def test_terminal_event_should_be_finalized_for_cleanup(event_type):
    uow = _unit_of_work(event=SimpleNamespace(event_type=event_type))

    result = await should_finalize_upload(uow, 'uploads/staging-key')

    assert result is True
    uow.upload_intent_repository.get_by_object_key.assert_awaited_once_with(
        'uploads/staging-key'
    )
    uow.resource_event_repository.get_by_idempotency_key.assert_awaited_once_with(
        'uploads/staging-key'
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'event',
    [None, SimpleNamespace(event_type='metadata_changed')],
    ids=['unknown-upload', 'unrelated-event'],
)
async def test_unknown_or_unrelated_event_should_not_be_finalized(event):
    uow = _unit_of_work(event=event)

    result = await should_finalize_upload(uow, 'uploads/staging-key')

    assert result is False
    uow.upload_intent_repository.get_by_object_key.assert_awaited_once_with(
        'uploads/staging-key'
    )
    uow.resource_event_repository.get_by_idempotency_key.assert_awaited_once_with(
        'uploads/staging-key'
    )
