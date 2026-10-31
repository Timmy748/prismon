from types import TracebackType
from typing import Protocol, Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.database import get_session_factory
from agents.repositories.chat import ChatRepository, IChatRepository
from agents.repositories.message import IMessageRepository, MessageRepository
from agents.repositories.workflow import IWorkflowRepository, WorkflowRepository
from infra.logs import get_logger

logger = get_logger(__name__)


class IAgentsUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...

    @property
    def chat_repository(self) -> IChatRepository: ...

    @property
    def message_repository(self) -> IMessageRepository: ...

    @property
    def workflow_repository(self) -> IWorkflowRepository: ...


class AgentsUnitOfWork(IAgentsUnitOfWork):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._session_factory = session_factory or get_session_factory()
        self._session: AsyncSession | None = None
        self._chat_repository: IChatRepository | None = None
        self._message_repository: IMessageRepository | None = None
        self._workflow_repository: IWorkflowRepository | None = None

    async def __aenter__(self) -> 'AgentsUnitOfWork':
        if self._session is not None:
            logger.warning('Attempted to enter an active agents unit of work')
            raise RuntimeError('AgentsUnitOfWork is already active')

        self._session = self._session_factory()
        self._chat_repository = ChatRepository(self._session)
        self._message_repository = MessageRepository(self._session)
        self._workflow_repository = WorkflowRepository(self._session)
        logger.debug('Agents unit of work started')
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._session
        if session is None:
            return

        try:
            if exc_type is not None:
                logger.warning(
                    'Rolling back agents unit of work after an exception',
                    exc_info=(exc_type, exc, traceback),
                )
                await session.rollback()
        finally:
            self._session = None
            self._chat_repository = None
            self._message_repository = None
            self._workflow_repository = None
            await session.close()
            logger.debug('Agents unit of work closed')

    async def commit(self) -> None:
        try:
            await self._require_session().commit()
        except Exception:
            logger.exception('Failed to commit agents unit of work')
            raise

    async def rollback(self) -> None:
        try:
            await self._require_session().rollback()
        except Exception:
            logger.exception('Failed to roll back agents unit of work')
            raise

    @property
    def chat_repository(self) -> IChatRepository:
        if self._chat_repository is None:
            raise RuntimeError(
                'chat_repository is available only inside the context'
            )
        return self._chat_repository

    @property
    def message_repository(self) -> IMessageRepository:
        if self._message_repository is None:
            raise RuntimeError(
                'message_repository is available only inside the context'
            )
        return self._message_repository

    @property
    def workflow_repository(self) -> IWorkflowRepository:
        if self._workflow_repository is None:
            raise RuntimeError(
                'workflow_repository is available only inside the context'
            )
        return self._workflow_repository

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError(
                'AgentsUnitOfWork is available only inside the context'
            )
        return self._session


def create_agents_unit_of_work() -> IAgentsUnitOfWork:
    return AgentsUnitOfWork()
