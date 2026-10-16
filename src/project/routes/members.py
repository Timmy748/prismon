# ruff: noqa: PLR0913, PLR0917
from collections.abc import Awaitable, Callable
from http import HTTPStatus

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from project.clients.client_user import IUserClient
from project.dtos.member import ChangeRoleMemberDTO, ResumeInviteMemberDTO
from project.dtos.page import PaginationDTO
from project.exceptions import (
    ProjectException,
    ProjectUserAuthenticationException,
)
from project.handlers.errors import handle_project_error
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository
from project.schemas.member import (
    ChangeMemberRoleSchema,
    InviteMemberSchema,
    MemberSchema,
)
from project.use_cases.member import (
    change_member_role,
    get_members,
    invite_member,
    remove_member,
    respond_to_invitation,
)
from project.utils.pagination import PageSchema, decode_cursor, encode_cursor


def create_project_members_router(
    project_repository_factory: Callable[[], Awaitable[IProjectRepository]],
    member_repository_factory: Callable[[], Awaitable[IMemberRepository]],
    user_client_factory: Callable[[], IUserClient],
) -> APIRouter:
    router = APIRouter(tags=['project members'])

    async def resolve_current_user(cookies):
        access_token = cookies.get('jwt')
        if not access_token:
            raise ProjectUserAuthenticationException()
        return await user_client_factory().get_current_user(access_token)

    @router.get(
        '/projects/{project_id}/members',
        response_model=PageSchema[MemberSchema],
    )
    async def get_project_members(
        request: Request,
        project_id: int,
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = Query(default=None),
    ) -> PageSchema[MemberSchema] | JSONResponse:
        try:
            user = await resolve_current_user(request.cookies)
            page = await get_members(
                await project_repository_factory(),
                await member_repository_factory(),
                project_id,
                user.id,
                PaginationDTO(cursor=decode_cursor(cursor), limit=limit),
            )
            return PageSchema[MemberSchema](
                items=page.items,
                limit=page.pagination.limit,
                more=page.pagination.more,
                cursor=encode_cursor(page.pagination.cursor),
            )
        except ProjectException as error:
            return handle_project_error(error)

    @router.post(
        '/projects/{project_id}/members',
        response_model=MemberSchema,
        status_code=HTTPStatus.CREATED,
    )
    async def post_member(
        request: Request,
        project_id: int,
        data: InviteMemberSchema,
    ) -> MemberSchema | JSONResponse:
        try:
            user = await resolve_current_user(request.cookies)
            return await invite_member(
                await project_repository_factory(),
                await member_repository_factory(),
                project_id,
                user.id,
                data.user_id,
            )
        except ProjectException as error:
            return handle_project_error(error)

    async def invitation_response(
        project_id: int,
        accept: bool,
        cookies,
    ) -> MemberSchema | JSONResponse:
        try:
            user = await resolve_current_user(cookies)
            return await respond_to_invitation(
                await project_repository_factory(),
                await member_repository_factory(),
                project_id,
                user.id,
                ResumeInviteMemberDTO(accept=accept),
            )
        except ProjectException as error:
            return handle_project_error(error)

    @router.patch(
        '/projects/{project_id}/members/accept', response_model=MemberSchema
    )
    async def accept_invitation(
        request: Request,
        project_id: int,
    ) -> MemberSchema | JSONResponse:
        return await invitation_response(project_id, True, request.cookies)

    @router.patch(
        '/projects/{project_id}/members/refuse', response_model=MemberSchema
    )
    async def refuse_invitation(
        request: Request,
        project_id: int,
    ) -> MemberSchema | JSONResponse:
        return await invitation_response(project_id, False, request.cookies)

    @router.patch(
        '/projects/{project_id}/members/{member_id}',
        response_model=MemberSchema,
    )
    async def patch_member(
        request: Request,
        project_id: int,
        member_id: int,
        data: ChangeMemberRoleSchema,
    ) -> MemberSchema | JSONResponse:
        try:
            user = await resolve_current_user(request.cookies)
            return await change_member_role(
                await project_repository_factory(),
                await member_repository_factory(),
                project_id,
                user.id,
                member_id,
                ChangeRoleMemberDTO(new_role=data.new_role),
            )
        except ProjectException as error:
            return handle_project_error(error)

    @router.delete(
        '/projects/{project_id}/members/{member_id}',
        status_code=HTTPStatus.NO_CONTENT,
        response_model=None,
    )
    async def delete_member(
        request: Request,
        project_id: int,
        member_id: int,
    ) -> JSONResponse | None:
        try:
            user = await resolve_current_user(request.cookies)
            await remove_member(
                await project_repository_factory(),
                await member_repository_factory(),
                project_id,
                user.id,
                member_id,
            )
            return None
        except ProjectException as error:
            return handle_project_error(error)

    return router
