class IdentityException(Exception):
    """Base exception for the Identity module."""


class UserNotFoundException(IdentityException):
    def __init__(self, id: int) -> None:
        self.id = id
        super().__init__(f'User with id {id} not found')
