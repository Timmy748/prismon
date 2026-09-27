from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from identity.dtos.user import UserDTO
from identity.entities.user import User
from identity.exceptions import UserNotFoundException


class IUserRepository(Protocol):
    async def get_user_by_id(self, id: int) -> UserDTO | None: ...

    async def create_user(
        self, username: str, email: str, password_hash: str
    ) -> UserDTO: ...

    async def update_user(
        self, id: int, username: str, email: str
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
            return None
        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
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
        await self._session.commit()
        await self._session.refresh(user)
        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def update_user(self, id: int, username: str, email: str) -> UserDTO:
        user = await self._session.get(User, id)
        if user is None:
            raise UserNotFoundException(id)
        user.username = username
        user.email = email
        await self._session.commit()
        await self._session.refresh(user)
        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def change_user_password(
        self, id: int, password_hash: str
    ) -> UserDTO:
        user = await self._session.get(User, id)
        if user is None:
            raise UserNotFoundException(id)
        user.password_hash = password_hash
        await self._session.commit()
        await self._session.refresh(user)
        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def delete_user(self, id: int) -> None:
        user = await self._session.get(User, id)
        if user is not None:
            await self._session.delete(user)
            await self._session.commit()
