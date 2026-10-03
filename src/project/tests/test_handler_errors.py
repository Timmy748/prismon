from http import HTTPStatus

import pytest

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
from project.handlers.errors import handle_project_error


@pytest.mark.parametrize(
    ('error', 'status'),
    [
        (ProjectNotFoundException(1), HTTPStatus.NOT_FOUND),
        (MemberNotFoundException(1), HTTPStatus.NOT_FOUND),
        (DocumentNotFoundException(1), HTTPStatus.NOT_FOUND),
        (AssetNotFoundException(1), HTTPStatus.NOT_FOUND),
        (ProjectUserNotFoundException(1), HTTPStatus.NOT_FOUND),
        (MemberAlreadyExistsException(1, 2), HTTPStatus.CONFLICT),
        (InvalidInvitationStateException(1, 2), HTTPStatus.CONFLICT),
        (
            InsufficientProjectPermissionException('member:invite'),
            HTTPStatus.FORBIDDEN,
        ),
        (
            ProjectUserAuthenticationException(),
            HTTPStatus.UNAUTHORIZED,
        ),
        (ProjectUserServiceException(), HTTPStatus.BAD_GATEWAY),
        (InvalidMemberRoleException('nobody'), HTTPStatus.BAD_REQUEST),
        (ProjectException('unmapped'), HTTPStatus.BAD_REQUEST),
    ],
)
def test_project_error_handler_uses_exact_type_status_map(error, status):
    response = handle_project_error(error)
    assert response.status_code == status
