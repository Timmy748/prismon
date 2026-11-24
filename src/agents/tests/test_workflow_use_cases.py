import pytest

from agents.dtos.page import CursorPage, PaginationDTO
from agents.use_cases.workflows import get_workflow_config, get_workflows


@pytest.mark.asyncio
async def test_get_workflows_returns_repository_page(
    workflow_repository, workflow_uow
):
    pagination = PaginationDTO(limit=12)
    expected = CursorPage([], pagination)
    workflow_repository.get_workflows.return_value = expected

    result = await get_workflows(workflow_uow, pagination)

    assert result is expected


@pytest.mark.asyncio
async def test_get_workflows_forwards_pagination(
    workflow_repository, workflow_uow
):
    pagination = PaginationDTO(limit=12)

    await get_workflows(workflow_uow, pagination)

    workflow_repository.get_workflows.assert_awaited_once_with(pagination)


@pytest.mark.asyncio
async def test_get_workflow_config_returns_repository_config(
    workflow_repository, workflow_uow
):
    config = {'node': {'fields': ['question']}}
    workflow_repository.get_workflow_config.return_value = config

    result = await get_workflow_config(workflow_uow, 'chat')

    assert result == config
    workflow_repository.get_workflow_config.assert_awaited_once_with('chat')


@pytest.mark.asyncio
async def test_get_workflow_config_returns_none_for_missing_workflow(
    workflow_repository, workflow_uow
):
    workflow_repository.get_workflow_config.return_value = None

    result = await get_workflow_config(workflow_uow, 'missing')

    assert result is None
