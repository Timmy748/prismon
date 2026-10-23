import pytest

from agents.dtos.page import CursorPage, PaginationDTO
from agents.use_cases.workflows import get_workflows


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
