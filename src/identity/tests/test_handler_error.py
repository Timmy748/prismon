from http import HTTPStatus

import pytest

from identity.exceptions import (
    IdentityException,
    IncorrectPasswordException,
    InvalidCredentialsException,
    InvalidTokenException,
    TokenExpiredException,
    UserAlreadyExistsException,
    UserNotFoundException,
)
from identity.handlers.errors import handle_identity_error


@pytest.mark.parametrize(
    ('exception', 'expected_status'),
    [
        (UserNotFoundException(identifier=1), HTTPStatus.NOT_FOUND),
        (UserAlreadyExistsException(field='email'), HTTPStatus.CONFLICT),
        (InvalidCredentialsException(), HTTPStatus.UNAUTHORIZED),
        (InvalidTokenException(), HTTPStatus.UNAUTHORIZED),
        (TokenExpiredException(), HTTPStatus.UNAUTHORIZED),
        (IncorrectPasswordException(), HTTPStatus.BAD_REQUEST),
        (IdentityException(), HTTPStatus.INTERNAL_SERVER_ERROR),
    ],
)
def test_handle_identity_error_maps_correct_status_and_body(
    exception: IdentityException,
    expected_status: HTTPStatus,
):
    response = handle_identity_error(exception)

    assert response.status_code == expected_status
    assert response.body == f'{{"detail":"{str(exception)}"}}'.encode()
