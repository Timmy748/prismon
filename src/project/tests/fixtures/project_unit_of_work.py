from unittest.mock import AsyncMock, Mock

import pytest

from project import unit_of_work as unit_of_work_module
from project.repositories.asset import IAssetRepository
from project.repositories.document import IDocumentRepository
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository


@pytest.fixture
def uow_dependencies(monkeypatch):
    session = Mock()
    session.close = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session_factory = Mock(return_value=session)
    project_repository = Mock(spec=IProjectRepository)
    member_repository = Mock(spec=IMemberRepository)
    document_repository = Mock(spec=IDocumentRepository)
    asset_repository = Mock(spec=IAssetRepository)
    constructors = (
        ('ProjectRepository', project_repository),
        ('MemberRepository', member_repository),
        ('DocumentRepository', document_repository),
        ('AssetRepository', asset_repository),
    )
    monkeypatch.setattr(
        unit_of_work_module,
        'get_session_factory',
        Mock(return_value=session_factory),
    )
    for name, repository in constructors:
        monkeypatch.setattr(
            unit_of_work_module,
            name,
            Mock(return_value=repository),
        )
    return (
        session,
        session_factory,
        project_repository,
        member_repository,
        document_repository,
        asset_repository,
    )
