from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Query

from agents.dtos.page import CursorPage
from agents.dtos.workflow import WorkflowDTO
from agents.schemas.page import PageSchema
from agents.schemas.workflow import WorkflowSchema
from agents.unit_of_work import (
    IAgentsUnitOfWork,
    create_agents_unit_of_work,
)
from agents.use_cases.workflows import get_workflow_config, get_workflows
from agents.utils.pagination import encode_cursor, pagination_dto
from infra.logs import get_logger

logger = get_logger(__name__)


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
    uow_factory: Callable[[], IAgentsUnitOfWork] = create_agents_unit_of_work,
) -> APIRouter:
    router = APIRouter(prefix='/workflows', tags=['workflows'])

    @router.get('/', response_model=PageSchema[WorkflowSchema])
    async def list_workflows(
        cursor: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> PageSchema[WorkflowSchema]:
        logger.info('Listing available workflows')
        async with uow_factory() as uow:
            page: CursorPage[WorkflowDTO] = await get_workflows(
                uow, pagination_dto(cursor, limit)
            )
        result = _workflow_page_schema(page)
        logger.info('Listed available workflows: count=%d', len(result.items))
        return result

    @router.get('/{name}/config', response_model=dict[str, object])
    async def workflow_config(name: str) -> dict[str, object]:
        async with uow_factory() as uow:
            config = await get_workflow_config(uow, name)
        if config is None:
            raise HTTPException(status_code=404, detail='Workflow not found')
        return config

    return router


router = create_workflow_routes()
