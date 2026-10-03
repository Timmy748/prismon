"""Anti-corruption client for the Identity domain."""

from typing import Protocol

from identity.exceptions import (
    IdentityException,
    InvalidCredentialsException,
    InvalidTokenException,
    TokenExpiredException,
    UserNotFoundException,
)
from identity.public_api import IdentityPublicAPI
from identity.repositories.user import create_user_repository
from identity.security.jwt import create_token_provider
from project.dtos.user import UserDTO
from project.exceptions import (
    ProjectUserAuthenticationException,
    ProjectUserNotFoundException,
    ProjectUserServiceException,
)


class IUserClient(Protocol):
    async def get_by_id(self, user_id: int) -> UserDTO: ...
    async def get_current_user(self, access_token: str) -> UserDTO: ...


class IdentityClient:
    """Expose Identity users using Project-owned DTOs."""

    def __init__(self, identity_api: IdentityPublicAPI) -> None:
        self._identity_api = identity_api

    async def get_by_id(self, user_id: int) -> UserDTO:
        try:
            user = await self._identity_api.get_by_id(user_id)
        except UserNotFoundException as error:
            raise ProjectUserNotFoundException(user_id) from error
        except IdentityException as error:
            raise ProjectUserServiceException() from error
        return UserDTO(id=user.id, username=user.username, email=user.email)

    async def get_current_user(self, access_token: str) -> UserDTO:
        try:
            user = await self._identity_api.get_current_user(access_token)
        except (
            InvalidCredentialsException,
            InvalidTokenException,
            TokenExpiredException,
        ) as error:
            raise ProjectUserAuthenticationException() from error
        except IdentityException as error:
            raise ProjectUserServiceException() from error
        return UserDTO(id=user.id, username=user.username, email=user.email)


def create_identity_client() -> IdentityClient:
    return IdentityClient(
        IdentityPublicAPI(create_user_repository, create_token_provider)
    )
