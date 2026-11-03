from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from http import HTTPStatus
from threading import Lock
from typing import Any, Literal, Protocol
from urllib.parse import quote

import aioboto3
from botocore.config import Config
from botocore.exceptions import ClientError

from infra.logs import get_logger
from infra.settings import get_settings
from project.utils.files import normalize_filename

logger = get_logger(__name__)

_notification_cache_lock = Lock()
_configured_notification_buckets: set[tuple[str, str]] = set()


class IStorage(Protocol):
    async def save(
        self,
        key: str,
        content: bytes,
        content_type: str | None = None,
    ) -> None: ...

    async def update(
        self,
        key: str,
        content: bytes,
        content_type: str | None = None,
    ) -> None: ...

    async def copy_object(
        self, source_key: str, destination_key: str
    ) -> None: ...

    async def delete(self, key: str) -> None: ...

    async def object_exists(self, key: str) -> bool: ...

    async def generate_presigned_put_url(
        self,
        key: str,
        content_type: str | None,
        expires_in: int,
    ) -> str: ...

    async def get_presigned_url(
        self,
        key: str,
        download_filename: str | None = None,
        content_type: str | None = None,
        disposition: Literal['attachment', 'inline'] = 'attachment',
        endpoint_url: str | None = None,
    ) -> str: ...


