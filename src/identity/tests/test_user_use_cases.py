from datetime import datetime, timezone

import pytest

from identity.dtos.user import (
    CreateUserDTO,
    UpdateUserDTO,
    UpdateUserPasswordDTO,
    UserDTO,
)
from identity.exceptions import (
    IncorrectPasswordException,
    UserAlreadyExistsException,
    UserNotFoundException,
)
from identity.use_cases.user import (
    change_password,
    create_user,
    delete_user,
    get_user_by_id,
    update_user,
)


@pytest.mark.asyncio
async def test_create_user_success(mock_user_repo, mock_password_hasher):
    created_user = UserDTO(
        id=1,
        username='newuser',
        email='new@example.com',
        password_hash='hashed_pw',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_user_repo.get_user.return_value = None
    mock_password_hasher.hash.return_value = 'hashed_pw'
    mock_user_repo.create_user.return_value = created_user

    dto = CreateUserDTO(
        username='newuser', email='new@example.com', password_hash='secret'
    )
    result = await create_user(
        user_repo=mock_user_repo,
        password_hasher=mock_password_hasher,
        data=dto,
    )

    assert result == created_user


@pytest.mark.asyncio
async def test_create_user_email_already_exists(
    mock_user_repo, mock_password_hasher
):
    existing_user = UserDTO(
        id=1,
        username='otheruser',
        email='existing@example.com',
        password_hash='hashed_pw',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_user_repo.get_user.return_value = existing_user

    dto = CreateUserDTO(
        username='newuser', email='existing@example.com', password_hash='secret'
    )

    with pytest.raises(UserAlreadyExistsException):
        await create_user(
            user_repo=mock_user_repo,
            password_hasher=mock_password_hasher,
            data=dto,
        )


@pytest.mark.asyncio
async def test_create_user_username_already_exists(
    mock_user_repo, mock_password_hasher
):
    existing_user = UserDTO(
        id=1,
        username='existinguser',
        email='other@example.com',
        password_hash='hashed_pw',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_user_repo.get_user.return_value = existing_user

    dto = CreateUserDTO(
        username='existinguser', email='new@example.com', password_hash='secret'
    )

    with pytest.raises(UserAlreadyExistsException):
        await create_user(
            user_repo=mock_user_repo,
            password_hasher=mock_password_hasher,
            data=dto,
        )


@pytest.mark.asyncio
async def test_get_user_by_id_success(mock_user_repo):
    user_dto = UserDTO(
        id=1,
        username='testuser',
        email='test@example.com',
        password_hash='hashed_pw',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_user_repo.get_user_by_id.return_value = user_dto

    result = await get_user_by_id(user_repo=mock_user_repo, id=1)

    assert result == user_dto


@pytest.mark.asyncio
async def test_get_user_by_id_not_found(mock_user_repo):
    mock_user_repo.get_user_by_id.return_value = None

    with pytest.raises(UserNotFoundException):
        await get_user_by_id(user_repo=mock_user_repo, id=999)


@pytest.mark.asyncio
async def test_update_user_success(mock_user_repo):
    updated_user = UserDTO(
        id=1,
        username='updateduser',
        email='updated@example.com',
        password_hash='hashed_pw',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_user_repo.get_user.return_value = None
    mock_user_repo.update_user.return_value = updated_user

    dto = UpdateUserDTO(username='updateduser', email='updated@example.com')
    result = await update_user(user_repo=mock_user_repo, id=1, data=dto)

    assert result == updated_user


@pytest.mark.asyncio
async def test_update_user_email_conflict(mock_user_repo):
    existing_user = UserDTO(
        id=2,
        username='otheruser',
        email='existing@example.com',
        password_hash='hashed_pw',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_user_repo.get_user.return_value = existing_user

    dto = UpdateUserDTO(username='newuser', email='existing@example.com')

    with pytest.raises(UserAlreadyExistsException):
        await update_user(user_repo=mock_user_repo, id=1, data=dto)


@pytest.mark.asyncio
async def test_update_user_username_conflict(mock_user_repo):
    existing_user = UserDTO(
        id=2,
        username='existinguser',
        email='other@example.com',
        password_hash='hashed_pw',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_user_repo.get_user.return_value = existing_user

    dto = UpdateUserDTO(username='existinguser', email='newemail@example.com')

    with pytest.raises(UserAlreadyExistsException):
        await update_user(user_repo=mock_user_repo, id=1, data=dto)


@pytest.mark.asyncio
async def test_change_password_success(mock_user_repo, mock_password_hasher):
    user_dto = UserDTO(
        id=1,
        username='testuser',
        email='test@example.com',
        password_hash='old_hashed_pw',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    updated_user = UserDTO(
        id=1,
        username='testuser',
        email='test@example.com',
        password_hash='new_hashed_pw',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_user_repo.get_user_by_id.return_value = user_dto
    mock_password_hasher.verify.return_value = True
    mock_password_hasher.hash.return_value = 'new_hashed_pw'
    mock_user_repo.change_user_password.return_value = updated_user

    dto = UpdateUserPasswordDTO(
        old_password='old_password', new_password='new_password'
    )
    result = await change_password(
        user_repo=mock_user_repo,
        password_hasher=mock_password_hasher,
        id=1,
        data=dto,
    )

    assert result == updated_user


@pytest.mark.asyncio
async def test_change_password_user_not_found(
    mock_user_repo, mock_password_hasher
):
    mock_user_repo.get_user_by_id.return_value = None

    dto = UpdateUserPasswordDTO(
        old_password='old_password', new_password='new_password'
    )

    with pytest.raises(UserNotFoundException):
        await change_password(
            user_repo=mock_user_repo,
            password_hasher=mock_password_hasher,
            id=999,
            data=dto,
        )


@pytest.mark.asyncio
async def test_change_password_incorrect_old_password(
    mock_user_repo, mock_password_hasher
):
    user_dto = UserDTO(
        id=1,
        username='testuser',
        email='test@example.com',
        password_hash='old_hashed_pw',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_user_repo.get_user_by_id.return_value = user_dto
    mock_password_hasher.verify.return_value = False

    dto = UpdateUserPasswordDTO(
        old_password='wrong_password', new_password='new_password'
    )

    with pytest.raises(IncorrectPasswordException):
        await change_password(
            user_repo=mock_user_repo,
            password_hasher=mock_password_hasher,
            id=1,
            data=dto,
        )


@pytest.mark.asyncio
async def test_delete_user_success(mock_user_repo):
    user_dto = UserDTO(
        id=1,
        username='testuser',
        email='test@example.com',
        password_hash='hashed_pw',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_user_repo.get_user_by_id.return_value = user_dto

    await delete_user(user_repo=mock_user_repo, id=1)

    mock_user_repo.get_user_by_id.assert_called_once_with(1)
    mock_user_repo.delete_user.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_delete_user_not_found(mock_user_repo):
    mock_user_repo.get_user_by_id.return_value = None

    with pytest.raises(UserNotFoundException):
        await delete_user(user_repo=mock_user_repo, id=999)

    mock_user_repo.delete_user.assert_not_called()
