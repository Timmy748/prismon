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
from identity.security.jwt import create_token_provider
from identity.unit_of_work import create_identity_unit_of_work
from infra.logs import get_logger
from project.dtos.user import UserDTO
from project.exceptions import (
    ProjectUserAuthenticationException,
    ProjectUserNotFoundException,
    ProjectUserServiceException,
)

logger = get_logger(__name__)


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
            logger.info(
                'Identity user lookup returned no user: user_id=%s', user_id
            )
            raise ProjectUserNotFoundException(user_id) from error
        except IdentityException as error:
            logger.exception('Identity user lookup failed: user_id=%s', user_id)
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
            logger.warning('Identity rejected current user authentication')
            raise ProjectUserAuthenticationException() from error
        except IdentityException as error:
            logger.exception('Identity current user lookup failed')
            raise ProjectUserServiceException() from error
        return UserDTO(id=user.id, username=user.username, email=user.email)


def create_identity_client() -> IdentityClient:
    return IdentityClient(
        IdentityPublicAPI(create_identity_unit_of_work, create_token_provider)
    )
