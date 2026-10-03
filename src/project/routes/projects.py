# ruff: noqa: PLR0913, PLR0917
from collections.abc import Awaitable, Callable
from http import HTTPStatus

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from project.clients.client_user import IUserClient
from project.dtos.project import CreateProjectDTO, ProjectDTO, UpdateProjectDTO
from project.dtos.user import UserDTO
from project.exceptions import (
    ProjectException,
    ProjectUserAuthenticationException,
)
from project.handlers.errors import handle_project_error
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository
from project.schemas.project import (
    CreateProjectSchema,
    ProjectSchema,
    UpdateProjectSchema,
)
from project.use_cases.project import (
    create_project,
    delete_project,
    get_projects,
    update_project,
)
from project.utils.pagination import PageSchema, page_schema, pagination_dto


def create_project_router(
    project_repository_factory: Callable[[], Awaitable[IProjectRepository]],
    member_repository_factory: Callable[[], Awaitable[IMemberRepository]],
    user_client_factory: Callable[[], IUserClient],
) -> APIRouter:
    router = APIRouter(prefix='/projects', tags=['projects'])
    bearer = HTTPBearer(auto_error=False)

    async def authenticated_user(
        credentials: HTTPAuthorizationCredentials | None,
    ) -> UserDTO:
        if credentials is None:
            raise ProjectUserAuthenticationException()
        return await user_client_factory().get_current_user(
            credentials.credentials
        )

    @router.get('', response_model=PageSchema[ProjectSchema])
    async def get_project_list(
        name: str | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = None,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> PageSchema[ProjectSchema] | JSONResponse:
        try:
            user = await authenticated_user(credentials)
            page = await get_projects(
                await project_repository_factory(),
                user.id,
                name,
                pagination_dto(cursor, limit),
            )
            return page_schema(page)
        except ProjectException as error:
            return handle_project_error(error)

    @router.post(
        '', response_model=ProjectSchema, status_code=HTTPStatus.CREATED
    )
    async def post_project(
        data: CreateProjectSchema,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> ProjectDTO | JSONResponse:
        try:
            user = await authenticated_user(credentials)
            return await create_project(
                await project_repository_factory(),
                await member_repository_factory(),
                user.id,
                CreateProjectDTO(name=data.name, owner=str(user.id)),
            )
        except ProjectException as error:
            return handle_project_error(error)

    @router.put('/{public_id}', response_model=ProjectSchema)
    async def put_project(
        public_id: int,
        data: UpdateProjectSchema,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> ProjectDTO | JSONResponse:
        try:
            user = await authenticated_user(credentials)
            return await update_project(
                await project_repository_factory(),
                await member_repository_factory(),
                public_id,
                user.id,
                UpdateProjectDTO(name=data.name),
            )
        except ProjectException as error:
            return handle_project_error(error)

    @router.delete(
        '/{public_id}', status_code=HTTPStatus.NO_CONTENT, response_model=None
    )
    async def remove_project(
        public_id: int,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> JSONResponse | None:
        try:
            user = await authenticated_user(credentials)
            await delete_project(
                await project_repository_factory(),
                await member_repository_factory(),
                public_id,
                user.id,
            )
            return None
        except ProjectException as error:
            return handle_project_error(error)

    return router
