from project.permissions.authorization import ResourceActions


class ProjectAction(ResourceActions):
    UPDATE = 'project:update'
    DELETE = 'project:delete'
    MEMBER_LIST = 'member:list'
    MEMBER_INVITE = 'member:invite'
    MEMBER_CHANGE_ROLE = 'member:change_role'
    MEMBER_REMOVE = 'member:remove'


class ChatAction(ResourceActions):
    CREATE = 'chat:create'
    READ = 'chat:read'
    DELETE = 'chat:delete'
    UPDATE = 'chat:update'
    SEND_MESSAGE = 'chat:send_message'


class MemberAction(ResourceActions):
    ACCEPT_INVITATION = 'member:accept_invitation'
    DECLINE_INVITATION = 'member:decline_invitation'


class DocumentAction(ResourceActions):
    CREATE = 'document:create'
    READ = 'document:read'
    UPDATE = 'document:update'
    DELETE = 'document:delete'
    APPROVE = 'document:approve'
    TAG_ASSIGN = 'document:tag:assign'


class AssetAction(ResourceActions):
    CREATE = 'asset:create'
    READ = 'asset:read'
    UPDATE = 'asset:update'
    APPROVE = 'asset:approve'
    TAG_ASSIGN = 'asset:tag:assign'


class TagAction(ResourceActions):
    READ = 'tag:read'
    CREATE = 'tag:create'
    UPDATE = 'tag:update'
    DELETE = 'tag:delete'


class ApiKeyAction(ResourceActions):
    MEMBER_CREATE = 'api_key:member:create'
    PROJECT_CREATE = 'api_key:project:create'
    MEMBER_LIST = 'api_key:member:list'
    PROJECT_LIST = 'api_key:project:list'
    READ = 'api_key:read'
    DELETE = 'api_key:delete'
