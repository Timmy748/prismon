import pytest

from identity.exceptions import UserNotFoundException
from identity.repositories.user import UserRepository


@pytest.mark.asyncio
async def test_create_user_returns_dto(
    user_repo: UserRepository,
) -> None:
    dto = await user_repo.create_user(
        username='john',
        email='john@example.com',
        password_hash='hashed',
    )

    assert dto.id is not None
    assert dto.username == 'john'
    assert dto.email == 'john@example.com'
    assert dto.password_hash == 'hashed'


@pytest.mark.asyncio
async def test_get_user_by_id_returns_dto(
    user_repo: UserRepository,
) -> None:
    created = await user_repo.create_user(
        username='john',
        email='john@example.com',
        password_hash='hashed',
    )

    dto = await user_repo.get_user_by_id(created.id)

    assert dto is not None
    assert dto.id == created.id
    assert dto.username == 'john'
    assert dto.password_hash == 'hashed'


@pytest.mark.asyncio
async def test_get_user_by_id_returns_none_when_not_found(
    user_repo: UserRepository,
) -> None:
    dto = await user_repo.get_user_by_id(999)

    assert dto is None


@pytest.mark.asyncio
async def test_get_user_by_email_returns_dto(
    user_repo: UserRepository,
) -> None:
    created = await user_repo.create_user(
        username='john',
        email='john@example.com',
        password_hash='hashed',
    )

    dto = await user_repo.get_user(email='john@example.com')

    assert dto is not None
    assert dto.id == created.id
    assert dto.email == 'john@example.com'


@pytest.mark.asyncio
async def test_get_user_by_username_returns_dto(
    user_repo: UserRepository,
) -> None:
    created = await user_repo.create_user(
        username='john',
        email='john@example.com',
        password_hash='hashed',
    )

    dto = await user_repo.get_user(username='john')

    assert dto is not None
    assert dto.id == created.id
    assert dto.username == 'john'


@pytest.mark.asyncio
async def test_get_user_by_email_or_username_returns_dto(
    user_repo: UserRepository,
) -> None:
    created = await user_repo.create_user(
        username='john',
        email='john@example.com',
        password_hash='hashed',
    )

    dto = await user_repo.get_user(email='other@example.com', username='john')

    assert dto is not None
    assert dto.id == created.id


@pytest.mark.asyncio
async def test_get_user_returns_none_when_not_found(
    user_repo: UserRepository,
) -> None:
    dto = await user_repo.get_user(
        email='notfound@example.com', username='notfound'
    )

    assert dto is None


@pytest.mark.asyncio
async def test_get_user_returns_none_when_no_arguments(
    user_repo: UserRepository,
) -> None:
    dto = await user_repo.get_user()

    assert dto is None


@pytest.mark.asyncio
async def test_update_user_changes_fields(
    user_repo: UserRepository,
) -> None:
    created = await user_repo.create_user(
        username='john',
        email='john@example.com',
        password_hash='hashed',
    )

    updated = await user_repo.update_user(
        id=created.id,
        username='johnny',
        email='johnny@example.com',
    )

    assert updated.username == 'johnny'
    assert updated.email == 'johnny@example.com'


@pytest.mark.asyncio
async def test_update_user_raises_when_not_found(
    user_repo: UserRepository,
) -> None:
    with pytest.raises(UserNotFoundException):
        await user_repo.update_user(
            id=999,
            username='ghost',
            email='ghost@example.com',
        )


@pytest.mark.asyncio
async def test_change_user_password_returns_dto(
    user_repo: UserRepository,
) -> None:
    created = await user_repo.create_user(
        username='john',
        email='john@example.com',
        password_hash='old_hash',
    )

    dto = await user_repo.change_user_password(
        id=created.id,
        password_hash='new_hash',
    )

    assert dto.id == created.id
    assert dto.password_hash == 'new_hash'


@pytest.mark.asyncio
async def test_change_user_password_raises_when_not_found(
    user_repo: UserRepository,
) -> None:
    with pytest.raises(UserNotFoundException):
        await user_repo.change_user_password(
            id=999,
            password_hash='new_hash',
        )


@pytest.mark.asyncio
async def test_delete_user_removes_user(
    user_repo: UserRepository,
) -> None:
    created = await user_repo.create_user(
        username='john',
        email='john@example.com',
        password_hash='hashed',
    )

    await user_repo.delete_user(created.id)

    assert await user_repo.get_user_by_id(created.id) is None


@pytest.mark.asyncio
async def test_delete_user_does_nothing_when_not_found(
    user_repo: UserRepository,
) -> None:
    await user_repo.delete_user(999)


@pytest.mark.asyncio
async def test_create_user_populates_timestamps(
    user_repo: UserRepository,
) -> None:
    dto = await user_repo.create_user(
        username='john',
        email='john@example.com',
        password_hash='hashed',
    )

    assert dto.created_at is not None
    assert dto.updated_at is not None
