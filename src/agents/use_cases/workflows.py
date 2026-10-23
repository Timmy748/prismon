from agents.dtos.page import CursorPage, PaginationDTO
from agents.dtos.workflow import WorkflowDTO
from agents.unit_of_work import IAgentsUnitOfWork


async def get_workflows(
    uow: IAgentsUnitOfWork, pagination: PaginationDTO
) -> CursorPage[WorkflowDTO]:
    return await uow.workflow_repository.get_workflows(pagination)
