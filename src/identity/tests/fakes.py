from datetime import datetime

from identity.dtos.token import RefreshTokenDTO
from identity.dtos.user import UserDTO
from identity.exceptions import UserNotFoundException
from identity.repositories.user import IUserRepository


class FakeUserRepository(IUserRepository):
    def __init__(self) -> None:
        self._users: dict[int, dict] = {}
        self._next_id = 1

    async def get_user_by_id(self, id: int) -> UserDTO | None:
        user = self._users.get(id)
        if user is None:
            return None
        return UserDTO(
            id=user['id'],
            username=user['username'],
            email=user['email'],
            created_at=user['created_at'],
            updated_at=user['updated_at'],
        )

    async def create_user(
        self, username: str, email: str, password_hash: str
    ) -> UserDTO:
        now = datetime.now()
        user = {
            'id': self._next_id,
            'username': username,
            'email': email,
            'password_hash': password_hash,
            'created_at': now,
            'updated_at': now,
        }
        self._users[self._next_id] = user
        self._next_id += 1
        return UserDTO(
            id=user['id'],
            username=user['username'],
            email=user['email'],
            created_at=user['created_at'],
            updated_at=user['updated_at'],
        )

    async def update_user(self, id: int, username: str, email: str) -> UserDTO:
        user = self._users.get(id)
        if user is None:
            raise UserNotFoundException(id)
        user['username'] = username
        user['email'] = email
        user['updated_at'] = datetime.now()
        return UserDTO(
            id=user['id'],
            username=user['username'],
            email=user['email'],
            created_at=user['created_at'],
            updated_at=user['updated_at'],
        )

    async def change_user_password(
        self, id: int, password_hash: str
    ) -> UserDTO:
        user = self._users.get(id)
        if user is None:
            raise UserNotFoundException(id)
        user['password_hash'] = password_hash
        user['updated_at'] = datetime.now()
        return UserDTO(
            id=user['id'],
            username=user['username'],
            email=user['email'],
            created_at=user['created_at'],
            updated_at=user['updated_at'],
        )

    async def delete_user(self, id: int) -> None:
        self._users.pop(id, None)


class FakeRefreshTokenRepository(IUserRepository):
    def __init__(self) -> None:
        self._tokens: dict[int, dict] = {}
        self._next_id = 1

    async def create_refresh_token(
        self, user_id: int, token_hash: str, expires_at: datetime
    ) -> RefreshTokenDTO:
        token = {
            'id': self._next_id,
            'user_id': user_id,
            'token_hash': token_hash,
            'expires_at': expires_at,
            'revoked': False,
        }
        self._tokens[self._next_id] = token
        self._next_id += 1
        return RefreshTokenDTO(
            id=token['id'],
            user_id=token['user_id'],
            token_hash=token['token_hash'],
            expires_at=token['expires_at'],
            revoked=token['revoked'],
        )

    async def get_refresh_token_by_token(
        self, token_hash: str
    ) -> RefreshTokenDTO | None:
        for token in self._tokens.values():
            if token['token_hash'] == token_hash:
                return RefreshTokenDTO(
                    id=token['id'],
                    user_id=token['user_id'],
                    token_hash=token['token_hash'],
                    expires_at=token['expires_at'],
                    revoked=token['revoked'],
                )
        return None

    async def revoke_refresh_token(self, id: int) -> None:
        token = self._tokens.get(id)
        if token is not None:
            token['revoked'] = True

    async def revoke_refresh_tokens_by_user_id(self, user_id: int) -> None:
        for token in self._tokens.values():
            if token['user_id'] == user_id:
                token['revoked'] = True
