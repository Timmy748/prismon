import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from project.entities import asset, document, member, project  # noqa: F401
from project.entities.registry import mapper_registry
from project.repositories.asset import AssetRepository
from project.repositories.document import DocumentRepository
from project.repositories.member import MemberRepository
from project.repositories.project import ProjectRepository


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as connection:
        await connection.run_sync(mapper_registry.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as db_session:
        yield db_session

    async with engine.begin() as connection:
        await connection.run_sync(mapper_registry.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def project_repo(session: AsyncSession) -> ProjectRepository:
    return ProjectRepository(session)


@pytest_asyncio.fixture
async def member_repo(session: AsyncSession) -> MemberRepository:
    return MemberRepository(session)


@pytest_asyncio.fixture
async def document_repo(session: AsyncSession) -> DocumentRepository:
    return DocumentRepository(session)


@pytest_asyncio.fixture
async def asset_repo(session: AsyncSession) -> AssetRepository:
    return AssetRepository(session)


@pytest_asyncio.fixture
async def sample_project(project_repo: ProjectRepository):
    return await project_repo.create_project(name='Brand project', owner_id=1)
