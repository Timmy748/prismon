from enum import Enum


class ChatAction(str, Enum):
    CREATE = 'chat:create'
    READ = 'chat:read'
    DELETE = 'chat:delete'
    UPDATE = 'chat:update'
    SEND_MESSAGE = 'chat:send_message'
