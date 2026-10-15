# ruff: noqa: PLR0913, PLR0917
from agents.clients.project import IProjectClient
from agents.dtos.chat import (
    MAX_CHAT_TITLE_LENGTH,
    ChatDTO,
    CreateChatDTO,
    UpdateTitleChatDTO,
)
from agents.dtos.message import CreateMessageDTO, MessageDTO
from agents.dtos.page import CursorPage, PaginationDTO
from agents.entities.message import SenderType
from agents.exceptions import (
    ChatNotFoundException,
    ChatOwnerException,
    EmptyMessageException,
    InsufficientProjectPermissionException,
    InvalidChatTitleException,
    MultipleSubmitError,
)
from agents.repositories.chat import IChatRepository
from agents.repositories.message import IMessageRepository
from project.permissions import ProjectPermission


async def _require_project_permission(
    project_client: IProjectClient,
    project_id: int,
    user_id: int,
    permission: ProjectPermission,
) -> None:
    if not await project_client.has_permission(project_id, user_id, permission):
        raise InsufficientProjectPermissionException(permission.value)


async def _get_chat(chat_repo: IChatRepository, chat_id: int) -> ChatDTO:
    chat = await chat_repo.get_chat(chat_id)
    if chat is None:
        raise ChatNotFoundException(chat_id)
    return chat


async def _get_owned_chat(
    chat_repo: IChatRepository, chat_id: int, user_id: int
) -> ChatDTO:
    chat = await _get_chat(chat_repo, chat_id)
    if chat.owner != user_id:
        raise ChatOwnerException(chat_id)
    return chat


async def create_chat(
    chat_repo: IChatRepository,
    project_client: IProjectClient,
    data: CreateChatDTO,
) -> ChatDTO:
    if not data.title.strip() or len(data.title) > MAX_CHAT_TITLE_LENGTH:
        raise InvalidChatTitleException()
    await _require_project_permission(
        project_client,
        data.project_id,
        data.owner,
        ProjectPermission.CHAT_CREATE,
    )
    return await chat_repo.create_chat(
        title=data.title,
        project_id=data.project_id,
        owner=data.owner,
    )


async def get_chat_messages(
    chat_repo: IChatRepository,
    message_repo: IMessageRepository,
    project_client: IProjectClient,
    chat_id: int,
    user_id: int,
    pagination: PaginationDTO,
) -> CursorPage[MessageDTO]:
    chat = await _get_chat(chat_repo, chat_id)
    await _require_project_permission(
        project_client,
        chat.project_id,
        user_id,
        ProjectPermission.CHAT_READ,
    )
    return await message_repo.get_messages_by_chat(chat_id, pagination)


async def send_human_message(
    chat_repo: IChatRepository,
    message_repo: IMessageRepository,
    project_client: IProjectClient,
    chat_id: int,
    user_id: int,
    message: CreateMessageDTO,
) -> MessageDTO:
    if not message.text.strip():
        raise EmptyMessageException()
    chat = await _get_owned_chat(chat_repo, chat_id, user_id)
    await _require_project_permission(
        project_client,
        chat.project_id,
        user_id,
        ProjectPermission.CHAT_SEND_MESSAGE,
    )
    history = await message_repo.get_messages_by_chat(
        chat_id=chat_id, pagination=PaginationDTO(limit=1)
    )
    if history.items and history.items[0].sender_type == SenderType.USER:
        raise MultipleSubmitError()

    return await message_repo.create_human_message(chat_id, message.text)


async def send_ai_message(
    chat_repo: IChatRepository,
    message_repo: IMessageRepository,
    chat_id: int,
    message: CreateMessageDTO,
) -> MessageDTO:
    if not message.text.strip():
        raise EmptyMessageException()
    await _get_chat(chat_repo, chat_id)
    return await message_repo.create_ai_message(
        chat_id=chat_id,
        parent_id=message.parent_id,
        text=message.text,
        payload=message.payload,
        meta_data=message.meta_data,
    )


async def update_chat_title(
    chat_repo: IChatRepository,
    project_client: IProjectClient,
    chat_id: int,
    user_id: int,
    data: UpdateTitleChatDTO,
) -> ChatDTO:
    if not data.title.strip() or len(data.title) > MAX_CHAT_TITLE_LENGTH:
        raise InvalidChatTitleException()
    chat = await _get_owned_chat(chat_repo, chat_id, user_id)
    await _require_project_permission(
        project_client,
        chat.project_id,
        user_id,
        ProjectPermission.CHAT_UPDATE,
    )
    return await chat_repo.update_chat_title(chat_id, data.title)


async def delete_chat(
    chat_repo: IChatRepository,
    project_client: IProjectClient,
    chat_id: int,
    user_id: int,
) -> None:
    chat = await _get_owned_chat(chat_repo, chat_id, user_id)
    await _require_project_permission(
        project_client,
        chat.project_id,
        user_id,
        ProjectPermission.CHAT_DELETE,
    )
    await chat_repo.delete_chat(chat_id)


async def get_project_chats(
    chat_repo: IChatRepository,
    project_client: IProjectClient,
    project_id: int,
    user_id: int,
    pagination: PaginationDTO,
) -> CursorPage[ChatDTO]:
    await _require_project_permission(
        project_client,
        project_id,
        user_id,
        ProjectPermission.CHAT_READ,
    )
    return await chat_repo.get_chats_by_project(
        project_id=project_id,
        title=None,
        owner_id=None,
        pagination=pagination,
    )
