# ruff: noqa: PLR0913, PLR0917
from collections.abc import Callable
from http import HTTPStatus

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from core.logs import get_logger
from project.clients.client_user import IUserClient
from project.dtos.member import ChangeRoleMemberDTO, ResumeInviteMemberDTO
from project.dtos.page import PaginationDTO
from project.exceptions import (
    ProjectException,
    ProjectUserAuthenticationException,
)
from project.handlers.errors import handle_project_error
from project.schemas.member import (
    ChangeMemberRoleSchema,
    InviteMemberSchema,
    MemberSchema,
)
from project.unit_of_work import IProjectUnitOfWork
from project.use_cases.member import (
    change_member_role,
    get_members,
    invite_member,
    remove_member,
    respond_to_invitation,
)
from project.utils.pagination import PageSchema, decode_cursor, encode_cursor

logger = get_logger(__name__)


def create_project_members_router(
    unit_of_work_factory: Callable[[], IProjectUnitOfWork],
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
        logger.info('Project member route started: operation=list')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                page = await get_members(
                    unit_of_work,
                    project_id,
                    user.id,
                    PaginationDTO(cursor=decode_cursor(cursor), limit=limit),
                )
            result = PageSchema[MemberSchema](
                items=page.items,
                limit=page.pagination.limit,
                more=page.pagination.more,
                cursor=encode_cursor(page.pagination.cursor),
            )
            logger.info(
                'Project member route completed: operation=list item_count=%s',
                len(page.items),
            )
            return result
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
        logger.info('Project member route started: operation=invite')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                member = await invite_member(
                    unit_of_work,
                    project_id,
                    user.id,
                    data.user_id,
                )
            logger.info('Project member route completed: operation=invite')
            return member
        except ProjectException as error:
            return handle_project_error(error)

    async def invitation_response(
        project_id: int,
        accept: bool,
        cookies,
    ) -> MemberSchema | JSONResponse:
        operation = 'accept_invitation' if accept else 'decline_invitation'
        logger.info('Project member route started: operation=%s', operation)
        try:
            user = await resolve_current_user(cookies)
            async with unit_of_work_factory() as unit_of_work:
                member = await respond_to_invitation(
                    unit_of_work,
                    project_id,
                    user.id,
                    ResumeInviteMemberDTO(accept=accept),
                )
            logger.info(
                'Project member route completed: operation=%s', operation
            )
            return member
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
        logger.info('Project member route started: operation=change_role')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                member = await change_member_role(
                    unit_of_work,
                    project_id,
                    user.id,
                    member_id,
                    ChangeRoleMemberDTO(new_role=data.new_role),
                )
            logger.info('Project member route completed: operation=change_role')
            return member
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
        logger.info('Project member route started: operation=remove')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                await remove_member(
                    unit_of_work,
                    project_id,
                    user.id,
                    member_id,
                )
            logger.info('Project member route completed: operation=remove')
            return None
        except ProjectException as error:
            return handle_project_error(error)

    return router