class RustFSStorage:
    """Async S3-compatible storage adapter for RustFS."""

    def __init__(
        self,
    ) -> None:
        self._settings = get_settings()
        self._session = aioboto3.Session()
        self._bucket_ready = False
        self._bucket_lock = asyncio.Lock()
        self._upload_notifications_ready = False
        self._upload_notifications_lock = asyncio.Lock()

        logger.info('RustFS project storage initialized')

    def _client(self, endpoint_url: str) -> AbstractAsyncContextManager[Any]:
        return self._session.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=self._settings.RUSTFS_ACCESS_KEY,
            aws_secret_access_key=self._settings.RUSTFS_SECRET_KEY,
            region_name=self._settings.RUSTFS_REGION,
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'},
            ),
        )

    async def _ensure_bucket(self) -> None:
        if self._bucket_ready:
            return
        async with self._bucket_lock:
            if self._bucket_ready:
                return
            async with self._client(
                self._settings.RUSTFS_ENDPOINT_URL
            ) as client:
                try:
                    await client.head_bucket(
                        Bucket=self._settings.RUSTFS_BUCKET
                    )
                except ClientError as error:
                    error_code = error.response.get('Error', {}).get('Code')
                    status_code = error.response.get(
                        'ResponseMetadata', {}
                    ).get('HTTPStatusCode')
                    if (
                        error_code not in {'404', 'NoSuchBucket', 'NotFound'}
                        and status_code != HTTPStatus.NOT_FOUND
                    ):
                        raise
                    try:
                        await client.create_bucket(
                            Bucket=self._settings.RUSTFS_BUCKET
                        )
                    except ClientError as create_error:
                        create_code = create_error.response.get(
                            'Error', {}
                        ).get('Code')
                        if create_code not in {
                            'BucketAlreadyExists',
                            'BucketAlreadyOwnedByYou',
                        }:
                            raise
            self._bucket_ready = True
            logger.info(
                'RustFS bucket is ready: bucket=%s',
                self._settings.RUSTFS_BUCKET,
            )

    async def save(
        self,
        key: str,
        content: bytes,
        content_type: str | None = None,
    ) -> None:
        """Store content at a new key.

        Callers should generate a unique key. Use ``update`` when replacing
        the bytes already stored at an existing key.
        """
        await self._ensure_bucket()
        await self._put_object(key, content, content_type)
        logger.debug(
            'Project file stored in RustFS: size_bytes=%s', len(content)
        )

    async def update(
        self,
        key: str,
        content: bytes,
        content_type: str | None = None,
    ) -> None:
        """Replace the content of an existing object key."""
        await self._ensure_bucket()
        async with self._client(self._settings.RUSTFS_ENDPOINT_URL) as client:
            await client.head_object(
                Bucket=self._settings.RUSTFS_BUCKET,
                Key=key,
            )
            await client.put_object(
                Bucket=self._settings.RUSTFS_BUCKET,
                Key=key,
                Body=content,
                **({'ContentType': content_type} if content_type else {}),
            )
        logger.debug(
            'Project file updated in RustFS: size_bytes=%s', len(content)
        )

    async def copy_object(self, source_key: str, destination_key: str) -> None:
        await self._ensure_bucket()
        async with self._client(self._settings.RUSTFS_ENDPOINT_URL) as client:
            await client.copy_object(
                Bucket=self._settings.RUSTFS_BUCKET,
                Key=destination_key,
                CopySource={
                    'Bucket': self._settings.RUSTFS_BUCKET,
                    'Key': source_key,
                },
                MetadataDirective='COPY',
            )
        logger.debug(
            'Project file copied in RustFS: source_key=%s destination_key=%s',
            source_key,
            destination_key,
        )

    async def _put_object(
        self,
        key: str,
        content: bytes,
        content_type: str | None,
    ) -> None:
        async with self._client(self._settings.RUSTFS_ENDPOINT_URL) as client:
            await client.put_object(
                Bucket=self._settings.RUSTFS_BUCKET,
                Key=key,
                Body=content,
                **({'ContentType': content_type} if content_type else {}),
            )

    async def delete(self, key: str) -> None:
        async with self._client(self._settings.RUSTFS_ENDPOINT_URL) as client:
            await client.delete_object(
                Bucket=self._settings.RUSTFS_BUCKET,
                Key=key,
            )
        logger.debug('Project file deleted from RustFS')

    async def object_exists(self, key: str) -> bool:
        await self._ensure_bucket()
        async with self._client(self._settings.RUSTFS_ENDPOINT_URL) as client:
            try:
                await client.head_object(
                    Bucket=self._settings.RUSTFS_BUCKET,
                    Key=key,
                )
            except ClientError as error:
                error_code = error.response.get('Error', {}).get('Code')
                status_code = error.response.get('ResponseMetadata', {}).get(
                    'HTTPStatusCode'
                )
                if error_code in {'404', 'NoSuchKey', 'NotFound'} or (
                    status_code == HTTPStatus.NOT_FOUND
                ):
                    return False
                raise
        return True

    async def generate_presigned_put_url(
        self,
        key: str,
        content_type: str | None,
        expires_in: int,
    ) -> str:
        await self._ensure_bucket()
        await self.ensure_upload_notifications()
        params: dict[str, str] = {
            'Bucket': self._settings.RUSTFS_BUCKET,
            'Key': key,
        }
        if content_type is not None:
            params['ContentType'] = content_type
        async with self._client(
            self._settings.RUSTFS_PUBLIC_ENDPOINT_URL
        ) as client:
            return await client.generate_presigned_url(
                'put_object', Params=params, ExpiresIn=expires_in
            )

    async def ensure_upload_notifications(self) -> None:
        await self._ensure_bucket()
        cache_key = (
            self._settings.RUSTFS_ENDPOINT_URL,
            self._settings.RUSTFS_BUCKET,
        )
        with _notification_cache_lock:
            if cache_key in _configured_notification_buckets:
                self._upload_notifications_ready = True
        if self._upload_notifications_ready:
            return
        async with self._upload_notifications_lock:
            if self._upload_notifications_ready:
                return
            token = self._settings.RUSTFS_WEBHOOK_AUTH_TOKEN.get_secret_value()
            if not token:
                raise RuntimeError(
                    'RUSTFS_WEBHOOK_AUTH_TOKEN must be configured before '
                    'issuing upload URLs'
                )

            target_arn = (
                f'arn:rustfs:sqs:{self._settings.RUSTFS_REGION}:primary:webhook'
            )
            rule = {
                'Id': 'prismon-uploads',
                'QueueArn': target_arn,
                'Events': ['s3:ObjectCreated:*'],
                'Filter': {
                    'Key': {
                        'FilterRules': [{'Name': 'prefix', 'Value': 'uploads/'}]
                    }
                },
            }
            async with self._client(
                self._settings.RUSTFS_ENDPOINT_URL
            ) as client:
                response = await client.get_bucket_notification_configuration(
                    Bucket=self._settings.RUSTFS_BUCKET
                )
                configuration = {
                    key: response[key]
                    for key in (
                        'QueueConfigurations',
                        'TopicConfigurations',
                        'LambdaFunctionConfigurations',
                        'EventBridgeConfiguration',
                    )
                    if key in response
                }
                queue_configurations = list(
                    configuration.get('QueueConfigurations', [])
                )
                if any(current == rule for current in queue_configurations):
                    self._upload_notifications_ready = True
                    with _notification_cache_lock:
                        _configured_notification_buckets.add(cache_key)
                    return
                queue_configurations = [
                    current
                    for current in queue_configurations
                    if current.get('Id') != rule['Id']
                ]
                queue_configurations.append(rule)
                configuration['QueueConfigurations'] = queue_configurations
                await client.put_bucket_notification_configuration(
                    Bucket=self._settings.RUSTFS_BUCKET,
                    NotificationConfiguration=configuration,
                )
            self._upload_notifications_ready = True
            with _notification_cache_lock:
                _configured_notification_buckets.add(cache_key)

    async def get_presigned_url(
        self,
        key: str,
        download_filename: str | None = None,
        content_type: str | None = None,
        disposition: Literal['attachment', 'inline'] = 'attachment',
        endpoint_url: str | None = None,
    ) -> str:
        params: dict[str, str] = {
            'Bucket': self._settings.RUSTFS_BUCKET,
            'Key': key,
            'ResponseContentDisposition': self._content_disposition(
                download_filename, disposition
            ),
        }
        if content_type is not None:
            params['ResponseContentType'] = content_type
        async with self._client(
            endpoint_url or self._settings.RUSTFS_PUBLIC_ENDPOINT_URL
        ) as client:
            return await client.generate_presigned_url(
                'get_object',
                Params=params,
                ExpiresIn=self._settings.RUSTFS_PRESIGNED_URL_TTL_SECONDS,
            )

    @staticmethod
    def _content_disposition(
        filename: str | None,
        disposition: Literal['attachment', 'inline'] = 'attachment',
    ) -> str:
        if filename is None:
            return 'inline'
        safe_filename = normalize_filename(filename)
        encoded_filename = quote(safe_filename, safe='!#$&+-.^_`|~')
        return f"{disposition}; filename*=UTF-8''{encoded_filename}"


def create_storage() -> IStorage:  # pragma: no cover
    return RustFSStorage()
