from http import HTTPStatus

import pytest

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
from agents.handlers.errors import handle_agents_error


@pytest.mark.parametrize(
    ('error', 'expected_status'),
    [
        (ChatNotFoundException(1), HTTPStatus.NOT_FOUND),
        (ChatOwnerException(1), HTTPStatus.FORBIDDEN),
        (MessageNotFoundException(1), HTTPStatus.NOT_FOUND),
        (MultipleSubmitError(), HTTPStatus.CONFLICT),
        (UserNotFoundException(1), HTTPStatus.NOT_FOUND),
        (UserAuthenticationException(), HTTPStatus.UNAUTHORIZED),
        (
            InsufficientProjectPermissionException('chat:read'),
            HTTPStatus.FORBIDDEN,
        ),
        (InvalidChatTitleException(), HTTPStatus.BAD_REQUEST),
        (EmptyMessageException(), HTTPStatus.BAD_REQUEST),
        (IdentityServiceException(), HTTPStatus.BAD_GATEWAY),
    ],
)
def test_handle_agents_error_maps_domain_error_status(error, expected_status):
    domain_error = error

    response = handle_agents_error(domain_error)

    assert response.status_code == expected_status


def test_handle_agents_error_uses_internal_server_error_for_unmapped_type():
    error = AgentsException('unexpected')

    response = handle_agents_error(error)

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
