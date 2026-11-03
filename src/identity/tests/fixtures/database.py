import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from identity.entities import token, user  # noqa: F401
from identity.entities.registry import mapper_registry


@pytest.fixture(scope='session')
def identity_postgres_container():
    with PostgresContainer('postgres:16-alpine') as postgres:
        yield postgres


@pytest_asyncio.fixture
async def session(identity_postgres_container):
    database_url = (
        identity_postgres_container.get_connection_url()
        .replace('postgresql+psycopg2://', 'postgresql+psycopg://', 1)
        .replace('postgresql://', 'postgresql+psycopg://', 1)
    )
    engine = create_async_engine(database_url)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(mapper_registry.metadata.create_all)

        async_session = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with async_session() as session:
            yield session
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(mapper_registry.metadata.drop_all)
        await engine.dispose()
