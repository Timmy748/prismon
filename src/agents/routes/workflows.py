from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Query

from agents.dtos.page import CursorPage
from agents.dtos.workflow import WorkflowDTO
from agents.repositories.workflow import IWorkflowRepository
from agents.schemas.page import PageSchema
from agents.schemas.workflow import WorkflowSchema
from agents.use_cases.workflows import get_workflows
from agents.utils.pagination import encode_cursor, pagination_dto


def _workflow_page_schema(
    page: CursorPage[WorkflowDTO],
) -> PageSchema[WorkflowSchema]:
    return PageSchema(
        items=[WorkflowSchema.from_dto(item) for item in page.items],
        limit=page.pagination.limit,
        more=page.pagination.more,
        cursor=encode_cursor(page.pagination.cursor),
    )


def create_workflow_routes(
    workflow_repository_factory: Callable[[], Awaitable[IWorkflowRepository]],
) -> APIRouter:
    router = APIRouter(prefix='/workflows', tags=['workflows'])

    @router.get('/', response_model=PageSchema[WorkflowSchema])
    async def list_workflows(
        cursor: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> PageSchema[WorkflowSchema]:
        page: CursorPage[WorkflowDTO] = await get_workflows(
            await workflow_repository_factory(), pagination_dto(cursor, limit)
        )
        return _workflow_page_schema(page)

    return router
