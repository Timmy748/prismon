# ruff: noqa: PLR0913, PLR0917
from typing import Protocol

from sqlalchemy import literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from project.database import get_session_factory
from project.dtos.document import DocumentDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.document import Document, DocumentStatus


class IDocumentRepository(Protocol):
    async def get_document(self, document_id: int) -> DocumentDTO | None: ...
    async def get_documents(
        self,
        project_id: int,
        pagination: PaginationDTO = PaginationDTO(),
        name: str | None = None,
        status: DocumentStatus | None = None,
    ) -> CursorPage[DocumentDTO]: ...
    async def create_document(
        self,
        project_id: int,
        file: str,
        name: str,
        description: str | None = None,
        status: DocumentStatus = DocumentStatus.DRAFT,
    ) -> DocumentDTO: ...
    async def update_document(
        self,
        document_id: int,
        file: str | None = None,
        name: str | None = None,
        description: str | None = None,
        status: DocumentStatus | None = None,
    ) -> DocumentDTO | None: ...
    async def delete_document(self, document_id: int) -> None: ...


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_dto(self, row: Document) -> DocumentDTO:
        return DocumentDTO(
            row.id,
            row.project_id,
            row.file,
            row.name,
            row.description,
            row.status,
            row.created_at,
            row.updated_at,
        )

    async def get_document(self, document_id: int) -> DocumentDTO | None:
        row = await self._session.get(Document, document_id)
        return self._to_dto(row) if row else None

    async def get_documents(
        self,
        project_id: int,
        pagination: PaginationDTO = PaginationDTO(),
        name: str | None = None,
        status: DocumentStatus | None = None,
    ) -> CursorPage[DocumentDTO]:
        limit = max(1, min(pagination.limit, 100))
        stmt = select(Document).where(Document.project_id == project_id)
        if pagination.cursor is not None:
            stmt = stmt.where(
                tuple_(Document.updated_at, Document.id)
                < tuple_(
                    literal(pagination.cursor[0]), literal(pagination.cursor[1])
                )
            )
        if name:
            stmt = stmt.where(Document.name.contains(name))
        if status is not None:
            stmt = stmt.where(Document.status == status)
        rows = list(
            (
                await self._session.scalars(
                    stmt.order_by(
                        Document.updated_at.desc(), Document.id.desc()
                    ).limit(limit + 1)
                )
            ).all()
        )
        more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = (
            (rows[-1].updated_at, rows[-1].id) if more and rows else None
        )
        return CursorPage(
            [self._to_dto(row) for row in rows],
            PaginationDTO(cursor=next_cursor, limit=limit, more=more),
        )

    async def create_document(
        self,
        project_id: int,
        file: str,
        name: str,
        description: str | None = None,
        status: DocumentStatus = DocumentStatus.DRAFT,
    ) -> DocumentDTO:
        row = Document(
            project_id=project_id,
            file=file,
            name=name,
            description=description,
            status=status,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_dto(row)

    async def update_document(
        self,
        document_id: int,
        file: str | None = None,
        name: str | None = None,
        description: str | None = None,
        status: DocumentStatus | None = None,
    ) -> DocumentDTO | None:
        row = await self._session.get(Document, document_id)
        if row is None:
            return None
        if file is not None:
            row.file = file
        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        if status is not None:
            row.status = status
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_dto(row)

    async def delete_document(self, document_id: int) -> None:
        row = await self._session.get(Document, document_id)
        if row is None:
            return
        await self._session.delete(row)
        await self._session.commit()


async def create_document_repository() -> (
    IDocumentRepository
):  # pragma: no cover
    session_maker = get_session_factory()
    async with session_maker() as session:
        return DocumentRepository(session)
