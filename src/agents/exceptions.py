class AgentsException(Exception):
    """Base exception for agents domain errors."""


class ChatNotFoundException(AgentsException):
    def __init__(self, chat_id: int) -> None:
        self.chat_id = chat_id
        super().__init__(f'Chat {chat_id} not found')


class ChatOwnerException(AgentsException):
    def __init__(self, chat_id: int) -> None:
        self.chat_id = chat_id
        super().__init__(f'User is not the owner of chat {chat_id}')


class InsufficientProjectPermissionException(AgentsException):
    def __init__(self, permission: str) -> None:
        self.permission = permission
        super().__init__(f'Missing project permission: {permission}')


class InvalidChatTitleException(AgentsException):
    """Raised when a chat title is empty or exceeds the supported length."""

    def __init__(self) -> None:
        super().__init__('Chat title must contain 1 to 256 characters')


class MultipleSubmitError(AgentsException):
    """Raised when a user try send two messages in sequence."""

    def __init__(self) -> None:
        super().__init__('Cannot send message while response is pending.')


class EmptyMessageException(AgentsException):
    """Raised when a message has no text."""


class MessageNotFoundException(AgentsException):
    def __init__(self, message_id: int) -> None:
        self.message_id = message_id
        super().__init__(f'Message {message_id} not found')


class ApiKeyNotFoundException(AgentsException):
    def __init__(self, api_key_id: int) -> None:
        self.api_key_id = api_key_id
        super().__init__(f'API key {api_key_id} not found')


class IdentityServiceException(AgentsException):
    """Raised when the Identity service cannot serve a request."""


class UserNotFoundException(AgentsException):
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        super().__init__(f'User {user_id} not found')


class UserAuthenticationException(AgentsException):
    """Raised when Identity rejects a user's credentials or access token."""
