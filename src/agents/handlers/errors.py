from http import HTTPStatus

from fastapi.responses import JSONResponse

from agents.exceptions import (
    AgentsException,
    ApiKeyNotFoundException,
    ChatNotFoundException,
    ChatOwnerException,
    EmptyMessageException,
    IdentityServiceException,
    InsufficientProjectPermissionException,
    InvalidChatTitleException,
    MessageNotFoundException,
    MultipleSubmitError,
    UserAuthenticationException,
    UserNotFoundException,
)
from core.logs import get_logger

logger = get_logger(__name__)

DOMAIN_ERROR_STATUS: dict[type[AgentsException], HTTPStatus] = {
    ApiKeyNotFoundException: HTTPStatus.NOT_FOUND,
    ChatNotFoundException: HTTPStatus.NOT_FOUND,
    ChatOwnerException: HTTPStatus.FORBIDDEN,
    MessageNotFoundException: HTTPStatus.NOT_FOUND,
    MultipleSubmitError: HTTPStatus.CONFLICT,
    UserNotFoundException: HTTPStatus.NOT_FOUND,
    UserAuthenticationException: HTTPStatus.UNAUTHORIZED,
    InsufficientProjectPermissionException: HTTPStatus.FORBIDDEN,
    InvalidChatTitleException: HTTPStatus.BAD_REQUEST,
    EmptyMessageException: HTTPStatus.BAD_REQUEST,
    IdentityServiceException: HTTPStatus.BAD_GATEWAY,
}


def handle_agents_error(error: AgentsException) -> JSONResponse:
    status_code = DOMAIN_ERROR_STATUS.get(
        type(error), HTTPStatus.INTERNAL_SERVER_ERROR
    )
    logger.info(
        'Handled agents domain error: error_type=%s status_code=%d',
        type(error).__name__,
        status_code,
    )
    return JSONResponse(
        status_code=status_code,
        content={'detail': str(error)},
    )
