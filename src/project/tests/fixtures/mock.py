from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from project.repositories.asset import IAssetRepository
from project.repositories.document import IDocumentRepository
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository
from project.storage import IStorage
from project.unit_of_work import IProjectUnitOfWork


def make_unit_of_work(
    project_repo=None,
    member_repo=None,
    document_repo=None,
    asset_repo=None,
):
    unit_of_work = MagicMock(spec=IProjectUnitOfWork)
    unit_of_work.project_repository = project_repo or AsyncMock(
        spec=IProjectRepository
    )
    unit_of_work.member_repository = member_repo or AsyncMock(
        spec=IMemberRepository
    )
    unit_of_work.document_repository = document_repo or AsyncMock(
        spec=IDocumentRepository
    )
    unit_of_work.asset_repository = asset_repo or AsyncMock(
        spec=IAssetRepository
    )
    unit_of_work.commit = AsyncMock()
    unit_of_work.rollback = AsyncMock()
    unit_of_work.__aenter__ = AsyncMock(return_value=unit_of_work)
    unit_of_work.__aexit__ = AsyncMock(return_value=False)
    return unit_of_work


@pytest.fixture
def mock_project_repo():
    return AsyncMock(spec=IProjectRepository)


@pytest.fixture
def mock_member_repo():
    return AsyncMock(spec=IMemberRepository)


@pytest.fixture
def mock_document_repo():
    return AsyncMock(spec=IDocumentRepository)


@pytest.fixture
def mock_asset_repo():
    return AsyncMock(spec=IAssetRepository)


@pytest.fixture
def mock_storage():
    return Mock(spec=IStorage)


@pytest.fixture
def unit_of_work(project_repo, member_repo, document_repo, asset_repo):
    return make_unit_of_work(
        project_repo, member_repo, document_repo, asset_repo
    )
