import pytest

from project.public_api import ProjectPublicAPI
from project.tests.fixtures.mock import make_unit_of_work


@pytest.fixture
def public_api(
    mock_project_repo,
    mock_member_repo,
    mock_document_repo,
    mock_asset_repo,
    mock_storage,
):
    unit_of_work = make_unit_of_work(
        mock_project_repo,
        mock_member_repo,
        mock_document_repo,
        mock_asset_repo,
    )

    return ProjectPublicAPI(
        storage_factory=lambda: mock_storage,
        unit_of_work_factory=lambda: unit_of_work,
    )
