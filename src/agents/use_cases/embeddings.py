from agents.clients.project import IProjectClient
from agents.embedding_engine.base import IEmbeddingEngine
from agents.unit_of_work import IAgentsUnitOfWork
from infra.logs import get_logger

logger = get_logger(__name__)
MAX_METADATA_REFRESH_ATTEMPTS = 3


async def embed_document(
    project_client: IProjectClient,
    agents_uow: IAgentsUnitOfWork,
    embedding_engine: IEmbeddingEngine,
    document_id: int,
) -> bool:
    for _ in range(MAX_METADATA_REFRESH_ATTEMPTS):
        document = await project_client.get_document_embedding_source(
            document_id
        )
        if document is None:
            logger.info(
                'Skipping embedding for missing document_id=%s', document_id
            )
            return False

        content = f'title: {document.name} | text: {document.description or ""}'
        embedding = await embedding_engine.embedding_document(
            document.name, document.description or ''
        )

        latest_document = await project_client.get_document_embedding_source(
            document_id
        )
        if latest_document is None:
            logger.info(
                'Skipping embedding for deleted document_id=%s', document_id
            )
            return False
        latest_content = (
            f'title: {latest_document.name} | '
            f'text: {latest_document.description or ""}'
        )
        if latest_content != content:
            logger.info(
                'Document changed during embedding; refreshing document_id=%s',
                document_id,
            )
            continue

        await agents_uow.document_embedding_repository.upsert_embedding(
            document_id, content, embedding
        )
        await agents_uow.commit()
        logger.info('Document embedding saved: document_id=%s', document_id)
        return True

    raise RuntimeError(
        f'Document metadata changed repeatedly during embedding: {document_id}'
    )


async def embed_asset(
    project_client: IProjectClient,
    agents_uow: IAgentsUnitOfWork,
    embedding_engine: IEmbeddingEngine,
    asset_id: int,
) -> bool:
    for _ in range(MAX_METADATA_REFRESH_ATTEMPTS):
        asset = await project_client.get_asset_embedding_source(asset_id)
        if asset is None:
            logger.info('Skipping embedding for missing asset_id=%s', asset_id)
            return False

        content = f'title: {asset.name} | text: {asset.description or ""}'
        embedding = await embedding_engine.embedding_asset(
            asset.name, asset.description or ''
        )

        latest_asset = await project_client.get_asset_embedding_source(asset_id)
        if latest_asset is None:
            logger.info('Skipping embedding for deleted asset_id=%s', asset_id)
            return False
        latest_content = (
            f'title: {latest_asset.name} | '
            f'text: {latest_asset.description or ""}'
        )
        if latest_content != content:
            logger.info(
                'Asset changed during embedding; refreshing asset_id=%s',
                asset_id,
            )
            continue

        await agents_uow.asset_embedding_repository.upsert_embedding(
            asset_id, content, embedding
        )
        await agents_uow.commit()
        logger.info('Asset embedding saved: asset_id=%s', asset_id)
        return True

    raise RuntimeError(
        f'Asset metadata changed repeatedly during embedding: {asset_id}'
    )
