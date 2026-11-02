# ruff: noqa: PLR0913, PLR0917
from typing import Protocol

from sqlalchemy import literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from infra.logs import get_logger
from project.dtos.asset import AssetDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.tag import TagDTO
from project.entities.asset import Asset, AssetStatus

logger = get_logger(__name__)


class IAssetRepository(Protocol):
    async def get_asset(self, asset_id: int) -> AssetDTO | None: ...
    async def get_assets(
        self,
        project_id: int,
        pagination: PaginationDTO = PaginationDTO(),
        asset_type: str | None = None,
        status: AssetStatus | None = None,
    ) -> CursorPage[AssetDTO]: ...
    async def create_asset(
        self,
        project_id: int,
        file: str | None,
        asset_type: str,
        created_by_member_id: int,
        description: str | None = None,
        status: AssetStatus = AssetStatus.ACTIVE,
        name: str = '',
        file_extension: str | None = None,
        content_type: str | None = None,
    ) -> AssetDTO: ...
    async def update_asset(
        self,
        asset_id: int,
        file: str | None = None,
        asset_type: str | None = None,
        description: str | None = None,
        status: AssetStatus | None = None,
        name: str | None = None,
        file_extension: str | None = None,
        content_type: str | None = None,
    ) -> AssetDTO | None: ...
    async def delete_asset(self, asset_id: int) -> None: ...


class AssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_dto(self, row: Asset) -> AssetDTO:
        return AssetDTO(
            row.id,
            row.project_id,
            row.created_by_member_id,
            row.file,
            row.type,
            row.description,
            row.status,
            row.created_at,
            row.updated_at,
            [
                TagDTO(
                    id=tag.id,
                    project_id=tag.project_id,
                    label=tag.label,
                    description=tag.description,
                    color=tag.color,
                )
                for tag in row.tags
            ],
            row.name,
            row.file_extension,
            row.content_type,
        )

    async def get_asset(self, asset_id: int) -> AssetDTO | None:
        logger.debug('Loading asset repository record: asset_id=%s', asset_id)
        row = await self._session.get(
            Asset, asset_id, options=[selectinload(Asset.tags)]
        )
        return self._to_dto(row) if row else None

    async def get_assets(
        self,
        project_id: int,
        pagination: PaginationDTO = PaginationDTO(),
        asset_type: str | None = None,
        status: AssetStatus | None = None,
    ) -> CursorPage[AssetDTO]:
        logger.debug(
            'Listing asset repository records: project_id=%s', project_id
        )
        limit = max(1, min(pagination.limit, 100))
        stmt = (
            select(Asset)
            .options(selectinload(Asset.tags))
            .where(Asset.project_id == project_id)
        )
        if pagination.cursor is not None:
            stmt = stmt.where(
                tuple_(Asset.updated_at, Asset.id)
                < tuple_(
                    literal(pagination.cursor[0]), literal(pagination.cursor[1])
                )
            )
        if asset_type:
            stmt = stmt.where(Asset.type == asset_type)
        if status is not None:
            stmt = stmt.where(Asset.status == status)
        rows = list(
            (
                await self._session.scalars(
                    stmt.order_by(
                        Asset.updated_at.desc(), Asset.id.desc()
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

    async def create_asset(
        self,
        project_id: int,
        file: str | None,
        asset_type: str,
        created_by_member_id: int,
        description: str | None = None,
        status: AssetStatus = AssetStatus.ACTIVE,
        name: str = '',
        file_extension: str | None = None,
        content_type: str | None = None,
    ) -> AssetDTO:
        logger.debug(
            'Creating asset repository record: project_id=%s', project_id
        )
        row = Asset(
            project_id=project_id,
            created_by_member_id=created_by_member_id,
            file=file,
            name=name,
            type=asset_type,
            description=description,
            status=status,
            file_extension=file_extension,
            content_type=content_type,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        row.tags = []
        return self._to_dto(row)

    async def update_asset(
        self,
        asset_id: int,
        file: str | None = None,
        asset_type: str | None = None,
        description: str | None = None,
        status: AssetStatus | None = None,
        name: str | None = None,
        file_extension: str | None = None,
        content_type: str | None = None,
    ) -> AssetDTO | None:
        logger.debug('Updating asset repository record: asset_id=%s', asset_id)
        row = await self._session.get(
            Asset, asset_id, options=[selectinload(Asset.tags)]
        )
        if row is None:
            return None
        if file is not None:
            row.file = file
        if asset_type is not None:
            row.type = asset_type
        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        if status is not None:
            row.status = status
        if file_extension is not None:
            row.file_extension = file_extension
        if content_type is not None:
            row.content_type = content_type
        await self._session.flush()
        await self._session.refresh(row)
        return self._to_dto(row)

    async def delete_asset(self, asset_id: int) -> None:
        logger.debug('Deleting asset repository record: asset_id=%s', asset_id)
        row = await self._session.get(Asset, asset_id)
        if row is None:
            return
        await self._session.delete(row)
        await self._session.flush()
