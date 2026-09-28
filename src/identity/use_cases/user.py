from identity.dtos.user import (
    CreateUserDTO,
    UpdateUserDTO,
    UpdateUserPasswordDTO,
    UserDTO,
)
from identity.exceptions import (
    IncorrectPasswordException,
    InvalidTokenException,
    UserAlreadyExistsException,
    UserNotFoundException,
)
from identity.repositories.user import IUserRepository
from identity.security.jwt import ITokenProvider
from identity.security.password_hasher import PasswordHasher


async def create_user(
    user_repo: IUserRepository,
    password_hasher: PasswordHasher,
    data: CreateUserDTO,
) -> UserDTO:
    existing_user = await user_repo.get_user(
        email=data.email, username=data.username
    )
    if existing_user:
        if existing_user.email == data.email:
            raise UserAlreadyExistsException('email')
        raise UserAlreadyExistsException('username')

    hashed_password = password_hasher.hash(data.password_hash)
    return await user_repo.create_user(
        username=data.username,
        email=data.email,
        password_hash=hashed_password,
    )


async def get_user_by_id(
    user_repo: IUserRepository,
    id: int,
) -> UserDTO:
    user = await user_repo.get_user_by_id(id)
    if not user:
        raise UserNotFoundException(id)
    return user


async def get_current_user(
    user_repo: IUserRepository,
    token_provider: ITokenProvider,
    access_token: str,
) -> UserDTO:
    try:
        claims = token_provider.decode_access_token(access_token)
        user_id = int(claims['sub'])
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidTokenException() from exc

    user = await user_repo.get_user_by_id(user_id)
    if user is None:
        raise InvalidTokenException()
    return user


async def update_user(
    user_repo: IUserRepository,
    id: int,
    data: UpdateUserDTO,
) -> UserDTO:
    existing_user = await user_repo.get_user(
        email=data.email, username=data.username
    )
    if existing_user:
        if existing_user.email == data.email:
            raise UserAlreadyExistsException('email')
        raise UserAlreadyExistsException('username')

    return await user_repo.update_user(
        id=id,
        username=data.username,
        email=data.email,
    )


async def change_password(
    user_repo: IUserRepository,
    password_hasher: PasswordHasher,
    id: int,
    data: UpdateUserPasswordDTO,
) -> UserDTO:
    user = await user_repo.get_user_by_id(id)
    if not user:
        raise UserNotFoundException(id)

    if not password_hasher.verify(data.old_password, user.password_hash):
        raise IncorrectPasswordException()

    new_hash = password_hasher.hash(data.new_password)
    return await user_repo.change_user_password(id=id, password_hash=new_hash)


async def delete_user(
    user_repo: IUserRepository,
    id: int,
) -> None:
    user = await user_repo.get_user_by_id(id)
    if not user:
        raise UserNotFoundException(id)
    await user_repo.delete_user(id)
