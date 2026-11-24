from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from agents.dtos.page import CursorPage, PaginationDTO
from agents.dtos.workflow import WorkflowDTO
from agents.routes.workflows import create_workflow_routes
from agents.utils.pagination import encode_cursor


def _app_with_router(router: APIRouter) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


async def _get(router: APIRouter, path: str):
    async with AsyncClient(
        transport=ASGITransport(app=_app_with_router(router)),
        base_url='http://test',
    ) as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_list_workflows_maps_page_to_http_response(
    workflow_repository, workflow_uow
):
    timestamp = datetime(2025, 1, 2, tzinfo=UTC)
    cursor = (timestamp, 12)
    workflow_repository.get_workflows.return_value = CursorPage(
        [
            WorkflowDTO(
                12,
                'Research',
                'Analyze data',
                '1.0.0',
                timestamp,
                timestamp,
            )
        ],
        PaginationDTO(cursor=cursor, limit=6, more=True),
    )
    router = create_workflow_routes(lambda: workflow_uow)
    encoded_cursor = encode_cursor(cursor)

    response = await _get(
        router, '/workflows/?limit=6&cursor=' + encoded_cursor
    )

    assert response.status_code == HTTPStatus.OK and response.json() == {
        'items': [
            {
                'id': 12,
                'name': 'Research',
                'description': 'Analyze data',
                'version': '1.0.0',
                'config': {},
                'created_at': '2025-01-02T00:00:00Z',
                'updated_at': '2025-01-02T00:00:00Z',
            }
        ],
        'limit': 6,
        'more': True,
        'cursor': encoded_cursor,
    }


@pytest.mark.asyncio
async def test_list_workflows_rejects_invalid_cursor(
    workflow_repository, workflow_uow
):
    router = create_workflow_routes(lambda: workflow_uow)

    response = await _get(router, '/workflows/?cursor=invalid')

    assert (
        response.status_code == HTTPStatus.BAD_REQUEST
        and response.json() == {'detail': 'Invalid cursor'}
    )


@pytest.mark.asyncio
async def test_list_workflows_rejects_limit_above_maximum(
    workflow_repository, workflow_uow
):
    router = create_workflow_routes(lambda: workflow_uow)

    response = await _get(router, '/workflows/?limit=101')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_get_workflow_config_returns_config(
    workflow_repository, workflow_uow
):
    config = {'retrieve_context': {'fields': ['project_id']}}
    workflow_repository.get_workflow_config.return_value = config

    response = await _get(
        create_workflow_routes(lambda: workflow_uow), '/workflows/chat/config'
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == config


@pytest.mark.asyncio
async def test_get_workflow_config_returns_not_found_for_missing_workflow(
    workflow_repository, workflow_uow
):
    workflow_repository.get_workflow_config.return_value = None

    response = await _get(
        create_workflow_routes(lambda: workflow_uow),
        '/workflows/missing/config',
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {'detail': 'Workflow not found'}
