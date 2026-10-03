from http import HTTPStatus

from fastapi.responses import JSONResponse

from project.exceptions import (
    AssetNotFoundException,
    DocumentNotFoundException,
    InsufficientProjectPermissionException,
    InvalidInvitationStateException,
    InvalidMemberRoleException,
    MemberAlreadyExistsException,
    MemberNotFoundException,
    ProjectException,
    ProjectNotFoundException,
    ProjectUserAuthenticationException,
    ProjectUserNotFoundException,
    ProjectUserServiceException,
)

DOMAIN_ERROR_STATUS: dict[type[ProjectException], HTTPStatus] = {
    ProjectNotFoundException: HTTPStatus.NOT_FOUND,
    MemberNotFoundException: HTTPStatus.NOT_FOUND,
    DocumentNotFoundException: HTTPStatus.NOT_FOUND,
    AssetNotFoundException: HTTPStatus.NOT_FOUND,
    ProjectUserNotFoundException: HTTPStatus.NOT_FOUND,
    MemberAlreadyExistsException: HTTPStatus.CONFLICT,
    InvalidInvitationStateException: HTTPStatus.CONFLICT,
    InsufficientProjectPermissionException: HTTPStatus.FORBIDDEN,
    ProjectUserAuthenticationException: HTTPStatus.UNAUTHORIZED,
    ProjectUserServiceException: HTTPStatus.BAD_GATEWAY,
    InvalidMemberRoleException: HTTPStatus.BAD_REQUEST,
}


def handle_project_error(error: ProjectException) -> JSONResponse:
    status = DOMAIN_ERROR_STATUS.get(type(error), HTTPStatus.BAD_REQUEST)
    return JSONResponse(status_code=status, content={'detail': str(error)})
