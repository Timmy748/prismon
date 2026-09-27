from datetime import datetime, timedelta, timezone

import pytest

from identity.repositories.token import RefreshTokenRepository
from identity.repositories.user import UserRepository


@pytest.mark.asyncio
async def test_create_refresh_token_returns_dto(
    token_repo: RefreshTokenRepository,
    user_repo: UserRepository,
) -> None:
    user = await user_repo.create_user(
        username='john',
        email='john@example.com',
        password_hash='hashed',
    )
    expires = datetime.now(timezone.utc) + timedelta(days=7)

    dto = await token_repo.create_refresh_token(
        user_id=user.id,
        token_hash='abc123',
        expires_at=expires,
    )

    assert dto.id is not None
    assert dto.user_id == user.id
    assert dto.token_hash == 'abc123'
    assert dto.revoked is False


@pytest.mark.asyncio
async def test_get_refresh_token_by_token_returns_dto(
    token_repo: RefreshTokenRepository,
    user_repo: UserRepository,
) -> None:
    user = await user_repo.create_user(
        username='john',
        email='john@example.com',
        password_hash='hashed',
    )
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    await token_repo.create_refresh_token(
        user_id=user.id,
        token_hash='abc123',
        expires_at=expires,
    )

    dto = await token_repo.get_refresh_token_by_token('abc123')

    assert dto is not None
    assert dto.token_hash == 'abc123'


@pytest.mark.asyncio
async def test_get_refresh_token_by_token_returns_none_when_not_found(
    token_repo: RefreshTokenRepository,
) -> None:
    dto = await token_repo.get_refresh_token_by_token('nonexistent')

    assert dto is None


@pytest.mark.asyncio
async def test_revoke_refresh_token_sets_revoked(
    token_repo: RefreshTokenRepository,
    user_repo: UserRepository,
) -> None:
    user = await user_repo.create_user(
        username='john',
        email='john@example.com',
        password_hash='hashed',
    )
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    created = await token_repo.create_refresh_token(
        user_id=user.id,
        token_hash='abc123',
        expires_at=expires,
    )

    await token_repo.revoke_refresh_token(created.id)

    dto = await token_repo.get_refresh_token_by_token('abc123')
    assert dto is not None
    assert dto.revoked is True


@pytest.mark.asyncio
async def test_revoke_refresh_token_does_nothing_when_not_found(
    token_repo: RefreshTokenRepository,
) -> None:
    await token_repo.revoke_refresh_token(999)


@pytest.mark.asyncio
async def test_revoke_refresh_tokens_by_user_id_revokes_all(
    token_repo: RefreshTokenRepository,
    user_repo: UserRepository,
) -> None:
    user_1 = await user_repo.create_user(
        username='john',
        email='john@example.com',
        password_hash='hashed',
    )
    user_2 = await user_repo.create_user(
        username='jane',
        email='jane@example.com',
        password_hash='hashed',
    )
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    await token_repo.create_refresh_token(
        user_id=user_1.id,
        token_hash='token_a',
        expires_at=expires,
    )
    await token_repo.create_refresh_token(
        user_id=user_1.id,
        token_hash='token_b',
        expires_at=expires,
    )
    await token_repo.create_refresh_token(
        user_id=user_2.id,
        token_hash='token_c',
        expires_at=expires,
    )

    await token_repo.revoke_refresh_tokens_by_user_id(user_1.id)

    token_a = await token_repo.get_refresh_token_by_token('token_a')
    token_b = await token_repo.get_refresh_token_by_token('token_b')
    token_c = await token_repo.get_refresh_token_by_token('token_c')

    assert token_a is not None and token_a.revoked is True
    assert token_b is not None and token_b.revoked is True
    assert token_c is not None and token_c.revoked is False
