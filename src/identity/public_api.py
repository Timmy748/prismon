"""Public facade exposed by Identity to other domains."""

from collections.abc import Awaitable, Callable

from identity.dtos.user import UserDTO
from identity.repositories.user import IUserRepository
from identity.security.jwt import ITokenProvider
from identity.use_cases.user import get_current_user, get_user_by_id


class IdentityPublicAPI:
    """Prepare Identity dependencies and expose its supported use cases."""

    def __init__(
        self,
        user_repository_factory: Callable[[], Awaitable[IUserRepository]],
        token_provider_factory: Callable[[], ITokenProvider],
    ) -> None:
        self._user_repository_factory = user_repository_factory
        self._token_provider_factory = token_provider_factory

    async def get_by_id(self, user_id: int) -> UserDTO:
        return await get_user_by_id(
            await self._user_repository_factory(), user_id
        )

    async def get_current_user(self, access_token: str) -> UserDTO:
        return await get_current_user(
            await self._user_repository_factory(),
            self._token_provider_factory(),
            access_token,
        )
