from unittest.mock import AsyncMock, Mock

import pytest

from project.repositories.asset import IAssetRepository
from project.repositories.document import IDocumentRepository
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository
from project.storage import IStorage


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
