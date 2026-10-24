from core.logs import get_logger
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
from identity.security.jwt import ITokenProvider
from identity.security.password_hasher import PasswordHasher
from identity.unit_of_work import IIdentityUnitOfWork

logger = get_logger(__name__)


async def create_user(
    uow: IIdentityUnitOfWork,
    password_hasher: PasswordHasher,
    data: CreateUserDTO,
) -> UserDTO:
    existing_user = await uow.user_repository.get_user(
        email=data.email, username=data.username
    )
    if existing_user:
        if existing_user.email == data.email:
            logger.warning('User creation rejected: email already registered')
            raise UserAlreadyExistsException('email')
        logger.warning('User creation rejected: username already registered')
        raise UserAlreadyExistsException('username')

    hashed_password = password_hasher.hash(data.password_hash)
    user = await uow.user_repository.create_user(
        username=data.username,
        email=data.email,
        password_hash=hashed_password,
    )
    await uow.commit()
    logger.info('User created successfully')
    return user


async def get_user_by_id(
    uow: IIdentityUnitOfWork,
    id: int,
) -> UserDTO:
    user = await uow.user_repository.get_user_by_id(id)
    if not user:
        logger.warning('User lookup failed: user was not found')
        raise UserNotFoundException(id)
    logger.debug('User lookup completed successfully')
    return user


async def get_current_user(
    uow: IIdentityUnitOfWork,
    token_provider: ITokenProvider,
    access_token: str,
) -> UserDTO:
    try:
        claims = token_provider.decode_access_token(access_token)
        user_id = int(claims['sub'])
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning('Current user lookup rejected: invalid access token')
        raise InvalidTokenException() from exc

    user = await uow.user_repository.get_user_by_id(user_id)
    if user is None:
        logger.warning('Current user lookup rejected: user was not found')
        raise InvalidTokenException()
    logger.debug('Current user lookup completed successfully')
    return user


async def update_user(
    uow: IIdentityUnitOfWork,
    id: int,
    data: UpdateUserDTO,
) -> UserDTO:
    existing_user = await uow.user_repository.get_user(
        email=data.email, username=data.username
    )
    if existing_user:
        if existing_user.email == data.email:
            logger.warning('User update rejected: email already registered')
            raise UserAlreadyExistsException('email')
        logger.warning('User update rejected: username already registered')
        raise UserAlreadyExistsException('username')

    user = await uow.user_repository.update_user(
        id=id,
        username=data.username,
        email=data.email,
    )
    await uow.commit()
    logger.info('User profile updated successfully')
    return user


async def change_password(
    uow: IIdentityUnitOfWork,
    password_hasher: PasswordHasher,
    id: int,
    data: UpdateUserPasswordDTO,
) -> UserDTO:
    user = await uow.user_repository.get_user_by_id(id)
    if not user:
        logger.warning('Password change failed: user was not found')
        raise UserNotFoundException(id)

    if not password_hasher.verify(data.old_password, user.password_hash):
        logger.warning('Password change rejected: current password mismatch')
        raise IncorrectPasswordException()

    new_hash = password_hasher.hash(data.new_password)
    updated_user = await uow.user_repository.change_user_password(
        id=id, password_hash=new_hash
    )
    await uow.commit()
    logger.info('User password changed successfully')
    return updated_user


async def delete_user(
    uow: IIdentityUnitOfWork,
    id: int,
) -> None:
    user = await uow.user_repository.get_user_by_id(id)
    if not user:
        logger.warning('User deletion failed: user was not found')
        raise UserNotFoundException(id)
    await uow.user_repository.delete_user(id)
    await uow.commit()
    logger.info('User deleted successfully')
