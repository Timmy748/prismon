from unittest.mock import AsyncMock, MagicMock

import pytest

from identity.unit_of_work import (
    IdentityUnitOfWork,
    create_identity_unit_of_work,
)


@pytest.fixture
def session():
    return AsyncMock()


@pytest.fixture
def unit_of_work(session):
    return IdentityUnitOfWork(session_factory=MagicMock(return_value=session))


@pytest.mark.asyncio
async def test_context_initializes_repositories_and_closes_session(
    unit_of_work, session
):
    async with unit_of_work as active_uow:
        assert active_uow.user_repository is not None
        assert active_uow.token_repository is not None

    session.close.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_factory_returns_usable_unit_of_work(monkeypatch, session):
    session_factory = MagicMock(return_value=session)
    session_factory_provider = MagicMock(return_value=session_factory)
    monkeypatch.setattr(
        'identity.unit_of_work.get_session_factory', session_factory_provider
    )

    uow = create_identity_unit_of_work()

    async with uow:
        assert uow.user_repository is not None
        assert uow.token_repository is not None

    session_factory_provider.assert_called_once_with()
    session_factory.assert_called_once_with()
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_context_rolls_back_when_body_raises(unit_of_work, session):
    with pytest.raises(ValueError, match='failed'):
        async with unit_of_work:
            raise ValueError('failed')

    session.rollback.assert_awaited_once()
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_commit_delegates_to_active_session(unit_of_work, session):
    async with unit_of_work:
        await unit_of_work.commit()

    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_explicit_rollback_delegates_to_active_session(
    unit_of_work, session
):
    async with unit_of_work:
        await unit_of_work.rollback()

    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_reentering_active_context_raises(unit_of_work):
    async with unit_of_work:
        with pytest.raises(RuntimeError, match='already active'):
            await unit_of_work.__aenter__()


@pytest.mark.asyncio
async def test_repository_properties_require_active_context(unit_of_work):
    with pytest.raises(RuntimeError, match='not active'):
        _ = unit_of_work.user_repository

    with pytest.raises(RuntimeError, match='not active'):
        _ = unit_of_work.token_repository


@pytest.mark.asyncio
async def test_commit_and_rollback_require_active_context(unit_of_work):
    with pytest.raises(RuntimeError, match='not active'):
        await unit_of_work.commit()

    with pytest.raises(RuntimeError, match='not active'):
        await unit_of_work.rollback()


@pytest.mark.asyncio
async def test_repository_properties_are_inactive_after_exit(unit_of_work):
    async with unit_of_work:
        pass

    with pytest.raises(RuntimeError, match='not active'):
        _ = unit_of_work.user_repository

    with pytest.raises(RuntimeError, match='not active'):
        _ = unit_of_work.token_repository


@pytest.mark.asyncio
async def test_session_is_closed_and_context_reset_when_close_fails(
    unit_of_work, session
):
    session.close.side_effect = OSError('close failed')

    with pytest.raises(OSError, match='close failed'):
        async with unit_of_work:
            pass

    with pytest.raises(RuntimeError, match='not active'):
        _ = unit_of_work.user_repository
