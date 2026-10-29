import asyncio

import pytest
from botocore.exceptions import ClientError
from pydantic import ValidationError

from project.settings import Settings
from project.storage import RustFSStorage

EXPECTED_CONCURRENT_WRITE_COUNT = 2
EXPECTED_TTL_SECONDS = 75


@pytest.mark.asyncio
async def test_save_creates_object_and_sends_content_type(rustfs_storage):
    adapter, client, session = rustfs_storage

    await adapter.save('folder/file.pdf', b'data', 'application/pdf')

    client.head_bucket.assert_awaited_once_with(Bucket='test-bucket')
    client.put_object.assert_awaited_once_with(
        Bucket='test-bucket',
        Key='folder/file.pdf',
        Body=b'data',
        ContentType='application/pdf',
    )
    assert session.client_calls[0][1]['endpoint_url'] == 'http://rustfs:9000'
    assert session.client_calls[1][1]['endpoint_url'] == 'http://rustfs:9000'


@pytest.mark.asyncio
async def test_save_omits_content_type_when_unspecified(rustfs_storage):
    adapter, client, _ = rustfs_storage

    await adapter.save('file', b'data')

    client.put_object.assert_awaited_once_with(
        Bucket='test-bucket', Key='file', Body=b'data'
    )


@pytest.mark.asyncio
async def test_save_does_not_recheck_bucket_after_first_write(rustfs_storage):
    adapter, client, _ = rustfs_storage

    await adapter.save('first', b'one')
    await adapter.save('second', b'two')

    client.head_bucket.assert_awaited_once_with(Bucket='test-bucket')


@pytest.mark.asyncio
async def test_save_creates_bucket_when_head_bucket_returns_not_found(
    rustfs_storage,
):
    adapter, client, _ = rustfs_storage
    client.head_bucket.side_effect = ClientError(
        {
            'Error': {'Code': '404', 'Message': 'missing'},
            'ResponseMetadata': {'HTTPStatusCode': 404},
        },
        'HeadBucket',
    )

    await adapter.save('file', b'data')

    client.create_bucket.assert_awaited_once_with(Bucket='test-bucket')
    client.put_object.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'error_code', ['BucketAlreadyExists', 'BucketAlreadyOwnedByYou']
)
async def test_save_accepts_bucket_already_created_by_another_request(
    rustfs_storage, error_code
):
    adapter, client, _ = rustfs_storage
    client.head_bucket.side_effect = ClientError(
        {
            'Error': {'Code': 'NoSuchBucket', 'Message': 'missing'},
            'ResponseMetadata': {'HTTPStatusCode': 404},
        },
        'HeadBucket',
    )
    client.create_bucket.side_effect = ClientError(
        {
            'Error': {'Code': error_code, 'Message': 'exists'},
            'ResponseMetadata': {'HTTPStatusCode': 409},
        },
        'CreateBucket',
    )

    await adapter.save('file', b'data')

    client.put_object.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_propagates_unexpected_bucket_check_error(rustfs_storage):
    adapter, client, _ = rustfs_storage
    error = ClientError(
        {
            'Error': {'Code': 'AccessDenied', 'Message': 'denied'},
            'ResponseMetadata': {'HTTPStatusCode': 403},
        },
        'HeadBucket',
    )
    client.head_bucket.side_effect = error

    with pytest.raises(ClientError) as raised:
        await adapter.save('file', b'data')

    assert raised.value is error
    client.create_bucket.assert_not_awaited()
    client.put_object.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_propagates_unexpected_bucket_creation_error(
    rustfs_storage,
):
    adapter, client, _ = rustfs_storage
    client.head_bucket.side_effect = ClientError(
        {
            'Error': {'Code': 'NotFound', 'Message': 'missing'},
            'ResponseMetadata': {'HTTPStatusCode': 404},
        },
        'HeadBucket',
    )
    error = ClientError(
        {
            'Error': {'Code': 'AccessDenied', 'Message': 'denied'},
            'ResponseMetadata': {'HTTPStatusCode': 403},
        },
        'CreateBucket',
    )
    client.create_bucket.side_effect = error

    with pytest.raises(ClientError) as raised:
        await adapter.save('file', b'data')

    assert raised.value is error
    client.put_object.assert_not_awaited()


