"""Public facade exposed by Identity to other domains."""

from collections.abc import Callable

from core.logs import get_logger
from identity.dtos.user import UserDTO
from identity.security.jwt import ITokenProvider
from identity.unit_of_work import IIdentityUnitOfWork
from identity.use_cases.user import get_current_user, get_user_by_id

logger = get_logger(__name__)


class IdentityPublicAPI:
    """Prepare Identity dependencies and expose its supported use cases."""

    def __init__(
        self,
        unit_of_work_factory: Callable[[], IIdentityUnitOfWork],
        token_provider_factory: Callable[[], ITokenProvider],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._token_provider_factory = token_provider_factory

    async def get_by_id(self, user_id: int) -> UserDTO:
        logger.debug('Identity public API user lookup started')
        async with self._unit_of_work_factory() as uow:
            user = await get_user_by_id(uow, user_id)
        logger.debug('Identity public API user lookup completed')
        return user

    async def get_current_user(self, access_token: str) -> UserDTO:
        logger.debug('Identity public API current-user lookup started')
        async with self._unit_of_work_factory() as uow:
            user = await get_current_user(
                uow,
                self._token_provider_factory(),
                access_token,
            )
        logger.debug('Identity public API current-user lookup completed')
        return user
