from agents.dtos.page import CursorPage, PaginationDTO
from agents.dtos.workflow import WorkflowDTO
from agents.unit_of_work import IAgentsUnitOfWork
from core.logs import get_logger

logger = get_logger(__name__)


async def get_workflows(
    uow: IAgentsUnitOfWork, pagination: PaginationDTO
) -> CursorPage[WorkflowDTO]:
    page = await uow.workflow_repository.get_workflows(pagination)
    logger.debug('Retrieved workflows: count=%d', len(page.items))
    return page
