class IdentityException(Exception):
    pass


class UserNotFoundException(IdentityException):
    def __init__(self, identifier: int | str) -> None:
        self.identifier = identifier
        super().__init__(f'User with identifier {identifier} not found')


class UserAlreadyExistsException(IdentityException):
    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(f'User with this {field} already exists')


class InvalidCredentialsException(IdentityException):
    def __init__(self) -> None:
        super().__init__('Invalid email or password')


class IncorrectPasswordException(IdentityException):
    def __init__(self) -> None:
        super().__init__('Incorrect current password')


class InvalidTokenException(IdentityException):
    def __init__(self) -> None:
        super().__init__('Invalid or revoked token')


class TokenExpiredException(IdentityException):
    def __init__(self) -> None:
        super().__init__('Token has expired')
