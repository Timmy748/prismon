# ruff: noqa: PLR0913, PLR0917
from typing import Protocol

from sqlalchemy import literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from project.database import get_session_factory
from project.dtos.asset import AssetDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.asset import Asset, AssetStatus


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
        file: str,
        asset_type: str,
        description: str | None = None,
        status: AssetStatus = AssetStatus.ACTIVE,
    ) -> AssetDTO: ...
    async def update_asset(
        self,
        asset_id: int,
        file: str | None = None,
        asset_type: str | None = None,
        description: str | None = None,
        status: AssetStatus | None = None,
    ) -> AssetDTO | None: ...
    async def delete_asset(self, asset_id: int) -> None: ...


class AssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_dto(self, row: Asset) -> AssetDTO:
        return AssetDTO(
            row.id,
            row.project_id,
            row.file,
            row.type,
            row.description,
            row.status,
            row.created_at,
            row.updated_at,
        )

    async def get_asset(self, asset_id: int) -> AssetDTO | None:
        row = await self._session.get(Asset, asset_id)
        return self._to_dto(row) if row else None

    async def get_assets(
        self,
        project_id: int,
        pagination: PaginationDTO = PaginationDTO(),
        asset_type: str | None = None,
        status: AssetStatus | None = None,
    ) -> CursorPage[AssetDTO]:
        limit = max(1, min(pagination.limit, 100))
        stmt = select(Asset).where(Asset.project_id == project_id)
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
        file: str,
        asset_type: str,
        description: str | None = None,
        status: AssetStatus = AssetStatus.ACTIVE,
    ) -> AssetDTO:
        row = Asset(
            project_id=project_id,
            file=file,
            type=asset_type,
            description=description,
            status=status,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_dto(row)

    async def update_asset(
        self,
        asset_id: int,
        file: str | None = None,
        asset_type: str | None = None,
        description: str | None = None,
        status: AssetStatus | None = None,
    ) -> AssetDTO | None:
        row = await self._session.get(Asset, asset_id)
        if row is None:
            return None
        if file is not None:
            row.file = file
        if asset_type is not None:
            row.type = asset_type
        if description is not None:
            row.description = description
        if status is not None:
            row.status = status
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_dto(row)

    async def delete_asset(self, asset_id: int) -> None:
        row = await self._session.get(Asset, asset_id)
        if row is None:
            return
        await self._session.delete(row)
        await self._session.commit()


async def create_asset_repository() -> IAssetRepository:  # pragma: no cover
    session_maker = get_session_factory()
    async with session_maker() as session:
        return AssetRepository(session)
