"""Public facade exposed by Identity to other domains."""

from collections.abc import Callable

from identity.dtos.user import UserDTO
from identity.security.jwt import ITokenProvider
from identity.unit_of_work import IIdentityUnitOfWork
from identity.use_cases.user import get_current_user, get_user_by_id


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
        async with self._unit_of_work_factory() as uow:
            return await get_user_by_id(uow, user_id)

    async def get_current_user(self, access_token: str) -> UserDTO:
        async with self._unit_of_work_factory() as uow:
            return await get_current_user(
                uow,
                self._token_provider_factory(),
                access_token,
            )
