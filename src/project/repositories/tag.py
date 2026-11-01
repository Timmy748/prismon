from typing import Protocol

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.logs import get_logger
from project.dtos.tag import TagDTO
from project.entities.tag import Tag, asset_tags, document_tags

logger = get_logger(__name__)


class ITagRepository(Protocol):
    async def get_tag(self, tag_id: int) -> TagDTO | None: ...
    async def get_tags(self, project_id: int) -> list[TagDTO]: ...
    async def create_tag(
        self, project_id: int, label: str, description: str, color: str
    ) -> TagDTO: ...
    async def update_tag(
        self,
        tag_id: int,
        label: str | None = None,
        description: str | None = None,
        color: str | None = None,
    ) -> TagDTO | None: ...
    async def delete_tag(self, tag_id: int) -> None: ...
    async def get_asset_tags(self, asset_id: int) -> list[TagDTO]: ...
    async def attach_asset_tag(self, asset_id: int, tag_id: int) -> None: ...
    async def detach_asset_tag(self, asset_id: int, tag_id: int) -> None: ...
    async def get_document_tags(self, document_id: int) -> list[TagDTO]: ...
    async def attach_document_tag(
        self, document_id: int, tag_id: int
    ) -> None: ...
    async def detach_document_tag(
        self, document_id: int, tag_id: int
    ) -> None: ...


class TagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_dto(row: Tag) -> TagDTO:
        return TagDTO(
            id=row.id,
            project_id=row.project_id,
            label=row.label,
            description=row.description,
            color=row.color,
        )

    async def get_tag(self, tag_id: int) -> TagDTO | None:
        logger.debug('Loading tag repository record: tag_id=%s', tag_id)
        row = await self._session.get(Tag, tag_id)
        return self._to_dto(row) if row is not None else None

    async def get_tags(self, project_id: int) -> list[TagDTO]:
        logger.debug(
            'Listing tag repository records: project_id=%s', project_id
        )
        rows = list(
            (
                await self._session.scalars(
                    select(Tag)
                    .where(Tag.project_id == project_id)
                    .order_by(Tag.label, Tag.id)
                )
            ).all()
        )
        return [self._to_dto(row) for row in rows]

    async def create_tag(
        self, project_id: int, label: str, description: str, color: str
    ) -> TagDTO:
        logger.debug(
            'Creating tag repository record: project_id=%s', project_id
        )
        row = Tag(
            project_id=project_id,
            label=label,
            description=description,
            color=color,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._to_dto(row)

    async def update_tag(
        self,
        tag_id: int,
        label: str | None = None,
        description: str | None = None,
        color: str | None = None,
    ) -> TagDTO | None:
        logger.debug('Updating tag repository record: tag_id=%s', tag_id)
        row = await self._session.get(Tag, tag_id)
        if row is None:
            return None
        if label is not None:
            row.label = label
        if description is not None:
            row.description = description
        if color is not None:
            row.color = color
        await self._session.flush()
        await self._session.refresh(row)
        return self._to_dto(row)

    async def delete_tag(self, tag_id: int) -> None:
        logger.debug('Deleting tag repository record: tag_id=%s', tag_id)
        row = await self._session.get(Tag, tag_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()

    async def get_asset_tags(self, asset_id: int) -> list[TagDTO]:
        logger.debug('Listing asset tags: asset_id=%s', asset_id)
        rows = list(
            (
                await self._session.scalars(
                    select(Tag)
                    .join(asset_tags, asset_tags.c.tag_id == Tag.id)
                    .where(asset_tags.c.asset_id == asset_id)
                    .order_by(Tag.label, Tag.id)
                )
            ).all()
        )
        return [self._to_dto(row) for row in rows]

    async def attach_asset_tag(self, asset_id: int, tag_id: int) -> None:
        logger.debug(
            'Attaching tag to asset: asset_id=%s tag_id=%s', asset_id, tag_id
        )
        existing = await self._session.scalar(
            select(asset_tags.c.tag_id).where(
                asset_tags.c.asset_id == asset_id,
                asset_tags.c.tag_id == tag_id,
            )
        )
        if existing is None:
            await self._session.execute(
                insert(asset_tags).values(asset_id=asset_id, tag_id=tag_id)
            )
            await self._session.flush()

    async def detach_asset_tag(self, asset_id: int, tag_id: int) -> None:
        logger.debug(
            'Detaching tag from asset: asset_id=%s tag_id=%s',
            asset_id,
            tag_id,
        )
        await self._session.execute(
            delete(asset_tags).where(
                asset_tags.c.asset_id == asset_id,
                asset_tags.c.tag_id == tag_id,
            )
        )
        await self._session.flush()

    async def get_document_tags(self, document_id: int) -> list[TagDTO]:
        logger.debug('Listing document tags: document_id=%s', document_id)
        rows = list(
            (
                await self._session.scalars(
                    select(Tag)
                    .join(document_tags, document_tags.c.tag_id == Tag.id)
                    .where(document_tags.c.document_id == document_id)
                    .order_by(Tag.label, Tag.id)
                )
            ).all()
        )
        return [self._to_dto(row) for row in rows]

    async def attach_document_tag(self, document_id: int, tag_id: int) -> None:
        logger.debug(
            'Attaching tag to document: document_id=%s tag_id=%s',
            document_id,
            tag_id,
        )
        existing = await self._session.scalar(
            select(document_tags.c.tag_id).where(
                document_tags.c.document_id == document_id,
                document_tags.c.tag_id == tag_id,
            )
        )
        if existing is None:
            await self._session.execute(
                insert(document_tags).values(
                    document_id=document_id, tag_id=tag_id
                )
            )
            await self._session.flush()

    async def detach_document_tag(self, document_id: int, tag_id: int) -> None:
        logger.debug(
            'Detaching tag from document: document_id=%s tag_id=%s',
            document_id,
            tag_id,
        )
        await self._session.execute(
            delete(document_tags).where(
                document_tags.c.document_id == document_id,
                document_tags.c.tag_id == tag_id,
            )
        )
        await self._session.flush()
