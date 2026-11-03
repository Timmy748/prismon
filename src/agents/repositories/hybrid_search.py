"""Shared single-query BM25, vector, and RRF retrieval."""

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agents.dtos.search import HybridSearchCandidate, ResourceType

RRF_K = 60
SearchTable = Literal['document_embeddings', 'asset_embeddings']
SearchIdColumn = Literal['document_id', 'asset_id']


@dataclass(frozen=True, slots=True)
class HybridSearchTarget:
    resource_type: ResourceType
    table: SearchTable
    id_column: SearchIdColumn
    status: str


@dataclass(frozen=True, slots=True)
class HybridSearchRequest:
    project_id: int
    query: str
    query_embedding: NDArray[np.float32]
    limit: int = 10
    rrf_k: int = RRF_K


def _hybrid_search_sql(table: SearchTable, id_column: SearchIdColumn) -> str:
    """Build a stable SQL statement using only internal table identifiers."""
    return f"""
        WITH bm25_ranked AS (
            SELECT
                {id_column} AS resource_id,
                ROW_NUMBER() OVER (
                    ORDER BY pdb.score({id_column}) DESC, {id_column} ASC
                ) AS bm25_rank
            FROM {table}
            WHERE content ||| :query
              AND project_id = :project_id
              AND status = :status
            ORDER BY pdb.score({id_column}) DESC, {id_column} ASC
            LIMIT :limit
        ),
        dense_ranked AS (
            SELECT
                {id_column} AS resource_id,
                ROW_NUMBER() OVER (
                    ORDER BY
                        embedding <#> CAST(:query_embedding AS halfvec(256)),
                        {id_column} ASC
                ) AS dense_rank
            FROM {table}
            WHERE project_id = :project_id
              AND status = :status
            ORDER BY
                embedding <#> CAST(:query_embedding AS halfvec(256)),
                {id_column} ASC
            LIMIT :limit
        ),
        rank_contributions AS (
            SELECT
                resource_id,
                bm25_rank,
                NULL::BIGINT AS dense_rank,
                1.0 / (:rrf_k + bm25_rank)::DOUBLE PRECISION
                    AS rrf_contribution
            FROM bm25_ranked

            UNION ALL

            SELECT
                resource_id,
                NULL::BIGINT AS bm25_rank,
                dense_rank,
                1.0 / (:rrf_k + dense_rank)::DOUBLE PRECISION
                    AS rrf_contribution
            FROM dense_ranked
        ),
        rrf_scores AS (
            SELECT
                resource_id,
                SUM(rrf_contribution) AS rrf_score,
                MIN(bm25_rank) AS bm25_rank,
                MIN(dense_rank) AS dense_rank
            FROM rank_contributions
            GROUP BY resource_id
        )
        SELECT resource_id, rrf_score, bm25_rank, dense_rank
        FROM rrf_scores
        ORDER BY rrf_score DESC, resource_id ASC
        LIMIT :limit
    """


async def hybrid_search(
    session: AsyncSession,
    *,
    target: HybridSearchTarget,
    request: HybridSearchRequest,
) -> list[HybridSearchCandidate]:
    """Return one merged ranking from a single database round trip.

    The SQL names both branch ranks and their RRF contributions explicitly,
    making the score and ordering straightforward to audit.
    """
    if not request.query.strip() or request.limit <= 0:
        return []

    statement = text(_hybrid_search_sql(target.table, target.id_column))
    parameters = {
        'query': request.query,
        'query_embedding': str(request.query_embedding.tolist()),
        'project_id': request.project_id,
        'status': target.status,
        'limit': request.limit,
        'rrf_k': request.rrf_k,
    }
    result = await session.execute(statement, parameters)
    rows = result.mappings().all()

    return [
        HybridSearchCandidate(
            resource_type=target.resource_type,
            resource_id=row['resource_id'],
            rank=rank,
            rrf_score=float(row['rrf_score']),
            bm25_rank=row['bm25_rank'],
            dense_rank=row['dense_rank'],
        )
        for rank, row in enumerate(rows, start=1)
    ]
