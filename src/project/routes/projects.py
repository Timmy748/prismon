# ruff: noqa: PLR0913, PLR0917
from collections.abc import Callable
from http import HTTPStatus

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from core.logs import get_logger
from project.clients.client_user import IUserClient
from project.dtos.project import CreateProjectDTO, ProjectDTO, UpdateProjectDTO
from project.exceptions import (
    ProjectException,
    ProjectUserAuthenticationException,
)
from project.handlers.errors import handle_project_error
from project.schemas.project import (
    CreateProjectSchema,
    ProjectSchema,
    UpdateProjectSchema,
)
from project.unit_of_work import IProjectUnitOfWork
from project.use_cases.project import (
    create_project,
    delete_project,
    get_projects,
    update_project,
)
from project.utils.pagination import PageSchema, page_schema, pagination_dto

logger = get_logger(__name__)


def create_project_router(
    unit_of_work_factory: Callable[[], IProjectUnitOfWork],
    user_client_factory: Callable[[], IUserClient],
) -> APIRouter:
    router = APIRouter(prefix='/projects', tags=['projects'])

    async def resolve_current_user(cookies):
        access_token = cookies.get('jwt')
        if not access_token:
            raise ProjectUserAuthenticationException()
        return await user_client_factory().get_current_user(access_token)

    @router.get('', response_model=PageSchema[ProjectSchema])
    async def get_project_list(
        request: Request,
        name: str | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = None,
    ) -> PageSchema[ProjectSchema] | JSONResponse:
        logger.info('Project route started: operation=list')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                page = await get_projects(
                    unit_of_work,
                    user.id,
                    name,
                    pagination_dto(cursor, limit),
                )
            result = page_schema(page)
            logger.info(
                'Project route completed: operation=list item_count=%s',
                len(page.items),
            )
            return result
        except ProjectException as error:
            return handle_project_error(error)

    @router.post(
        '', response_model=ProjectSchema, status_code=HTTPStatus.CREATED
    )
    async def post_project(
        request: Request,
        data: CreateProjectSchema,
    ) -> ProjectDTO | JSONResponse:
        logger.info('Project route started: operation=create')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                project = await create_project(
                    unit_of_work,
                    user.id,
                    CreateProjectDTO(name=data.name, owner=str(user.id)),
                )
            logger.info('Project route completed: operation=create')
            return project
        except ProjectException as error:
            return handle_project_error(error)

    @router.put('/{public_id}', response_model=ProjectSchema)
    async def put_project(
        request: Request,
        public_id: int,
        data: UpdateProjectSchema,
    ) -> ProjectDTO | JSONResponse:
        logger.info('Project route started: operation=update')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                project = await update_project(
                    unit_of_work,
                    public_id,
                    user.id,
                    UpdateProjectDTO(name=data.name),
                )
            logger.info('Project route completed: operation=update')
            return project
        except ProjectException as error:
            return handle_project_error(error)

    @router.delete(
        '/{public_id}', status_code=HTTPStatus.NO_CONTENT, response_model=None
    )
    async def remove_project(
        request: Request,
        public_id: int,
    ) -> JSONResponse | None:
        logger.info('Project route started: operation=delete')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                await delete_project(
                    unit_of_work,
                    public_id,
                    user.id,
                )
            logger.info('Project route completed: operation=delete')
            return None
        except ProjectException as error:
            return handle_project_error(error)

    return router
