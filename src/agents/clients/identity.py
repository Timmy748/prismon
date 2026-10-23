from typing import Protocol

from agents.dtos.user import UserDTO
from agents.exceptions import (
    IdentityServiceException,
    UserAuthenticationException,
    UserNotFoundException,
)
from identity.dtos.user import UserDTO as IdentityUserDTO
from identity.exceptions import (
    IdentityException,
    InvalidCredentialsException,
    InvalidTokenException,
    TokenExpiredException,
)
from identity.exceptions import (
    UserNotFoundException as IdentityUserNotFoundException,
)
from identity.public_api import IdentityPublicAPI
from identity.security.jwt import create_token_provider
from identity.unit_of_work import create_identity_unit_of_work


class IIdentityClient(Protocol):
    async def get_by_id(self, user_id: int) -> UserDTO: ...

    async def get_current_user(self, access_token: str) -> UserDTO: ...


class IdentityClient:
    def __init__(self, identity_api: IdentityPublicAPI) -> None:
        self._identity_api = identity_api

    @staticmethod
    def _to_agents_user(user: IdentityUserDTO) -> UserDTO:
        return UserDTO(id=user.id, username=user.username, email=user.email)

    async def get_by_id(self, user_id: int) -> UserDTO:
        try:
            user = await self._identity_api.get_by_id(user_id)
        except IdentityUserNotFoundException as error:
            raise UserNotFoundException(user_id) from error
        except IdentityException as error:
            raise IdentityServiceException() from error
        return self._to_agents_user(user)

    async def get_current_user(self, access_token: str) -> UserDTO:
        try:
            user = await self._identity_api.get_current_user(access_token)
        except (
            InvalidCredentialsException,
            InvalidTokenException,
            TokenExpiredException,
        ) as error:
            raise UserAuthenticationException() from error
        except IdentityException as error:
            raise IdentityServiceException() from error
        return self._to_agents_user(user)


def create_identity_client() -> IdentityClient:
    api = IdentityPublicAPI(
        unit_of_work_factory=create_identity_unit_of_work,
        token_provider_factory=create_token_provider,
    )
    return IdentityClient(api)
