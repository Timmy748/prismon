# ruff: noqa: PLR0913, PLR0915, PLR0917
import asyncio
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Any, Callable

from agents.actions import ChatAction
from agents.clients.project import IProjectClient
from agents.dtos.chat import (
    MAX_CHAT_TITLE_LENGTH,
    ChatDTO,
    CreateChatDTO,
    UpdateTitleChatDTO,
)
from agents.dtos.message import CreateMessageDTO, MessageDTO
from agents.dtos.page import CursorPage, PaginationDTO
from agents.embedding_engine.factory import create_embedding_engine
from agents.entities.message import SenderType
from agents.exceptions import (
    ChatNotFoundException,
    ChatOwnerException,
    EmptyMessageException,
    InsufficientProjectPermissionException,
    InvalidChatTitleException,
    MultipleSubmitError,
)
from agents.llm_engine.base import GenerationChunk, GenerationFinal
from agents.llm_engine.factory import create_llm_engine
from agents.unit_of_work import IAgentsUnitOfWork
from agents.workflows.nodes.rag import RAGNode
from agents.workflows.registry import workflow_registry_factory
from infra.logs import get_logger
from infra.settings import get_settings

logger = get_logger(__name__)
_BACKGROUND_CHAT_TASKS: set[asyncio.Task[None]] = set()


def _release_background_task(task: asyncio.Task[None]) -> None:
    _BACKGROUND_CHAT_TASKS.discard(task)
    if not task.cancelled() and (error := task.exception()) is not None:
        logger.error(
            'Background chat task failed: error_type=%s', type(error).__name__
        )


async def _require_project_permission(
    project_client: IProjectClient,
    project_id: int,
    user_id: int,
    action: ChatAction,
) -> None:
    if not await project_client.verify_resource_permission(
        project_id, user_id, action
    ):
        logger.warning(
            'Project permission denied: project_id=%d user_id=%d permission=%s',
            project_id,
            user_id,
            action.value,
        )
        raise InsufficientProjectPermissionException(action.value)


async def _get_chat(uow: IAgentsUnitOfWork, chat_id: int) -> ChatDTO:
    chat = await uow.chat_repository.get_chat(chat_id)
    if chat is None:
        raise ChatNotFoundException(chat_id)
    return chat


async def _get_owned_chat(
    uow: IAgentsUnitOfWork, chat_id: int, user_id: int
) -> ChatDTO:
    chat = await _get_chat(uow, chat_id)
    if chat.owner != user_id:
        raise ChatOwnerException(chat_id)
    return chat


async def create_chat(
    uow: IAgentsUnitOfWork,
    project_client: IProjectClient,
    data: CreateChatDTO,
) -> ChatDTO:
    if not data.title.strip() or len(data.title) > MAX_CHAT_TITLE_LENGTH:
        raise InvalidChatTitleException()
    await _require_project_permission(
        project_client,
        data.project_id,
        data.owner,
        ChatAction.CREATE,
    )
    chat = await uow.chat_repository.create_chat(
        title=data.title,
        project_id=data.project_id,
        owner=data.owner,
    )
    await uow.commit()
    logger.info(
        'Created chat: chat_id=%d project_id=%d', chat.id, chat.project_id
    )
    return chat


async def get_chat_messages(
    uow: IAgentsUnitOfWork,
    project_client: IProjectClient,
    chat_id: int,
    user_id: int,
    pagination: PaginationDTO,
) -> CursorPage[MessageDTO]:
    chat = await _get_chat(uow, chat_id)
    await _require_project_permission(
        project_client,
        chat.project_id,
        user_id,
        ChatAction.READ,
    )
    page = await uow.message_repository.get_messages_by_chat(
        chat_id, pagination
    )
    logger.debug(
        'Retrieved chat messages: chat_id=%d count=%d', chat_id, len(page.items)
    )
    return page


