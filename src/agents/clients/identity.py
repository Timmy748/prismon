from typing import Protocol

from agents.dtos.user import UserDTO
from agents.exceptions import (
    IdentityServiceException,
    UserAuthenticationException,
    UserNotFoundException,
)
from core.logs import get_logger
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

logger = get_logger(__name__)


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
            logger.info('Identity lookup found no user: user_id=%d', user_id)
            raise UserNotFoundException(user_id) from error
        except IdentityException as error:
            logger.warning('Identity lookup failed: user_id=%d', user_id)
            raise IdentityServiceException() from error
        logger.debug('Identity lookup succeeded: user_id=%d', user_id)
        return self._to_agents_user(user)

    async def get_current_user(self, access_token: str) -> UserDTO:
        try:
            user = await self._identity_api.get_current_user(access_token)
        except (
            InvalidCredentialsException,
            InvalidTokenException,
            TokenExpiredException,
        ) as error:
            logger.info('Identity token authentication was rejected')
            raise UserAuthenticationException() from error
        except IdentityException as error:
            logger.warning('Identity current-user lookup failed')
            raise IdentityServiceException() from error
        logger.debug(
            'Identity current-user lookup succeeded: user_id=%d', user.id
        )
        return self._to_agents_user(user)


def create_identity_client() -> IdentityClient:
    api = IdentityPublicAPI(
        unit_of_work_factory=create_identity_unit_of_work,
        token_provider_factory=create_token_provider,
    )
    return IdentityClient(api)
