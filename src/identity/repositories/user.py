from typing import Protocol

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logs import get_logger
from identity.dtos.user import UserDTO
from identity.entities.user import User
from identity.exceptions import UserNotFoundException

logger = get_logger(__name__)


class IUserRepository(Protocol):
    async def get_user_by_id(self, id: int) -> UserDTO | None: ...

    async def get_user(
        self, email: str | None = None, username: str | None = None
    ) -> UserDTO | None: ...

    async def create_user(
        self, username: str, email: str, password_hash: str
    ) -> UserDTO: ...

    async def update_user(
        self, id: int, username: str | None, email: str | None
    ) -> UserDTO: ...

    async def change_user_password(
        self, id: int, password_hash: str
    ) -> UserDTO: ...

    async def delete_user(self, id: int) -> None: ...


class UserRepository(IUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_by_id(self, id: int) -> UserDTO | None:
        user = await self._session.get(User, id)
        if user is None:
            logger.debug('User repository lookup by ID found no record')
            return None
        logger.debug('User repository lookup by ID completed')
        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def get_user(
        self, email: str | None = None, username: str | None = None
    ) -> UserDTO | None:
        conditions = []
        if email is not None:
            conditions.append(User.email == email)
        if username is not None:
            conditions.append(User.username == username)

        if not conditions:
            logger.debug('User repository lookup skipped: no criteria provided')
            return None

        stmt = select(User).where(or_(*conditions))
        result = await self._session.execute(stmt)
        user = result.scalars().first()

        if user is None:
            logger.debug('User repository lookup found no record')
            return None

        logger.debug('User repository lookup completed')
        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def create_user(
        self, username: str, email: str, password_hash: str
    ) -> UserDTO:
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        logger.debug('User repository create completed')
        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def update_user(
        self, id: int, username: str | None, email: str | None
    ) -> UserDTO:
        user = await self._session.get(User, id)
        if user is None:
            logger.warning('User repository update failed: record not found')
            raise UserNotFoundException(id)

        if username is not None:
            user.username = username
        if email is not None:
            user.email = email

        await self._session.flush()
        await self._session.refresh(user)
        logger.debug('User repository update completed')
        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def change_user_password(
        self, id: int, password_hash: str
    ) -> UserDTO:
        user = await self._session.get(User, id)
        if user is None:
            logger.warning(
                'User repository password update failed: record not found'
            )
            raise UserNotFoundException(id)
        user.password_hash = password_hash
        await self._session.flush()
        await self._session.refresh(user)
        logger.debug('User repository password update completed')
        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def delete_user(self, id: int) -> None:
        user = await self._session.get(User, id)
        if user is not None:
            await self._session.delete(user)
            await self._session.flush()
            logger.debug('User repository delete completed')
        else:
            logger.debug('User repository delete skipped: record not found')
