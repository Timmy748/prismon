import asyncio

from agents.clients.project import create_project_client
from agents.embedding_engine.factory import create_embedding_engine
from agents.unit_of_work import create_agents_unit_of_work
from agents.use_cases.embeddings import embed_asset, embed_document
from infra.celery_app import celery_app


@celery_app.task(
    name='agents.embeddings.document',
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 8},
)
def embed_document_task(document_id: int) -> bool:
    return asyncio.run(_embed_document(document_id))


async def _embed_document(document_id: int) -> bool:
    async with create_agents_unit_of_work() as agents_uow:
        return await embed_document(
            create_project_client(),
            agents_uow,
            create_embedding_engine(),
            document_id,
        )


@celery_app.task(
    name='agents.embeddings.asset',
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 8},
)
def embed_asset_task(asset_id: int) -> bool:
    return asyncio.run(_embed_asset(asset_id))


async def _embed_asset(asset_id: int) -> bool:
    async with create_agents_unit_of_work() as agents_uow:
        return await embed_asset(
            create_project_client(),
            agents_uow,
            create_embedding_engine(),
            asset_id,
        )
