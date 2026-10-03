from datetime import UTC, datetime

import pytest

from identity.dtos.user import UserDTO


@pytest.mark.asyncio
async def test_public_api_get_by_id(identity_public_api):
    api, user_repo, _ = identity_public_api
    user = UserDTO(
        id=15,
        username='public',
        email='public@example.com',
        password_hash='hash',
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    user_repo.get_user_by_id.return_value = user

    result = await api.get_by_id(15)

    assert result == user
    user_repo.get_user_by_id.assert_awaited_once_with(15)


@pytest.mark.asyncio
async def test_public_api_get_current_user(identity_public_api):
    api, user_repo, token_provider = identity_public_api
    user = UserDTO(
        id=15,
        username='public',
        email='public@example.com',
        password_hash='hash',
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    user_repo.get_user_by_id.return_value = user
    token_provider.decode_access_token.return_value = {'sub': '15'}

    result = await api.get_current_user('valid-token')

    assert result == user
    token_provider.decode_access_token.assert_called_once_with('valid-token')
    user_repo.get_user_by_id.assert_awaited_once_with(15)
