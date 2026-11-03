# ruff: noqa: PLR0913, PLR0917
from time import monotonic

import numpy as np
from numpy.typing import NDArray

from agents.dtos.search import HybridSearchCandidate
from agents.repositories.hybrid_search import RRF_K
from agents.unit_of_work import IAgentsUnitOfWork
from infra.logs import get_logger

logger = get_logger(__name__)


async def hybrid_search_documents(
    uow: IAgentsUnitOfWork,
    project_id: int,
    query: str,
    query_embedding: NDArray[np.float32],
    limit: int = 10,
    rrf_k: int = RRF_K,
) -> list[HybridSearchCandidate]:
    """Retrieve and fuse document matches in one repository query."""
    started_at = monotonic()
    logger.info(
        'Hybrid document search started: project_id=%d query=%r limit=%d',
        project_id,
        query,
        limit,
    )
    candidates = await uow.document_embedding_repository.hybrid_search(
        project_id=project_id,
        query=query,
        query_embedding=query_embedding,
        limit=limit,
        rrf_k=rrf_k,
    )
    logger.info(
        'Hybrid document search finished: project_id=%d elapsed_ms=%.1f '
        'candidate_count=%d candidates=%s',
        project_id,
        (monotonic() - started_at) * 1000,
        len(candidates),
        [
            {
                'id': candidate.resource_id,
                'rank': candidate.rank,
                'rrf_score': round(candidate.rrf_score, 8),
                'bm25_rank': candidate.bm25_rank,
                'dense_rank': candidate.dense_rank,
            }
            for candidate in candidates
        ],
    )
    return candidates


async def hybrid_search_assets(
    uow: IAgentsUnitOfWork,
    project_id: int,
    query: str,
    query_embedding: NDArray[np.float32],
    limit: int = 10,
    rrf_k: int = RRF_K,
) -> list[HybridSearchCandidate]:
    """Retrieve and fuse asset matches in one repository query."""
    started_at = monotonic()
    logger.info(
        'Hybrid asset search started: project_id=%d query=%r limit=%d',
        project_id,
        query,
        limit,
    )
    candidates = await uow.asset_embedding_repository.hybrid_search(
        project_id=project_id,
        query=query,
        query_embedding=query_embedding,
        limit=limit,
        rrf_k=rrf_k,
    )
    logger.info(
        'Hybrid asset search finished: project_id=%d elapsed_ms=%.1f '
        'candidate_count=%d candidates=%s',
        project_id,
        (monotonic() - started_at) * 1000,
        len(candidates),
        [
            {
                'id': candidate.resource_id,
                'rank': candidate.rank,
                'rrf_score': round(candidate.rrf_score, 8),
                'bm25_rank': candidate.bm25_rank,
                'dense_rank': candidate.dense_rank,
            }
            for candidate in candidates
        ],
    )
    return candidates
