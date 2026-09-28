from http import HTTPStatus

from fastapi.responses import JSONResponse

from identity.exceptions import (
    IdentityException,
    IncorrectPasswordException,
    InvalidCredentialsException,
    InvalidTokenException,
    TokenExpiredException,
    UserAlreadyExistsException,
    UserNotFoundException,
)

DOMAIN_ERROR_STATUS: dict[type[IdentityException], HTTPStatus] = {
    UserNotFoundException: HTTPStatus.NOT_FOUND,
    UserAlreadyExistsException: HTTPStatus.CONFLICT,
    InvalidCredentialsException: HTTPStatus.UNAUTHORIZED,
    InvalidTokenException: HTTPStatus.UNAUTHORIZED,
    TokenExpiredException: HTTPStatus.UNAUTHORIZED,
    IncorrectPasswordException: HTTPStatus.BAD_REQUEST,
}


def handle_identity_error(error: IdentityException) -> JSONResponse:
    status_code = DOMAIN_ERROR_STATUS.get(
        type(error), HTTPStatus.INTERNAL_SERVER_ERROR
    )
    return JSONResponse(
        status_code=status_code,
        content={'detail': str(error)},
    )
