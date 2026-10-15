from http import HTTPStatus

from fastapi.responses import JSONResponse

from agents.exceptions import (
    AgentsException,
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

DOMAIN_ERROR_STATUS: dict[type[AgentsException], HTTPStatus] = {
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
    return JSONResponse(
        status_code=status_code,
        content={'detail': str(error)},
    )
