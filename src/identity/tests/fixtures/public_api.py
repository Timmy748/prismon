import pytest

from identity.public_api import IdentityPublicAPI


@pytest.fixture
def identity_public_api(mock_user_repo, mock_token_provider):
    async def user_repository_factory():
        return mock_user_repo

    api = IdentityPublicAPI(
        user_repository_factory,
        lambda: mock_token_provider,
    )
    return api, mock_user_repo, mock_token_provider
