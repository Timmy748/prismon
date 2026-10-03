import pytest

from project.dtos.page import PaginationDTO
from project.entities.document import DocumentStatus
from project.repositories.document import DocumentRepository


@pytest.mark.asyncio
async def test_create_and_get_document(
    document_repo: DocumentRepository, sample_project
) -> None:
    created = await document_repo.create_document(
        sample_project.id, 'https://files.test/voice.pdf', 'Voice guide'
    )

    loaded = await document_repo.get_document(created.id)

    assert loaded is not None
    assert loaded.file == 'https://files.test/voice.pdf'
    assert loaded.status == DocumentStatus.DRAFT


@pytest.mark.asyncio
async def test_get_documents_filters_name_and_status(
    document_repo: DocumentRepository, sample_project
) -> None:
    wanted = await document_repo.create_document(
        sample_project.id,
        'url-a',
        'Voice guide',
        status=DocumentStatus.PUBLISHED,
    )
    await document_repo.create_document(
        sample_project.id, 'url-b', 'Logo guide', status=DocumentStatus.DRAFT
    )

    page = await document_repo.get_documents(
        sample_project.id,
        pagination=PaginationDTO(limit=1),
        name='Voice',
        status=DocumentStatus.PUBLISHED,
    )

    assert [item.id for item in page.items] == [wanted.id]
    assert page.pagination.cursor is None
    assert page.pagination.more is False


@pytest.mark.asyncio
async def test_update_and_delete_document(
    document_repo: DocumentRepository, sample_project
) -> None:
    created = await document_repo.create_document(
        sample_project.id, 'url-old', 'Draft'
    )

    updated = await document_repo.update_document(
        created.id,
        file='url-new',
        name='Published',
        description='Updated description',
        status=DocumentStatus.PUBLISHED,
    )
    deleted = await document_repo.delete_document(created.id)

    assert updated is not None and updated.file == 'url-new'
    assert deleted is None
    assert await document_repo.get_document(created.id) is None


@pytest.mark.asyncio
async def test_update_document_returns_none_when_missing(
    document_repo: DocumentRepository,
) -> None:
    result = await document_repo.update_document(404, name='Missing')

    assert result is None


@pytest.mark.asyncio
async def test_delete_document_does_nothing_when_missing(
    document_repo: DocumentRepository,
) -> None:
    result = await document_repo.delete_document(404)

    assert result is None


@pytest.mark.asyncio
async def test_document_cursor_returns_older_documents(
    document_repo: DocumentRepository, sample_project
) -> None:
    documents = [
        await document_repo.create_document(
            sample_project.id, f'url-{index}', f'Document {index}'
        )
        for index in range(3)
    ]

    first_page = await document_repo.get_documents(
        sample_project.id, pagination=PaginationDTO(limit=1)
    )
    second_page = await document_repo.get_documents(
        sample_project.id,
        pagination=PaginationDTO(limit=1, cursor=first_page.pagination.cursor),
    )

    assert first_page.items[0].id == documents[-1].id
    assert second_page.items[0].id == documents[-2].id
    assert first_page.pagination.more is True
