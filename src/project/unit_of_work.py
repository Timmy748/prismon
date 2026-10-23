from types import TracebackType
from typing import Protocol, Self

from sqlalchemy.ext.asyncio import AsyncSession

from project.database import get_session_factory
from project.repositories.asset import AssetRepository, IAssetRepository
from project.repositories.document import (
    DocumentRepository,
    IDocumentRepository,
)
from project.repositories.member import IMemberRepository, MemberRepository
from project.repositories.project import IProjectRepository, ProjectRepository


class IProjectUnitOfWork(Protocol):
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
    def project_repository(self) -> IProjectRepository: ...

    @property
    def member_repository(self) -> IMemberRepository: ...

    @property
    def document_repository(self) -> IDocumentRepository: ...

    @property
    def asset_repository(self) -> IAssetRepository: ...


class UnitOfWork(IProjectUnitOfWork):
    def __init__(self) -> None:
        self._session: AsyncSession | None = None
        self._project_repository: IProjectRepository | None = None
        self._member_repository: IMemberRepository | None = None
        self._document_repository: IDocumentRepository | None = None
        self._asset_repository: IAssetRepository | None = None

    async def __aenter__(self) -> 'UnitOfWork':
        if self._session is not None:
            raise RuntimeError('UnitOfWork context is already active')

        self._session = get_session_factory()()
        self._project_repository = ProjectRepository(self._session)
        self._member_repository = MemberRepository(self._session)
        self._document_repository = DocumentRepository(self._session)
        self._asset_repository = AssetRepository(self._session)
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
                await session.rollback()
        finally:
            self._session = None
            self._project_repository = None
            self._member_repository = None
            self._document_repository = None
            self._asset_repository = None
            await session.close()

    async def commit(self) -> None:
        await self._active_session().commit()

    async def rollback(self) -> None:
        await self._active_session().rollback()

    @property
    def project_repository(self) -> IProjectRepository:
        if self._project_repository is None:
            raise RuntimeError('UnitOfWork context is not active')
        return self._project_repository

    @property
    def member_repository(self) -> IMemberRepository:
        if self._member_repository is None:
            raise RuntimeError('UnitOfWork context is not active')
        return self._member_repository

    @property
    def document_repository(self) -> IDocumentRepository:
        if self._document_repository is None:
            raise RuntimeError('UnitOfWork context is not active')
        return self._document_repository

    @property
    def asset_repository(self) -> IAssetRepository:
        if self._asset_repository is None:
            raise RuntimeError('UnitOfWork context is not active')
        return self._asset_repository

    def _active_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError('UnitOfWork context is not active')
        return self._session


def create_project_unit_of_work() -> IProjectUnitOfWork:
    return UnitOfWork()
