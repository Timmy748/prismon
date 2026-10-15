from unittest.mock import AsyncMock

import pytest

from agents.clients.identity import IIdentityClient
from agents.clients.project import IProjectClient
from agents.repositories.chat import IChatRepository
from agents.repositories.message import IMessageRepository
from agents.repositories.workflow import IWorkflowRepository


@pytest.fixture
def chat_repository():
    return AsyncMock(spec=IChatRepository)


@pytest.fixture
def message_repository():
    return AsyncMock(spec=IMessageRepository)


@pytest.fixture
def workflow_repository():
    return AsyncMock(spec=IWorkflowRepository)


@pytest.fixture
def project_client():
    return AsyncMock(spec=IProjectClient)


@pytest.fixture
def identity_client():
    return AsyncMock(spec=IIdentityClient)
