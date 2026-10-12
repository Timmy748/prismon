import pytest

from project.public_api import ProjectPublicAPI


@pytest.fixture
def public_api(
    mock_project_repo,
    mock_member_repo,
    mock_document_repo,
    mock_asset_repo,
    mock_storage,
):
    async def project_repo_factory():
        return mock_project_repo

    async def member_repo_factory():
        return mock_member_repo

    async def document_repo_factory():
        return mock_document_repo

    async def asset_repo_factory():
        return mock_asset_repo

    return ProjectPublicAPI(
        project_repository_factory=project_repo_factory,
        member_repository_factory=member_repo_factory,
        document_repository_factory=document_repo_factory,
        asset_repository_factory=asset_repo_factory,
        storage_factory=lambda: mock_storage,
    )
