import pytest

from identity.public_api import IdentityPublicAPI


@pytest.fixture
def identity_public_api(mock_unit_of_work, mock_token_provider):
    api = IdentityPublicAPI(
        lambda: mock_unit_of_work,
        lambda: mock_token_provider,
    )
    return api, mock_unit_of_work.user_repository, mock_token_provider
