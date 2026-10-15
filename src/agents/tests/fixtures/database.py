import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from agents.entities import chat, message, workflow  # noqa: F401
from agents.entities.registry import mapper_registry


@pytest.fixture(scope='session')
def postgres_container():
    with PostgresContainer('postgres:16-alpine') as postgres:
        yield postgres


@pytest_asyncio.fixture
async def session(postgres_container):
    database_url = postgres_container.get_connection_url()
    database_url = database_url.replace(
        'postgresql+psycopg2://', 'postgresql+psycopg://', 1
    ).replace('postgresql://', 'postgresql+psycopg://', 1)
    engine = create_async_engine(database_url)

    async with engine.begin() as connection:
        await connection.run_sync(mapper_registry.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        async with session_factory() as database_session:
            yield database_session
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(mapper_registry.metadata.drop_all)
        await engine.dispose()
