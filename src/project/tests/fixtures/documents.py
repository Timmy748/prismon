from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from project.clients.client_user import IUserClient
from project.dtos.document import DocumentDTO
from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.project import ProjectDTO
from project.dtos.user import UserDTO
from project.entities.document import DocumentStatus
from project.entities.member import MemberRole, MemberStatus
from project.repositories.document import IDocumentRepository
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository
from project.routes.documents import create_documents_router
from project.storage import IStorage


@pytest.fixture
def document_api():
    project_repo = AsyncMock(spec=IProjectRepository)
    member_repo = AsyncMock(spec=IMemberRepository)
    document_repo = AsyncMock(spec=IDocumentRepository)
    user_client = AsyncMock(spec=IUserClient)
    storage = MagicMock(spec=IStorage)
    now = datetime.now(timezone.utc)
    user = UserDTO(7, 'ana', 'ana@example.com')
    project = ProjectDTO(2, 'Project', 7, now, now)
    member = MemberDTO(1, 2, MemberRole.OWNER, MemberStatus.ACTIVE, 7, now, now)
    document = DocumentDTO(
        4,
        2,
        'projects/2/documents/file',
        'Brief',
        None,
        DocumentStatus.PUBLISHED,
        now,
        now,
    )
    user_client.get_current_user.return_value = user
    project_repo.get_project.return_value = project
    member_repo.get_members.return_value = CursorPage(
        [member], PaginationDTO(limit=100)
    )
    document_repo.get_documents.return_value = CursorPage(
        [document], PaginationDTO(limit=10)
    )
    document_repo.get_document.return_value = document
    document_repo.create_document.return_value = document
    document_repo.update_document.return_value = document

    async def project_factory():
        return project_repo

    async def member_factory():
        return member_repo

    async def document_factory():
        return document_repo

    app = FastAPI()
    app.include_router(
        create_documents_router(
            project_factory,
            member_factory,
            document_factory,
            lambda: storage,
            lambda: user_client,
        )
    )
    return (
        app,
        project_repo,
        member_repo,
        document_repo,
        user_client,
        storage,
        document,
    )


@pytest_asyncio.fixture
async def document_client(document_api):
    async with AsyncClient(
        transport=ASGITransport(app=document_api[0]), base_url='http://test'
    ) as client:
        yield client