async def send_message(
    uow: IAgentsUnitOfWork,
    project_client: IProjectClient,
    chat_id: int,
    user_id: int,
    api_key_id: int,
    message: CreateMessageDTO,
    config: dict[str, Any] | None = None,
    uow_factory: Callable[[], IAgentsUnitOfWork] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    if not message.text.strip():
        raise EmptyMessageException()

    chat = await _get_owned_chat(uow, chat_id, user_id)
    await _require_project_permission(
        project_client,
        chat.project_id,
        user_id,
        ChatAction.SEND_MESSAGE,
    )
    latest = await uow.message_repository.get_messages_by_chat(
        chat_id=chat_id,
        pagination=PaginationDTO(limit=1),
    )
    if latest.items and latest.items[0].sender_type == SenderType.USER:
        raise MultipleSubmitError()

    api_key = await project_client.get_api_key(
        chat.project_id, user_id, api_key_id
    )
    await uow.message_repository.create_human_message(chat_id, message.text)
    await uow.commit()
    history = await uow.message_repository.get_messages_by_chat(
        chat_id, PaginationDTO(limit=100)
    )
    event_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    async def produce() -> None:  # noqa: PLR0912
        worker_uow = uow_factory() if uow_factory is not None else uow
        owns_uow = uow_factory is not None
        entered = False
        try:
            if owns_uow:
                await worker_uow.__aenter__()
                entered = True
            default_provider = get_settings().LLM_PROVIDER
            rag_config = config.get('rag', {}) if config else {}
            chat_config = config.get('chat', {}) if config else {}
            if not isinstance(rag_config, dict):
                rag_config = {}
            if not isinstance(chat_config, dict):
                chat_config = {}
            rag_engine = create_llm_engine(
                api_key=api_key,
                provider=rag_config.get('provider', default_provider),
                model=rag_config.get('model'),
            )
            chat_engine = create_llm_engine(
                api_key=api_key,
                provider=chat_config.get('provider', default_provider),
                model=chat_config.get('model'),
            )
            rag_node = RAGNode(
                engine=rag_engine,
                embedding_engine=create_embedding_engine(),
                uow=worker_uow,
                project_client=project_client,
            )
            workflow = workflow_registry_factory().get_workflow(
                'chat', engine=chat_engine, rag_node=rag_node
            )
            stream_input: dict[str, Any] = {
                'messages': list(reversed(history.items)),
                'project_id': chat.project_id,
                'user_id': user_id,
            }
            if config is not None:
                stream_input['config'] = config
            final: GenerationFinal | None = None
            async for event in workflow.stream(str(chat_id), stream_input):
                if isinstance(event, GenerationChunk):
                    if event.text_delta:
                        await event_queue.put(
                            {'event': 'token', 'data': event.text_delta}
                        )
                elif isinstance(event, GenerationFinal):
                    final = event
                elif isinstance(event, dict) and 'event' in event:
                    await event_queue.put(event)

            if final is None:
                raise RuntimeError('O workflow terminou sem evento final.')
            if not final.raw_text.strip():
                raise EmptyMessageException()

            await _get_chat(worker_uow, chat_id)
            saved_message = (
                await worker_uow.message_repository.create_ai_message(
                    chat_id=chat_id,
                    parent_id=None,
                    text=final.raw_text,
                    payload={},
                    meta_data={
                        'workflow': workflow.name,
                        'version': workflow.version,
                        'generation': asdict(final.usage),
                    },
                )
            )
            await worker_uow.commit()
            logger.info(
                'Completed assistant response: chat_id=%d message_id=%d',
                chat_id,
                saved_message.id,
            )
            await event_queue.put({'event': 'done', 'data': saved_message})
        except asyncio.CancelledError:
            if entered:
                await worker_uow.rollback()
            raise
        except Exception as error:
            logger.error(
                'Assistant response failed: chat_id=%d error_type=%s',
                chat_id,
                type(error).__name__,
            )
            if entered:
                await worker_uow.rollback()
            await event_queue.put(
                {'event': 'error', 'data': {'message': str(error)}}
            )
        finally:
            try:
                if entered:
                    await worker_uow.__aexit__(None, None, None)
            finally:
                await event_queue.put(None)

    task = asyncio.create_task(produce(), name=f'chat-generation-{chat_id}')
    _BACKGROUND_CHAT_TASKS.add(task)
    task.add_done_callback(_release_background_task)

    async def stream_response() -> AsyncIterator[dict[str, Any]]:
        while True:
            item = await event_queue.get()
            if item is None:
                break
            yield item
        # Keep a strong reference until the producer has finished.
        await task

    return stream_response()


async def update_chat_title(
    uow: IAgentsUnitOfWork,
    project_client: IProjectClient,
    chat_id: int,
    user_id: int,
    data: UpdateTitleChatDTO,
) -> ChatDTO:
    if not data.title.strip() or len(data.title) > MAX_CHAT_TITLE_LENGTH:
        raise InvalidChatTitleException()
    chat = await _get_owned_chat(uow, chat_id, user_id)
    await _require_project_permission(
        project_client,
        chat.project_id,
        user_id,
        ChatAction.UPDATE,
    )
    updated_chat = await uow.chat_repository.update_chat_title(
        chat_id, data.title
    )
    await uow.commit()
    logger.info('Updated chat title: chat_id=%d', chat_id)
    return updated_chat


async def delete_chat(
    uow: IAgentsUnitOfWork,
    project_client: IProjectClient,
    chat_id: int,
    user_id: int,
) -> None:
    chat = await _get_owned_chat(uow, chat_id, user_id)
    await _require_project_permission(
        project_client,
        chat.project_id,
        user_id,
        ChatAction.DELETE,
    )
    await uow.chat_repository.delete_chat(chat_id)
    await uow.commit()
    logger.info('Deleted chat: chat_id=%d', chat_id)


async def get_project_chats(
    uow: IAgentsUnitOfWork,
    project_client: IProjectClient,
    project_id: int,
    user_id: int,
    pagination: PaginationDTO,
) -> CursorPage[ChatDTO]:
    await _require_project_permission(
        project_client,
        project_id,
        user_id,
        ChatAction.READ,
    )
    page = await uow.chat_repository.get_chats_by_project(
        project_id=project_id,
        title=None,
        owner_id=None,
        pagination=pagination,
    )
    logger.debug(
        'Retrieved project chats: project_id=%d count=%d',
        project_id,
        len(page.items),
    )
    return page
