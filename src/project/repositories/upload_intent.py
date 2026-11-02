# ruff: noqa: PLR0913, PLR0917
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.logs import get_logger
from project.dtos.upload_intent import UploadIntentDTO
from project.entities.upload_intent import UploadIntent

logger = get_logger(__name__)


class IUploadIntentRepository(Protocol):
    async def create_upload_intent(
        self,
        project_id: int,
        *,
        asset_id: int | None = None,
        document_id: int | None = None,
        object_key: str,
        final_file_key: str,
        started_by_member_id: int,
        target_status: str,
        expires_at: datetime,
        file_extension: str | None = None,
        content_type: str = 'application/octet-stream',
        previous_file_key: str | None = None,
    ) -> UploadIntentDTO: ...

    async def get_by_object_key(
        self, object_key: str
    ) -> UploadIntentDTO | None: ...

    async def get_by_object_key_for_update(
        self, object_key: str
    ) -> UploadIntentDTO | None: ...

    async def get_expired_upload_intents(
        self, now: datetime, limit: int = 100
    ) -> list[UploadIntentDTO]: ...

    async def delete_upload_intent(self, intent_id: int) -> None: ...


class UploadIntentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_dto(row: UploadIntent) -> UploadIntentDTO:
        return UploadIntentDTO(
            id=row.id,
            project_id=row.project_id,
            asset_id=row.asset_id,
            document_id=row.document_id,
            object_key=row.object_key,
            final_file_key=row.final_file_key,
            started_by_member_id=row.started_by_member_id,
            target_status=row.target_status,
            expires_at=row.expires_at,
            previous_file_key=row.previous_file_key,
            created_at=row.created_at,
            file_extension=row.file_extension,
            content_type=row.content_type,
        )

    async def create_upload_intent(
        self,
        project_id: int,
        *,
        asset_id: int | None = None,
        document_id: int | None = None,
        object_key: str,
        final_file_key: str,
        started_by_member_id: int,
        target_status: str,
        expires_at: datetime,
        file_extension: str | None = None,
        content_type: str = 'application/octet-stream',
        previous_file_key: str | None = None,
    ) -> UploadIntentDTO:
        logger.debug(
            'Creating upload intent: project_id=%s object_key=%s',
            project_id,
            object_key,
        )
        row = UploadIntent(
            project_id=project_id,
            asset_id=asset_id,
            document_id=document_id,
            object_key=object_key,
            final_file_key=final_file_key,
            started_by_member_id=started_by_member_id,
            target_status=target_status,
            file_extension=file_extension,
            content_type=content_type,
            expires_at=expires_at,
            previous_file_key=previous_file_key,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._to_dto(row)

    async def get_by_object_key(
        self, object_key: str
    ) -> UploadIntentDTO | None:
        row = await self._session.scalar(
            select(UploadIntent).where(UploadIntent.object_key == object_key)
        )
        return self._to_dto(row) if row is not None else None

    async def get_by_object_key_for_update(
        self, object_key: str
    ) -> UploadIntentDTO | None:
        row = await self._session.scalar(
            select(UploadIntent)
            .where(UploadIntent.object_key == object_key)
            .with_for_update()
        )
        return self._to_dto(row) if row is not None else None

    async def get_expired_upload_intents(
        self, now: datetime, limit: int = 100
    ) -> list[UploadIntentDTO]:
        bounded_limit = max(1, min(limit, 500))
        rows = list(
            (
                await self._session.scalars(
                    select(UploadIntent)
                    .where(UploadIntent.expires_at <= now)
                    .order_by(UploadIntent.expires_at, UploadIntent.id)
                    .with_for_update(skip_locked=True)
                    .limit(bounded_limit)
                )
            ).all()
        )
        return [self._to_dto(row) for row in rows]

    async def delete_upload_intent(self, intent_id: int) -> None:
        row = await self._session.get(UploadIntent, intent_id)
        if row is None:
            return
        await self._session.delete(row)
        await self._session.flush()
