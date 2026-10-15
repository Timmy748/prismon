from datetime import UTC, datetime
from http import HTTPStatus

from agents.dtos.page import CursorPage, PaginationDTO
from agents.dtos.workflow import WorkflowDTO
from agents.routes.workflows import create_workflow_routes
from agents.utils.pagination import encode_cursor


async def _async_value(value):
    return value


def test_list_workflows_maps_page_to_http_response(
    api_client, workflow_repository
):
    timestamp = datetime(2025, 1, 2, tzinfo=UTC)
    cursor = (timestamp, 12)
    workflow_repository.get_workflows.return_value = CursorPage(
        [
            WorkflowDTO(
                12,
                'Research',
                'Analyze data',
                '/workflow.png',
                timestamp,
                timestamp,
            )
        ],
        PaginationDTO(cursor=cursor, limit=6, more=True),
    )
    router = create_workflow_routes(lambda: _async_value(workflow_repository))
    client = api_client(router)
    encoded_cursor = encode_cursor(cursor)

    response = client.get('/workflows/?limit=6&cursor=' + encoded_cursor)

    assert response.status_code == HTTPStatus.OK and response.json() == {
        'items': [
            {
                'id': 12,
                'name': 'Research',
                'description': 'Analyze data',
                'picture': '/workflow.png',
                'created_at': '2025-01-02T00:00:00Z',
                'updated_at': '2025-01-02T00:00:00Z',
            }
        ],
        'limit': 6,
        'more': True,
        'cursor': encoded_cursor,
    }


def test_list_workflows_rejects_invalid_cursor(api_client, workflow_repository):
    router = create_workflow_routes(lambda: _async_value(workflow_repository))
    client = api_client(router)

    response = client.get('/workflows/?cursor=invalid')

    assert (
        response.status_code == HTTPStatus.BAD_REQUEST
        and response.json() == {'detail': 'Invalid cursor'}
    )


def test_list_workflows_rejects_limit_above_maximum(
    api_client, workflow_repository
):
    router = create_workflow_routes(lambda: _async_value(workflow_repository))
    client = api_client(router)

    response = client.get('/workflows/?limit=101')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
