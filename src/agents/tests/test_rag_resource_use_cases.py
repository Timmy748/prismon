from unittest.mock import AsyncMock, call

import httpx
import pytest

from agents.dtos.search import HybridSearchCandidate
from agents.use_cases import rag_resources
from agents.use_cases.rag_resources import load_rag_resources

PROJECT_ID = 7
USER_ID = 9


@pytest.mark.asyncio
async def test_load_rag_resources_keeps_human_text_and_skips_other_formats():
    content_by_path = {
        '/document-1': ('text/plain; charset=utf-8', b'first document'),
        '/document-2': ('text/markdown', b'# Human text'),
        '/document-3': ('text/html', b'<p>html is unsupported</p>'),
        '/document-4': ('application/json', b'{"ok": true}'),
        '/document-5': ('text/csv', b'name,age\nAda,37'),
        '/image-6': ('image/png', b'png-bytes'),
    }

    async def handler(request):
        content_type, content = content_by_path[request.url.path]
        return httpx.Response(
            200, headers={'content-type': content_type}, content=content
        )

    candidates = [
        HybridSearchCandidate('document', 1, 1, 0.04),
        HybridSearchCandidate('document', 2, 2, 0.03),
        HybridSearchCandidate('document', 3, 3, 0.02),
        HybridSearchCandidate('document', 4, 4, 0.01),
        HybridSearchCandidate('document', 5, 5, 0.005),
        HybridSearchCandidate('asset', 6, 6, 0.004),
    ]

    project_client = AsyncMock()

    async def get_document_url(project_id, user_id, document_id, *, internal):
        assert project_id == PROJECT_ID
        assert user_id == USER_ID
        assert internal is True
        return f'https://signed/document-{document_id}'

    async def get_asset_url(project_id, user_id, asset_id, *, internal):
        assert project_id == PROJECT_ID
        assert user_id == USER_ID
        assert internal is True
        return f'https://signed/image-{asset_id}'

    project_client.get_document_file_url.side_effect = get_document_url
    project_client.get_asset_file_url.side_effect = get_asset_url

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        loaded = await load_rag_resources(
            candidates,
            project_client,
            PROJECT_ID,
            USER_ID,
            client=client,
        )

    assert [resource.text for resource in loaded] == [
        'first document',
        '# Human text',
        None,
        None,
        None,
        None,
    ]
    assert [
        (resource.resource_type, resource.resource_id, resource.rank)
        for resource in loaded
    ] == [
        ('document', 1, 1),
        ('document', 2, 2),
        ('document', 3, 3),
        ('document', 4, 4),
        ('document', 5, 5),
        ('asset', 6, 6),
    ]
    assert loaded[2].error == 'unsupported_content_type'
    assert loaded[3].error == 'unsupported_content_type'
    assert loaded[4].error == 'unsupported_content_type'
    assert loaded[5].error == 'unsupported_content_type'
    assert all(resource.error is None for resource in [loaded[0], loaded[1]])
    assert project_client.get_document_file_url.await_args_list == [
        call(PROJECT_ID, USER_ID, 1, internal=True),
        call(PROJECT_ID, USER_ID, 2, internal=True),
        call(PROJECT_ID, USER_ID, 3, internal=True),
        call(PROJECT_ID, USER_ID, 4, internal=True),
        call(PROJECT_ID, USER_ID, 5, internal=True),
    ]
    project_client.get_asset_file_url.assert_awaited_once_with(
        PROJECT_ID, USER_ID, 6, internal=True
    )


@pytest.mark.asyncio
async def test_load_rag_resources_rejects_pdf_without_extracting_it():
    async def handler(request):
        del request
        return httpx.Response(
            200,
            headers={'content-type': 'application/pdf'},
            content=b'%PDF-not-extracted',
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        loaded = await load_rag_resources(
            [HybridSearchCandidate('document', 7, 1, 0.01)],
            AsyncMock(
                get_document_file_url=AsyncMock(
                    return_value='https://signed/document-7'
                )
            ),
            4,
            9,
            client=client,
        )

    assert len(loaded) == 1
    assert loaded[0].text is None
    assert loaded[0].error == 'unsupported_content_type'


@pytest.mark.asyncio
async def test_load_rag_resources_keeps_other_resources_on_download_failure():
    async def handler(request):
        if request.url.path.endswith('2'):
            return httpx.Response(403)
        return httpx.Response(
            200,
            headers={'content-type': 'text/plain'},
            content=b'available text',
        )

    candidates = [
        HybridSearchCandidate('document', 1, 1, 0.02),
        HybridSearchCandidate('asset', 2, 2, 0.01),
    ]
    project_client = AsyncMock(
        get_document_file_url=AsyncMock(return_value='https://signed/1'),
        get_asset_file_url=AsyncMock(return_value='https://signed/2'),
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        loaded = await load_rag_resources(
            candidates, project_client, 4, 9, client=client
        )

    assert loaded[0].text == 'available text'
    assert loaded[1].error == 'http_status_403'


@pytest.mark.asyncio
async def test_load_rag_resources_rejects_content_over_size_limit(monkeypatch):
    monkeypatch.setattr(rag_resources, 'DEFAULT_MAX_RESOURCE_BYTES', 3)

    async def handler(request):
        del request
        return httpx.Response(
            200, headers={'content-type': 'text/plain'}, content=b'four'
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        loaded = await load_rag_resources(
            [HybridSearchCandidate('document', 1, 1, 0.1)],
            AsyncMock(
                get_document_file_url=AsyncMock(return_value='https://signed/1')
            ),
            PROJECT_ID,
            USER_ID,
            client=client,
        )

    assert loaded[0].text is None
    assert loaded[0].error == 'resource_too_large'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('exception', 'expected_error'),
    [
        (httpx.ConnectError('connection refused'), 'resource_load_failed'),
        (
            RuntimeError('authorization client failed'),
            'resource_access_denied_or_unavailable',
        ),
    ],
)
async def test_load_rag_resources_translates_download_exceptions(
    exception, expected_error
):
    project_client = AsyncMock()
    project_client.get_document_file_url.side_effect = exception

    loaded = await load_rag_resources(
        [HybridSearchCandidate('document', 1, 1, 0.1)],
        project_client,
        PROJECT_ID,
        USER_ID,
    )

    assert loaded[0].error == expected_error
