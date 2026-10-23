from unittest.mock import AsyncMock

import pytest

from agents.clients.identity import IIdentityClient
from agents.clients.project import IProjectClient
from agents.repositories.chat import IChatRepository
from agents.repositories.message import IMessageRepository
from agents.repositories.workflow import IWorkflowRepository


class MockAgentsUnitOfWork:
    def __init__(
        self, chat_repository, message_repository, workflow_repository
    ):
        self.chat_repository = chat_repository
        self.message_repository = message_repository
        self.workflow_repository = workflow_repository
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        if exc_type is not None:
            await self.rollback()

    def __getattr__(self, name):
        return getattr(self.chat_repository, name)


@pytest.fixture
def chat_repository(message_repository, workflow_repository):
    return MockAgentsUnitOfWork(
        AsyncMock(spec=IChatRepository),
        message_repository,
        workflow_repository,
    )


@pytest.fixture
def message_repository():
    return AsyncMock(spec=IMessageRepository)


@pytest.fixture
def workflow_repository():
    return AsyncMock(spec=IWorkflowRepository)


@pytest.fixture
def workflow_uow(workflow_repository):
    return MockAgentsUnitOfWork(None, None, workflow_repository)


@pytest.fixture
def project_client():
    return AsyncMock(spec=IProjectClient)


@pytest.fixture
def identity_client():
    return AsyncMock(spec=IIdentityClient)
