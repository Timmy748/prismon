from agents.dtos.page import CursorPage, PaginationDTO
from agents.dtos.workflow import WorkflowDTO
from agents.repositories.workflow import IWorkflowRepository


async def get_workflows(
    workflow_repo: IWorkflowRepository, pagination: PaginationDTO
) -> CursorPage[WorkflowDTO]:
    return await workflow_repo.get_workflows(pagination)
