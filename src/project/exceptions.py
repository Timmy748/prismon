class ProjectException(Exception):
    """Base exception for project domain errors."""


class ProjectNotFoundException(ProjectException):
    def __init__(self, project_id: int) -> None:
        self.project_id = project_id
        super().__init__(f'Project {project_id} not found')


class MemberNotFoundException(ProjectException):
    def __init__(self, member_id: int) -> None:
        self.member_id = member_id
        super().__init__(f'Member {member_id} not found')


class DocumentNotFoundException(ProjectException):
    def __init__(self, document_id: int) -> None:
        self.document_id = document_id
        super().__init__(f'Document {document_id} not found')


class AssetNotFoundException(ProjectException):
    def __init__(self, asset_id: int) -> None:
        self.asset_id = asset_id
        super().__init__(f'Asset {asset_id} not found')


class MemberAlreadyExistsException(ProjectException):
    def __init__(self, project_id: int, user_id: int) -> None:
        self.project_id = project_id
        self.user_id = user_id
        super().__init__(
            f'User {user_id} is already a member of project {project_id}'
        )


class InsufficientProjectPermissionException(ProjectException):
    def __init__(self, permission: str) -> None:
        self.permission = permission
        super().__init__(f'Missing project permission: {permission}')


class InvalidInvitationStateException(ProjectException):
    def __init__(self, project_id: int, user_id: int) -> None:
        self.project_id = project_id
        self.user_id = user_id
        super().__init__(
            f'No pending invitation for user {user_id} in project {project_id}'
        )


class InvalidResourceStateException(ProjectException):
    def __init__(self, resource_id: int, status: str) -> None:
        self.resource_id = resource_id
        self.status = status
        super().__init__(
            f'Resource {resource_id} cannot be changed from status {status}'
        )


# Kept as the document-specific name used by document review callers.
class InvalidDocumentStateException(InvalidResourceStateException):
    pass


class InvalidAssetStateException(InvalidResourceStateException):
    pass
