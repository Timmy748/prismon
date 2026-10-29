from http import HTTPStatus

from fastapi.responses import JSONResponse

from core.logs import get_logger
from project.exceptions import (
    ApiKeyNotFoundException,
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

logger = get_logger(__name__)

DOMAIN_ERROR_STATUS: dict[type[ProjectException], HTTPStatus] = {
    ApiKeyNotFoundException: HTTPStatus.NOT_FOUND,
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
    logger.warning(
        'Project request failed: error_type=%s status=%s',
        type(error).__name__,
        status.value,
    )
    return JSONResponse(status_code=status, content={'detail': str(error)})
