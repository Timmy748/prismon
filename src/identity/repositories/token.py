from datetime import datetime
from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from identity.database import get_session_factory
from identity.dtos.token import RefreshTokenDTO
from identity.entities.token import RefreshToken


class IRefreshTokenRepository(Protocol):
    async def create_refresh_token(
        self, user_id: int, token_hash: str, expires_at: datetime
    ) -> RefreshTokenDTO: ...

    async def get_refresh_token_by_token(
        self, token_hash: str
    ) -> RefreshTokenDTO | None: ...

    async def revoke_refresh_token(self, id: int) -> None: ...

    async def revoke_refresh_tokens_by_user_id(self, user_id: int) -> None: ...


class RefreshTokenRepository(IRefreshTokenRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_refresh_token(
        self, user_id: int, token_hash: str, expires_at: datetime
    ) -> RefreshTokenDTO:
        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(refresh_token)
        await self._session.commit()
        await self._session.refresh(refresh_token)
        return RefreshTokenDTO(
            id=refresh_token.id,
            user_id=refresh_token.user_id,
            token_hash=refresh_token.token_hash,
            expires_at=refresh_token.expires_at,
            revoked=refresh_token.revoked,
        )

    async def get_refresh_token_by_token(
        self, token_hash: str
    ) -> RefreshTokenDTO | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self._session.execute(stmt)
        token = result.scalar_one_or_none()
        if token is None:
            return None
        return RefreshTokenDTO(
            id=token.id,
            user_id=token.user_id,
            token_hash=token.token_hash,
            expires_at=token.expires_at,
            revoked=token.revoked,
        )

    async def revoke_refresh_token(self, id: int) -> None:
        token = await self._session.get(RefreshToken, id)
        if token is not None:
            token.revoked = True
            await self._session.commit()

    async def revoke_refresh_tokens_by_user_id(self, user_id: int) -> None:
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .values(revoked=True)
        )
        await self._session.execute(stmt)
        await self._session.commit()


async def create_refresh_token_repository() -> IRefreshTokenRepository:
    session_maker = get_session_factory()
    async with session_maker() as session:
        return RefreshTokenRepository(session)
