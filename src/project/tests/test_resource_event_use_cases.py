from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.resource_event import ResourceEventDTO
from project.use_cases.resource_events import (
    get_resource_events,
    record_resource_event,
)


@pytest.mark.asyncio
async def test_record_resource_event_forwards_event_to_repository():
    repository = SimpleNamespace(create_event=AsyncMock())
    uow = SimpleNamespace(resource_event_repository=repository)
    expected = ResourceEventDTO(
        id=4,
        project_id=3,
        resource_type='asset',
        resource_id=7,
        author_member_id=11,
        event_type='metadata_changed',
        data={'title': 'New title'},
        idempotency_key=None,
        created_at=None,
    )
    repository.create_event.return_value = expected

    result = await record_resource_event(
        uow,
        3,
        'asset',
        7,
        11,
        'metadata_changed',
        {'title': 'New title'},
    )

    assert result is expected
    repository.create_event.assert_awaited_once_with(
        3,
        'asset',
        7,
        11,
        'metadata_changed',
        {'title': 'New title'},
        idempotency_key=None,
    )


@pytest.mark.asyncio
async def test_get_resource_events_forwards_pagination_to_repository():
    pagination = PaginationDTO(limit=20)
    page = CursorPage([], pagination)
    repository = SimpleNamespace(get_events=AsyncMock(return_value=page))
    uow = SimpleNamespace(resource_event_repository=repository)

    result = await get_resource_events(uow, 3, 'document', 8, pagination)

    assert result is page
    repository.get_events.assert_awaited_once_with(3, 'document', 8, pagination)
