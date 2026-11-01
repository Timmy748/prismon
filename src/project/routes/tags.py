# ruff: noqa: PLR0915
from collections.abc import Callable
from http import HTTPStatus

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from infra.logs import get_logger
from project.clients.client_user import IUserClient, create_identity_client
from project.dtos.tag import CreateTagDTO, UpdateTagDTO
from project.exceptions import (
    ProjectException,
    ProjectUserAuthenticationException,
)
from project.handlers.errors import handle_project_error
from project.schemas.tag import (
    CreateTagSchema,
    TagListSchema,
    TagSchema,
    UpdateTagSchema,
)
from project.unit_of_work import IProjectUnitOfWork, create_project_unit_of_work
from project.use_cases.tags import (
    add_tag,
    attach_asset_tag,
    attach_document_tag,
    delete_tag,
    detach_asset_tag,
    detach_document_tag,
    get_asset_tags,
    get_document_tags,
    get_tags,
    update_tag,
)

logger = get_logger(__name__)


def create_tags_router(
    unit_of_work_factory: Callable[[], IProjectUnitOfWork],
    user_client_factory: Callable[[], IUserClient],
) -> APIRouter:
    router = APIRouter(prefix='/projects/{project_id}', tags=['tags'])

    async def resolve_current_user(cookies):
        access_token = cookies.get('jwt')
        if not access_token:
            raise ProjectUserAuthenticationException()
        return await user_client_factory().get_current_user(access_token)

    @router.get('/tags', response_model=TagListSchema)
    async def list_tags(
        request: Request, project_id: int
    ) -> TagListSchema | JSONResponse:
        logger.info(
            'Tag route started: operation=list project_id=%s', project_id
        )
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                items = await get_tags(unit_of_work, project_id, user.id)
            result = TagListSchema(
                items=[TagSchema.from_dto(item) for item in items]
            )
            logger.info(
                'Tag route completed: operation=list '
                'project_id=%s item_count=%s',
                project_id,
                len(items),
            )
            return result
        except ProjectException as error:
            return handle_project_error(error)

    @router.post(
        '/tags', response_model=TagSchema, status_code=HTTPStatus.CREATED
    )
    async def post_tag(
        request: Request, project_id: int, data: CreateTagSchema
    ) -> TagSchema | JSONResponse:
        logger.info(
            'Tag route started: operation=create project_id=%s', project_id
        )
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                item = await add_tag(
                    unit_of_work,
                    project_id,
                    user.id,
                    CreateTagDTO(
                        label=data.label,
                        description=data.description,
                        color=data.color,
                    ),
                )
            result = TagSchema.from_dto(item)
            logger.info(
                'Tag route completed: operation=create project_id=%s tag_id=%s',
                project_id,
                item.id,
            )
            return result
        except ProjectException as error:
            return handle_project_error(error)

    @router.put('/tags/{tag_id}', response_model=TagSchema)
    async def put_tag(
        request: Request,
        project_id: int,
        tag_id: int,
        data: UpdateTagSchema,
    ) -> TagSchema | JSONResponse:
        logger.info(
            'Tag route started: operation=update project_id=%s tag_id=%s',
            project_id,
            tag_id,
        )
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                item = await update_tag(
                    unit_of_work,
                    project_id,
                    user.id,
                    tag_id,
                    UpdateTagDTO(
                        label=data.label,
                        description=data.description,
                        color=data.color,
                    ),
                )
            result = TagSchema.from_dto(item)
            logger.info(
                'Tag route completed: operation=update project_id=%s tag_id=%s',
                project_id,
                tag_id,
            )
            return result
        except ProjectException as error:
            return handle_project_error(error)

    @router.delete(
        '/tags/{tag_id}',
        status_code=HTTPStatus.NO_CONTENT,
        response_model=None,
    )
    async def remove_tag(
        request: Request, project_id: int, tag_id: int
    ) -> Response | JSONResponse:
        logger.info(
            'Tag route started: operation=delete project_id=%s tag_id=%s',
            project_id,
            tag_id,
        )
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                await delete_tag(unit_of_work, project_id, user.id, tag_id)
            logger.info(
                'Tag route completed: operation=delete project_id=%s tag_id=%s',
                project_id,
                tag_id,
            )
            return Response(status_code=HTTPStatus.NO_CONTENT)
        except ProjectException as error:
            return handle_project_error(error)

    @router.get('/assets/{asset_id}/tags', response_model=TagListSchema)
    async def list_asset_tags(
        request: Request, project_id: int, asset_id: int
    ) -> TagListSchema | JSONResponse:
        logger.info(
            'Tag route started: operation=list_asset project_id=%s asset_id=%s',
            project_id,
            asset_id,
        )
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                items = await get_asset_tags(
                    unit_of_work, project_id, user.id, asset_id
                )
            result = TagListSchema(
                items=[TagSchema.from_dto(item) for item in items]
            )
            logger.info(
                'Tag route completed: operation=list_asset '
                'project_id=%s asset_id=%s item_count=%s',
                project_id,
                asset_id,
                len(items),
            )
            return result
        except ProjectException as error:
            return handle_project_error(error)

    @router.put(
        '/assets/{asset_id}/tags/{tag_id}',
        status_code=HTTPStatus.NO_CONTENT,
        response_model=None,
    )
    async def put_asset_tag(
        request: Request, project_id: int, asset_id: int, tag_id: int
    ) -> Response | JSONResponse:
        logger.info(
            'Tag route started: operation=attach_asset '
            'project_id=%s asset_id=%s tag_id=%s',
            project_id,
            asset_id,
            tag_id,
        )
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                await attach_asset_tag(
                    unit_of_work, project_id, user.id, asset_id, tag_id
                )
            logger.info(
                'Tag route completed: operation=attach_asset '
                'project_id=%s asset_id=%s tag_id=%s',
                project_id,
                asset_id,
                tag_id,
            )
            return Response(status_code=HTTPStatus.NO_CONTENT)
        except ProjectException as error:
            return handle_project_error(error)

    @router.delete(
        '/assets/{asset_id}/tags/{tag_id}',
        status_code=HTTPStatus.NO_CONTENT,
        response_model=None,
    )
    async def remove_asset_tag(
        request: Request, project_id: int, asset_id: int, tag_id: int
    ) -> Response | JSONResponse:
        logger.info(
            'Tag route started: operation=detach_asset '
            'project_id=%s asset_id=%s tag_id=%s',
            project_id,
            asset_id,
            tag_id,
        )
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                await detach_asset_tag(
                    unit_of_work, project_id, user.id, asset_id, tag_id
                )
            logger.info(
                'Tag route completed: operation=detach_asset '
                'project_id=%s asset_id=%s tag_id=%s',
                project_id,
                asset_id,
                tag_id,
            )
            return Response(status_code=HTTPStatus.NO_CONTENT)
        except ProjectException as error:
            return handle_project_error(error)

    @router.get('/documents/{document_id}/tags', response_model=TagListSchema)
    async def list_document_tags(
        request: Request, project_id: int, document_id: int
    ) -> TagListSchema | JSONResponse:
        logger.info(
            'Tag route started: operation=list_document '
            'project_id=%s document_id=%s',
            project_id,
            document_id,
        )
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                items = await get_document_tags(
                    unit_of_work, project_id, user.id, document_id
                )
            result = TagListSchema(
                items=[TagSchema.from_dto(item) for item in items]
            )
            logger.info(
                'Tag route completed: operation=list_document '
                'project_id=%s document_id=%s item_count=%s',
                project_id,
                document_id,
                len(items),
            )
            return result
        except ProjectException as error:
            return handle_project_error(error)

    @router.put(
        '/documents/{document_id}/tags/{tag_id}',
        status_code=HTTPStatus.NO_CONTENT,
        response_model=None,
    )
    async def put_document_tag(
        request: Request, project_id: int, document_id: int, tag_id: int
    ) -> Response | JSONResponse:
        logger.info(
            'Tag route started: operation=attach_document '
            'project_id=%s document_id=%s tag_id=%s',
            project_id,
            document_id,
            tag_id,
        )
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                await attach_document_tag(
                    unit_of_work, project_id, user.id, document_id, tag_id
                )
            logger.info(
                'Tag route completed: operation=attach_document '
                'project_id=%s document_id=%s tag_id=%s',
                project_id,
                document_id,
                tag_id,
            )
            return Response(status_code=HTTPStatus.NO_CONTENT)
        except ProjectException as error:
            return handle_project_error(error)

    @router.delete(
        '/documents/{document_id}/tags/{tag_id}',
        status_code=HTTPStatus.NO_CONTENT,
        response_model=None,
    )
    async def remove_document_tag(
        request: Request, project_id: int, document_id: int, tag_id: int
    ) -> Response | JSONResponse:
        logger.info(
            'Tag route started: operation=detach_document '
            'project_id=%s document_id=%s tag_id=%s',
            project_id,
            document_id,
            tag_id,
        )
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                await detach_document_tag(
                    unit_of_work, project_id, user.id, document_id, tag_id
                )
            logger.info(
                'Tag route completed: operation=detach_document '
                'project_id=%s document_id=%s tag_id=%s',
                project_id,
                document_id,
                tag_id,
            )
            return Response(status_code=HTTPStatus.NO_CONTENT)
        except ProjectException as error:
            return handle_project_error(error)

    return router


router = create_tags_router(
    create_project_unit_of_work,
    create_identity_client,
)
