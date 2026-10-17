from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from agents.dtos.page import PaginationDTO
from agents.entities.workflow import Workflow
from agents.repositories.workflow import WorkflowRepository


@pytest.mark.asyncio
async def test_get_workflows_returns_empty_page(session: AsyncSession) -> None:
    repository = WorkflowRepository(session)

    page = await repository.get_workflows()

    assert (page.items, page.pagination.more, page.pagination.cursor) == (
        [],
        False,
        None,
    )


@pytest.mark.asyncio
async def test_get_workflows_maps_dtos_and_orders_desc(
    session: AsyncSession,
) -> None:
    repository = WorkflowRepository(session)
    workflows = await _create_workflows(session, 2)
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for index, workflow in enumerate(workflows):
        await session.execute(
            update(Workflow)
            .where(Workflow.id == workflow.id)
            .values(updated_at=base + timedelta(seconds=index))
        )
    await session.commit()

    page = await repository.get_workflows()

    assert [
        (item.id, item.name, item.description, item.version)
        for item in page.items
    ] == [
        (workflows[1].id, 'Workflow 1', 'Description 1', '1.0.0'),
        (workflows[0].id, 'Workflow 0', 'Description 0', '1.0.0'),
    ]


@pytest.mark.asyncio
async def test_get_workflows_returns_cursor_when_more_results(
    session: AsyncSession,
) -> None:
    repository = WorkflowRepository(session)
    workflows = await _create_workflows(session, 3)
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for index, workflow in enumerate(workflows):
        await session.execute(
            update(Workflow)
            .where(Workflow.id == workflow.id)
            .values(updated_at=base + timedelta(seconds=index))
        )
    await session.commit()

    page = await repository.get_workflows(PaginationDTO(limit=2))

    assert (
        [item.id for item in page.items],
        page.pagination.more,
        page.pagination.cursor,
    ) == (
        [workflows[2].id, workflows[1].id],
        True,
        (base + timedelta(seconds=1), workflows[1].id),
    )


@pytest.mark.asyncio
async def test_get_workflows_cursor_returns_following_page(
    session: AsyncSession,
) -> None:
    repository = WorkflowRepository(session)
    workflows = await _create_workflows(session, 3)
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for index, workflow in enumerate(workflows):
        await session.execute(
            update(Workflow)
            .where(Workflow.id == workflow.id)
            .values(updated_at=base + timedelta(seconds=index))
        )
    await session.commit()

    page = await repository.get_workflows(
        PaginationDTO(
            cursor=(workflows[1].updated_at, workflows[1].id), limit=2
        )
    )

    assert ([item.id for item in page.items], page.pagination.more) == (
        [workflows[0].id],
        False,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('requested_limit', 'expected_limit'), [(0, 1), (-5, 1), (101, 100)]
)
async def test_get_workflows_clamps_limit(
    session: AsyncSession, requested_limit: int, expected_limit: int
) -> None:
    repository = WorkflowRepository(session)

    page = await repository.get_workflows(PaginationDTO(limit=requested_limit))

    assert page.pagination.limit == expected_limit


async def _create_workflows(
    session: AsyncSession, count: int
) -> list[Workflow]:
    workflows = [
        Workflow(
            name=f'Workflow {index}',
            description=f'Description {index}',
            version='1.0.0',
        )
        for index in range(count)
    ]
    session.add_all(workflows)
    await session.commit()
    for workflow in workflows:
        await session.refresh(workflow)
    return workflows
