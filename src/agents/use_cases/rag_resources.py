"""Authorize and load project text resources for RAG."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from time import monotonic

import httpx

from agents.clients.project import IProjectClient
from agents.dtos.search import HybridSearchCandidate
from infra.logs import get_logger

logger = get_logger(__name__)

DEFAULT_MAX_CONCURRENT_DOWNLOADS = 4
DEFAULT_MAX_RESOURCE_BYTES = 5 * 1024 * 1024
SUPPORTED_TEXT_CONTENT_TYPES = {
    'text/markdown',
    'text/plain',
}


@dataclass(frozen=True, slots=True)
class LoadedResource:
    resource_type: str
    resource_id: int
    rank: int
    media_type: str | None
    text: str | None
    error: str | None = None


async def load_rag_resources(
    candidates: Sequence[HybridSearchCandidate],
    project_client: IProjectClient,
    project_id: int,
    user_id: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[LoadedResource]:
    """Authorize, fetch, and decode project resources concurrently."""
    started_at = monotonic()
    logger.info(
        'RAG resource loading started: project_id=%d candidate_count=%d '
        'candidates=%s',
        project_id,
        len(candidates),
        [
            f'{candidate.resource_type}:{candidate.resource_id}'
            for candidate in candidates
        ],
    )
    semaphore = asyncio.Semaphore(DEFAULT_MAX_CONCURRENT_DOWNLOADS)
    owns_client = client is None
    http_client = client or httpx.AsyncClient(
        timeout=60.0, follow_redirects=True
    )

    async def load_one(candidate: HybridSearchCandidate) -> LoadedResource:
        async with semaphore:
            return await _load_resource(
                candidate,
                project_client,
                project_id,
                user_id,
                http_client,
            )

    try:
        results = await asyncio.gather(*(load_one(item) for item in candidates))
    finally:
        if owns_client:
            await http_client.aclose()

    ranked_results = sorted(results, key=lambda item: item.rank)
    logger.info(
        'RAG resource loading finished: project_id=%d elapsed_ms=%.1f '
        'loaded_count=%d failed_count=%d resources=%s',
        project_id,
        (monotonic() - started_at) * 1000,
        len(ranked_results),
        sum(resource.error is not None for resource in ranked_results),
        [
            {
                'type': resource.resource_type,
                'id': resource.resource_id,
                'rank': resource.rank,
                'media_type': resource.media_type,
                'text_length': len(resource.text or ''),
                'error': resource.error,
            }
            for resource in ranked_results
        ],
    )
    return ranked_results


async def _load_resource(
    candidate: HybridSearchCandidate,
    project_client: IProjectClient,
    project_id: int,
    user_id: int,
    client: httpx.AsyncClient,
) -> LoadedResource:
    logger.debug(
        'RAG resource download started: project_id=%d resource_type=%s '
        'resource_id=%d rank=%d',
        project_id,
        candidate.resource_type,
        candidate.resource_id,
        candidate.rank,
    )
    try:
        url = await _get_presigned_url(
            candidate, project_client, project_id, user_id
        )
        async with client.stream('GET', url) as response:
            response.raise_for_status()
            media_type = response.headers.get('content-type', '')
            media_type = media_type.partition(';')[0].strip().lower()
            if not _supports_content_type(media_type):
                logger.info(
                    'RAG resource skipped: project_id=%d resource_type=%s '
                    'resource_id=%d rank=%d media_type=%s '
                    'reason=unsupported_content_type',
                    project_id,
                    candidate.resource_type,
                    candidate.resource_id,
                    candidate.rank,
                    media_type or 'unknown',
                )
                return _resource_error(
                    candidate, 'unsupported_content_type', media_type
                )
            content = await _read_content(response, DEFAULT_MAX_RESOURCE_BYTES)
        if content is None:
            logger.warning(
                'RAG resource skipped: project_id=%d resource_type=%s '
                'resource_id=%d rank=%d max_bytes=%d '
                'reason=resource_too_large',
                project_id,
                candidate.resource_type,
                candidate.resource_id,
                candidate.rank,
                DEFAULT_MAX_RESOURCE_BYTES,
            )
            return _resource_error(candidate, 'resource_too_large', media_type)
        resource = _decode_resource(candidate, media_type, content)
        logger.info(
            'RAG resource downloaded: project_id=%d resource_type=%s '
            'resource_id=%d rank=%d media_type=%s bytes=%d text_length=%d',
            project_id,
            candidate.resource_type,
            candidate.resource_id,
            candidate.rank,
            media_type,
            len(content),
            len(resource.text or ''),
        )
        return resource
    except httpx.HTTPStatusError as error:
        logger.warning(
            'RAG resource download failed: project_id=%d resource_type=%s '
            'resource_id=%d rank=%d status_code=%d',
            project_id,
            candidate.resource_type,
            candidate.resource_id,
            candidate.rank,
            error.response.status_code,
        )
        return _resource_error(
            candidate, f'http_status_{error.response.status_code}'
        )
    except (httpx.HTTPError, OSError, ValueError) as error:
        logger.warning(
            'RAG resource download failed: project_id=%d resource_type=%s '
            'resource_id=%d rank=%d error_type=%s',
            project_id,
            candidate.resource_type,
            candidate.resource_id,
            candidate.rank,
            type(error).__name__,
        )
        return _resource_error(candidate, 'resource_load_failed')
    except Exception as error:
        logger.warning(
            'RAG resource could not be accessed: resource_type=%s '
            'resource_id=%s error_type=%s',
            candidate.resource_type,
            candidate.resource_id,
            type(error).__name__,
        )
        return _resource_error(
            candidate, 'resource_access_denied_or_unavailable'
        )


async def _get_presigned_url(
    candidate: HybridSearchCandidate,
    project_client: IProjectClient,
    project_id: int,
    user_id: int,
) -> str:
    if candidate.resource_type == 'document':
        return await project_client.get_document_file_url(
            project_id, user_id, candidate.resource_id, internal=True
        )
    return await project_client.get_asset_file_url(
        project_id, user_id, candidate.resource_id, internal=True
    )


async def _read_content(
    response: httpx.Response, max_resource_bytes: int
) -> bytes | None:
    content = bytearray()
    async for chunk in response.aiter_bytes():
        content.extend(chunk)
        if len(content) > max_resource_bytes:
            return None
    return bytes(content)


def _decode_resource(
    candidate: HybridSearchCandidate, media_type: str, content: bytes
) -> LoadedResource:
    return LoadedResource(
        resource_type=candidate.resource_type,
        resource_id=candidate.resource_id,
        rank=candidate.rank,
        media_type=media_type,
        text=_decode_text(content),
    )


def _resource_error(
    candidate: HybridSearchCandidate,
    error: str,
    media_type: str | None = None,
) -> LoadedResource:
    return LoadedResource(
        resource_type=candidate.resource_type,
        resource_id=candidate.resource_id,
        rank=candidate.rank,
        media_type=media_type,
        text=None,
        error=error,
    )


def _supports_content_type(content_type: str) -> bool:
    return content_type in SUPPORTED_TEXT_CONTENT_TYPES


def _decode_text(content: bytes) -> str:
    return content.decode('utf-8-sig', errors='replace').strip()
