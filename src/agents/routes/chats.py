# ruff: noqa: PLR0913, PLR0917
from collections.abc import AsyncIterator, Awaitable, Callable
from http import HTTPStatus

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from agents.clients.identity import IIdentityClient
from agents.clients.project import IProjectClient
from agents.dtos.chat import (
    ChatDTO,
    CreateChatDTO,
    UpdateTitleChatDTO,
)
from agents.dtos.message import CreateMessageDTO, MessageDTO
from agents.dtos.page import CursorPage
from agents.dtos.user import UserDTO
from agents.entities.message import SenderType
from agents.exceptions import AgentsException, UserAuthenticationException
from agents.handlers.errors import handle_agents_error
from agents.repositories.chat import IChatRepository
from agents.repositories.message import IMessageRepository
from agents.schemas.chat import ChatSchema, UpdateChatTitleSchema
from agents.schemas.message import CreateMessageSchema, MessageSchema
from agents.schemas.page import PageSchema
from agents.use_cases.chats import (
    create_chat,
    delete_chat,
    get_chat_messages,
    get_project_chats,
    send_message,
    update_chat_title,
)
from agents.utils.pagination import encode_cursor, pagination_dto
from agents.utils.sse import format_sse


def _message_page_schema(
    page: CursorPage[MessageDTO],
) -> PageSchema[MessageSchema]:
    return PageSchema(
        items=[MessageSchema.from_dto(item) for item in page.items],
        limit=page.pagination.limit,
        more=page.pagination.more,
        cursor=encode_cursor(page.pagination.cursor),
    )


def _chat_page_schema(page: CursorPage[ChatDTO]) -> PageSchema[ChatSchema]:
    return PageSchema(
        items=[ChatSchema.from_dto(item) for item in page.items],
        limit=page.pagination.limit,
        more=page.pagination.more,
        cursor=encode_cursor(page.pagination.cursor),
    )


def create_chat_routes(  # noqa: PLR0915
    chat_repository_factory: Callable[[], Awaitable[IChatRepository]],
    message_repository_factory: Callable[[], Awaitable[IMessageRepository]],
    identity_client_factory: Callable[[], IIdentityClient],
    project_client_factory: Callable[[], IProjectClient],
) -> APIRouter:
    router = APIRouter(tags=['chats'])

    async def resolve_current_user(cookies) -> UserDTO:
        access_token = cookies.get('jwt')
        if not access_token:
            raise UserAuthenticationException()
        return await identity_client_factory().get_current_user(access_token)

    @router.get(
        '/chats/{chat_id}/messages', response_model=PageSchema[MessageSchema]
    )
    async def list_chat_messages(
        request: Request,
        chat_id: int,
        cursor: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> PageSchema[MessageSchema] | JSONResponse:
        try:
            user = await resolve_current_user(request.cookies)
            page = await get_chat_messages(
                await chat_repository_factory(),
                await message_repository_factory(),
                project_client_factory(),
                chat_id,
                user.id,
                pagination_dto(cursor, limit),
            )
            return _message_page_schema(page)
        except AgentsException as error:
            return handle_agents_error(error)

    @router.post(
        '/chats/messages',
        response_model=None,
    )
    async def post_chat_message(
        request: Request,
        data: CreateMessageSchema,
    ) -> StreamingResponse | JSONResponse:
        try:
            user = await resolve_current_user(request.cookies)
            chat_repo = await chat_repository_factory()
            project_client = project_client_factory()
            chat_id = data.chat_id
            chat: ChatDTO | None = None
            if chat_id is None:
                project_id = data.project_id
                if project_id is None:
                    raise HTTPException(
                        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                        detail='project_id is required when chat_id is omitted',
                    )
                chat = await create_chat(
                    chat_repo,
                    project_client,
                    CreateChatDTO(
                        project_id=project_id,
                        owner=user.id,
                    ),
                )
                chat_id = chat.id
            message_repo = await message_repository_factory()
            user_message = CreateMessageDTO(
                parent_id=None,
                sender_type=SenderType.USER,
                text=data.text,
                payload={},
                meta_data={},
            )
            message = await send_message(
                chat_repo,
                message_repo,
                project_client,
                chat_id,
                user.id,
                user_message,
            )

            async def event_stream() -> AsyncIterator[str]:
                if chat is not None:
                    yield format_sse('chat', ChatSchema.from_dto(chat))
                try:
                    async for item in message:
                        event_name = item['event']
                        event_data = item.get('data')
                        if event_name == 'done' and isinstance(
                            event_data, MessageDTO
                        ):
                            event_data = MessageSchema.from_dto(event_data)
                        elif event_name == 'chat' and isinstance(
                            event_data, ChatDTO
                        ):
                            event_data = ChatSchema.from_dto(event_data)
                        yield format_sse(event_name, event_data)
                except AgentsException as error:
                    yield format_sse('error', {'detail': str(error)})
                except Exception as error:
                    yield format_sse('error', {'detail': str(error)})

            return StreamingResponse(
                event_stream(),
                media_type='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'X-Accel-Buffering': 'no',
                },
            )
        except AgentsException as error:
            return handle_agents_error(error)

    @router.patch('/chats/{chat_id}', response_model=ChatSchema)
    async def patch_chat(
        request: Request,
        chat_id: int,
        data: UpdateChatTitleSchema,
    ) -> ChatSchema | JSONResponse:
        try:
            user = await resolve_current_user(request.cookies)
            chat = await update_chat_title(
                await chat_repository_factory(),
                project_client_factory(),
                chat_id,
                user.id,
                UpdateTitleChatDTO(title=data.title),
            )
            return ChatSchema.from_dto(chat)
        except AgentsException as error:
            return handle_agents_error(error)

    @router.delete(
        '/chats/{chat_id}',
        status_code=HTTPStatus.NO_CONTENT,
        response_model=None,
    )
    async def remove_chat(
        request: Request,
        chat_id: int,
    ) -> Response | JSONResponse:
        try:
            user = await resolve_current_user(request.cookies)
            await delete_chat(
                await chat_repository_factory(),
                project_client_factory(),
                chat_id,
                user.id,
            )
            return Response(status_code=HTTPStatus.NO_CONTENT)
        except AgentsException as error:
            return handle_agents_error(error)

    @router.get(
        '/projects/{project_id}/chats', response_model=PageSchema[ChatSchema]
    )
    async def list_project_chats(
        request: Request,
        project_id: int,
        cursor: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> PageSchema[ChatSchema] | JSONResponse:
        try:
            user = await resolve_current_user(request.cookies)
            page = await get_project_chats(
                await chat_repository_factory(),
                project_client_factory(),
                project_id,
                user.id,
                pagination_dto(cursor, limit),
            )
            return _chat_page_schema(page)
        except AgentsException as error:
            return handle_agents_error(error)

    return router
