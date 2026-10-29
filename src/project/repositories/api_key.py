from typing import Protocol

from sqlalchemy import literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from project.dtos.api_key import ApiKeyDTO, CreateApiKeyDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.api_key import ApiKey


class IApiKeyRepository(Protocol):
    async def create_api_key(self, data: CreateApiKeyDTO) -> ApiKeyDTO: ...
    async def get_api_key(self, api_key_id: int) -> ApiKeyDTO | None: ...
    async def list_member_api_keys(
        self, member_id: int, pagination: PaginationDTO = PaginationDTO()
    ) -> CursorPage[ApiKeyDTO]: ...
    async def list_project_api_keys(
        self, project_id: int, pagination: PaginationDTO = PaginationDTO()
    ) -> CursorPage[ApiKeyDTO]: ...
    async def delete_api_key(self, api_key_id: int) -> None: ...


class ApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_dto(row: ApiKey) -> ApiKeyDTO:
        return ApiKeyDTO(
            id=row.id,
            provider=row.provider,
            api_hint=row.api_hint,
            encrypted_api_key=row.encrypted_api_key,
            encrypted_dek=row.encrypted_dek,
            api_key_nonce=row.api_key_nonce,
            dek_nonce=row.dek_nonce,
            member_id=row.member_id,
            project_id=row.project_id,
            created_at=row.created_at,
        )

    async def create_api_key(self, data: CreateApiKeyDTO) -> ApiKeyDTO:
        row = ApiKey(
            provider=data.provider,
            api_hint=data.api_hint,
            encrypted_api_key=data.encrypted_api_key,
            encrypted_dek=data.encrypted_dek,
            api_key_nonce=data.api_key_nonce,
            dek_nonce=data.dek_nonce,
            member_id=data.member_id,
            project_id=data.project_id,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._to_dto(row)

    async def get_api_key(self, api_key_id: int) -> ApiKeyDTO | None:
        row = await self._session.get(ApiKey, api_key_id)
        return self._to_dto(row) if row is not None else None

    async def _list_api_keys(
        self, condition: ColumnElement[bool], pagination: PaginationDTO
    ) -> CursorPage[ApiKeyDTO]:
        limit = max(1, min(pagination.limit, 100))
        stmt = select(ApiKey).where(condition)
        if pagination.cursor is not None:
            stmt = stmt.where(
                tuple_(ApiKey.created_at, ApiKey.id)
                < tuple_(
                    literal(pagination.cursor[0]), literal(pagination.cursor[1])
                )
            )
        rows = list(
            (
                await self._session.scalars(
                    stmt.order_by(
                        ApiKey.created_at.desc(), ApiKey.id.desc()
                    ).limit(limit + 1)
                )
            ).all()
        )
        more = len(rows) > limit
        rows = rows[:limit]
        cursor = (rows[-1].created_at, rows[-1].id) if more and rows else None
        return CursorPage(
            [self._to_dto(row) for row in rows],
            PaginationDTO(cursor=cursor, limit=limit, more=more),
        )

    async def list_member_api_keys(
        self, member_id: int, pagination: PaginationDTO = PaginationDTO()
    ) -> CursorPage[ApiKeyDTO]:
        return await self._list_api_keys(
            ApiKey.member_id == member_id, pagination
        )

    async def list_project_api_keys(
        self, project_id: int, pagination: PaginationDTO = PaginationDTO()
    ) -> CursorPage[ApiKeyDTO]:
        return await self._list_api_keys(
            ApiKey.project_id == project_id, pagination
        )

    async def delete_api_key(self, api_key_id: int) -> None:
        row = await self._session.get(ApiKey, api_key_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()
