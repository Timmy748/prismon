from unittest.mock import AsyncMock, Mock

import pytest

from project import unit_of_work as unit_of_work_module
from project.repositories.asset import IAssetRepository
from project.repositories.document import IDocumentRepository
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository
from project.unit_of_work import (
    UnitOfWork,
    create_project_unit_of_work,
)


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


@pytest.mark.asyncio
async def test_unit_of_work_binds_all_repositories_to_one_session(
    uow_dependencies,
):
    (
        session,
        session_factory,
        project_repository,
        member_repository,
        document_repository,
        asset_repository,
    ) = uow_dependencies
    unit_of_work = UnitOfWork()

    async with unit_of_work as entered:
        assert entered is unit_of_work
        assert unit_of_work.project_repository is project_repository
        assert unit_of_work.member_repository is member_repository
        assert unit_of_work.document_repository is document_repository
        assert unit_of_work.asset_repository is asset_repository
        for name, repository in (
            ('ProjectRepository', project_repository),
            ('MemberRepository', member_repository),
            ('DocumentRepository', document_repository),
            ('AssetRepository', asset_repository),
        ):
            getattr(unit_of_work_module, name).assert_called_once_with(session)

    session_factory.assert_called_once_with()
    session.close.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_unit_of_work_forwards_explicit_commit_and_rollback(
    uow_dependencies,
):
    session = uow_dependencies[0]
    unit_of_work = UnitOfWork()

    async with unit_of_work:
        await unit_of_work.commit()
        await unit_of_work.rollback()

    session.commit.assert_awaited_once()
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_unit_of_work_rolls_back_on_exception_and_closes(
    uow_dependencies,
):
    session = uow_dependencies[0]
    unit_of_work = UnitOfWork()

    with pytest.raises(ValueError, match='failed'):
        async with unit_of_work:
            raise ValueError('failed')

    session.rollback.assert_awaited_once()
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_unit_of_work_rejects_reentry(uow_dependencies):
    session_factory = uow_dependencies[1]
    unit_of_work = UnitOfWork()

    async with unit_of_work:
        with pytest.raises(RuntimeError, match='already active'):
            await unit_of_work.__aenter__()

    session_factory.assert_called_once_with()


@pytest.mark.parametrize(
    'repository_property',
    [
        'project_repository',
        'member_repository',
        'document_repository',
        'asset_repository',
    ],
)
def test_unit_of_work_repository_is_unavailable_outside_context(
    repository_property,
):
    unit_of_work = UnitOfWork()

    with pytest.raises(RuntimeError, match='context is not active'):
        getattr(unit_of_work, repository_property)


@pytest.mark.asyncio
async def test_unit_of_work_commit_and_rollback_require_active_context():
    unit_of_work = UnitOfWork()

    with pytest.raises(RuntimeError, match='context is not active'):
        await unit_of_work.commit()
    with pytest.raises(RuntimeError, match='context is not active'):
        await unit_of_work.rollback()


@pytest.mark.asyncio
async def test_inactive_unit_of_work_exit_is_safe():
    await UnitOfWork().__aexit__(None, None, None)


def test_factory_returns_project_unit_of_work():
    assert isinstance(create_project_unit_of_work(), UnitOfWork)
