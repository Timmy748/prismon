from unittest.mock import AsyncMock, Mock, patch

import pytest

import agents.unit_of_work as unit_of_work_module
from agents.repositories.chat import ChatRepository
from agents.repositories.message import MessageRepository
from agents.repositories.workflow import WorkflowRepository
from agents.unit_of_work import AgentsUnitOfWork, create_agents_unit_of_work


@pytest.mark.asyncio
async def test_unit_of_work_builds_all_repositories_from_one_session():
    session = AsyncMock()
    session_factory = Mock(return_value=session)
    chat_repository = Mock(spec=ChatRepository)
    message_repository = Mock(spec=MessageRepository)
    workflow_repository = Mock(spec=WorkflowRepository)

    with (
        patch(
            'agents.unit_of_work.ChatRepository',
            return_value=chat_repository,
        ) as chat_factory,
        patch(
            'agents.unit_of_work.MessageRepository',
            return_value=message_repository,
        ) as message_factory,
        patch(
            'agents.unit_of_work.WorkflowRepository',
            return_value=workflow_repository,
        ) as workflow_factory,
    ):
        async with AgentsUnitOfWork(session_factory) as uow:
            assert (
                uow.chat_repository,
                uow.message_repository,
                uow.workflow_repository,
            ) == (chat_repository, message_repository, workflow_repository)

    session_factory.assert_called_once_with()
    chat_factory.assert_called_once_with(session)
    message_factory.assert_called_once_with(session)
    workflow_factory.assert_called_once_with(session)
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_unit_of_work_rejects_reentry():
    session = AsyncMock()
    uow = AgentsUnitOfWork(Mock(return_value=session))
    await uow.__aenter__()

    with pytest.raises(RuntimeError, match='already active'):
        await uow.__aenter__()

    await uow.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_unit_of_work_commit_and_rollback_forward_to_session():
    session = AsyncMock()
    async with AgentsUnitOfWork(Mock(return_value=session)) as uow:
        await uow.commit()
        await uow.rollback()

    session.commit.assert_awaited_once()
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_unit_of_work_exception_exit_rolls_back_and_closes():
    session = AsyncMock()
    uow = AgentsUnitOfWork(Mock(return_value=session))

    with pytest.raises(ValueError, match='failure'):
        async with uow:
            raise ValueError('failure')

    session.rollback.assert_awaited_once()
    session.close.assert_awaited_once()
    with pytest.raises(RuntimeError, match='only inside the context'):
        _ = uow.chat_repository


@pytest.mark.asyncio
async def test_unit_of_work_normal_exit_does_not_rollback():
    session = AsyncMock()
    uow = AgentsUnitOfWork(Mock(return_value=session))

    async with uow:
        pass

    session.rollback.assert_not_awaited()
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_unit_of_work_operations_require_active_context():
    uow = AgentsUnitOfWork(Mock())

    with pytest.raises(RuntimeError, match='only inside the context'):
        await uow.commit()
    with pytest.raises(RuntimeError, match='only inside the context'):
        await uow.rollback()
    with pytest.raises(RuntimeError, match='only inside the context'):
        _ = uow.message_repository
    with pytest.raises(RuntimeError, match='only inside the context'):
        _ = uow.workflow_repository


@pytest.mark.asyncio
async def test_unit_of_work_exit_while_inactive_is_harmless():
    uow = AgentsUnitOfWork(Mock())

    await uow.__aexit__(None, None, None)


def test_create_agents_unit_of_work_returns_implementation(monkeypatch):
    instance = object()
    constructor = Mock(return_value=instance)
    monkeypatch.setattr(unit_of_work_module, 'AgentsUnitOfWork', constructor)

    result = create_agents_unit_of_work()

    assert result is instance
    constructor.assert_called_once_with()