@pytest.mark.asyncio
async def test_bucket_is_checked_only_once_for_concurrent_writes(
    rustfs_storage,
):
    adapter, client, _ = rustfs_storage
    head_entered = asyncio.Event()
    allow_head_to_finish = asyncio.Event()

    async def wait_for_head_bucket(**kwargs):
        del kwargs
        head_entered.set()
        await allow_head_to_finish.wait()

    client.head_bucket.side_effect = wait_for_head_bucket
    first_write = asyncio.create_task(adapter.save('first', b'one'))
    await head_entered.wait()
    second_write = asyncio.create_task(adapter.save('second', b'two'))
    allow_head_to_finish.set()

    await asyncio.gather(first_write, second_write)

    client.head_bucket.assert_awaited_once_with(Bucket='test-bucket')
    assert client.put_object.await_count == EXPECTED_CONCURRENT_WRITE_COUNT


@pytest.mark.asyncio
async def test_update_replaces_existing_object_with_content_type(
    rustfs_storage,
):
    adapter, client, _ = rustfs_storage

    await adapter.update('existing', b'new', 'image/png')

    client.head_object.assert_awaited_once_with(
        Bucket='test-bucket', Key='existing'
    )
    client.put_object.assert_awaited_once_with(
        Bucket='test-bucket',
        Key='existing',
        Body=b'new',
        ContentType='image/png',
    )


@pytest.mark.asyncio
async def test_update_omits_content_type_when_unspecified(rustfs_storage):
    adapter, client, _ = rustfs_storage

    await adapter.update('existing', b'new')

    client.put_object.assert_awaited_once_with(
        Bucket='test-bucket', Key='existing', Body=b'new'
    )


@pytest.mark.asyncio
async def test_update_propagates_when_object_does_not_exist(rustfs_storage):
    adapter, client, _ = rustfs_storage
    error = ClientError(
        {
            'Error': {'Code': '404', 'Message': 'missing'},
            'ResponseMetadata': {'HTTPStatusCode': 404},
        },
        'HeadObject',
    )
    client.head_object.side_effect = error

    with pytest.raises(ClientError) as raised:
        await adapter.update('missing', b'new')

    assert raised.value is error
    client.put_object.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_removes_object_from_internal_endpoint(rustfs_storage):
    adapter, client, session = rustfs_storage

    await adapter.delete('file')

    client.delete_object.assert_awaited_once_with(
        Bucket='test-bucket', Key='file'
    )
    assert session.client_calls[0][1]['endpoint_url'] == 'http://rustfs:9000'


@pytest.mark.asyncio
async def test_presigned_view_url_uses_public_endpoint_and_configured_ttl(
    rustfs_storage,
):
    adapter, client, session = rustfs_storage

    result = await adapter.get_presigned_url('file')

    assert result == 'https://rustfs.test/signed'
    client.generate_presigned_url.assert_awaited_once_with(
        'get_object',
        Params={
            'Bucket': 'test-bucket',
            'Key': 'file',
            'ResponseContentDisposition': 'inline',
        },
        ExpiresIn=900,
    )
    assert session.client_calls[0][1]['endpoint_url'] == (
        'http://localhost:9000'
    )


@pytest.mark.asyncio
async def test_presigned_download_url_encodes_filename(rustfs_storage):
    adapter, client, _ = rustfs_storage

    await adapter.get_presigned_url('file', 'reports/quarterly 1.pdf')

    params = client.generate_presigned_url.await_args.kwargs['Params']
    assert params['ResponseContentDisposition'] == (
        "attachment; filename*=UTF-8''quarterly%201.pdf"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('filename', 'expected'),
    [
        (None, 'inline'),
        ('folder\\name\r\n.pdf', "attachment; filename*=UTF-8''name.pdf"),
        ('/\r\n', "attachment; filename*=UTF-8''download"),
    ],
)
async def test_presigned_url_sanitizes_download_filename(
    rustfs_storage, filename, expected
):
    adapter, client, _ = rustfs_storage

    await adapter.get_presigned_url('file', filename)

    params = client.generate_presigned_url.await_args.kwargs['Params']
    assert params['ResponseContentDisposition'] == expected


def test_settings_load_presigned_ttl_from_environment(
    set_required_project_environment,
):
    set_required_project_environment(EXPECTED_TTL_SECONDS)

    settings = Settings(_env_file=None)

    assert settings.RUSTFS_PRESIGNED_URL_TTL_SECONDS == EXPECTED_TTL_SECONDS


def test_settings_reject_invalid_presigned_ttl(
    set_required_project_environment,
):
    set_required_project_environment(0)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_create_storage_returns_rustfs_adapter(rustfs_storage):
    adapter, _, _ = rustfs_storage

    assert isinstance(adapter, RustFSStorage)
