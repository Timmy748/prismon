from types import TracebackType
from typing import Protocol, Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.logs import get_logger
from identity.database import get_session_factory
from identity.repositories.token import (
    IRefreshTokenRepository,
    RefreshTokenRepository,
)
from identity.repositories.user import IUserRepository, UserRepository

logger = get_logger(__name__)


class IIdentityUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...

    @property
    def user_repository(self) -> IUserRepository: ...

    @property
    def token_repository(self) -> IRefreshTokenRepository: ...


class IdentityUnitOfWork(IIdentityUnitOfWork):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._session_factory = session_factory or get_session_factory()
        self._session: AsyncSession | None = None
        self._user_repository: IUserRepository | None = None
        self._token_repository: IRefreshTokenRepository | None = None

    async def __aenter__(self) -> 'IdentityUnitOfWork':
        if self._session is not None:
            logger.error('Identity unit of work entered while already active')
            raise RuntimeError('IdentityUnitOfWork context is already active')

        self._session = self._session_factory()
        self._user_repository = UserRepository(self._session)
        self._token_repository = RefreshTokenRepository(self._session)
        logger.debug('Identity unit of work started')
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._require_session()
        try:
            if exc_type is not None:
                logger.warning(
                    'Identity unit of work rolling back after %s',
                    exc_type.__name__,
                )
                await session.rollback()
        finally:
            try:
                await session.close()
            finally:
                self._session = None
                self._user_repository = None
                self._token_repository = None
                logger.debug('Identity unit of work closed')

    async def commit(self) -> None:
        await self._require_session().commit()
        logger.debug('Identity unit of work committed')

    async def rollback(self) -> None:
        await self._require_session().rollback()
        logger.debug('Identity unit of work rolled back')

    @property
    def user_repository(self) -> IUserRepository:
        if self._user_repository is None:
            raise RuntimeError('IdentityUnitOfWork is not active')
        return self._user_repository

    @property
    def token_repository(self) -> IRefreshTokenRepository:
        if self._token_repository is None:
            raise RuntimeError('IdentityUnitOfWork is not active')
        return self._token_repository

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError('IdentityUnitOfWork is not active')
        return self._session


def create_identity_unit_of_work() -> IIdentityUnitOfWork:
    return IdentityUnitOfWork()
