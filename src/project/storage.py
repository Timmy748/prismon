from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from http import HTTPStatus
from typing import Any, Protocol
from urllib.parse import quote

import aioboto3
from botocore.config import Config
from botocore.exceptions import ClientError

from infra.logs import get_logger
from infra.settings import get_settings

logger = get_logger(__name__)


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

    async def delete(self, key: str) -> None: ...

    async def get_presigned_url(
        self,
        key: str,
        download_filename: str | None = None,
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

    async def get_presigned_url(
        self,
        key: str,
        download_filename: str | None = None,
    ) -> str:
        params: dict[str, str] = {
            'Bucket': self._settings.RUSTFS_BUCKET,
            'Key': key,
            'ResponseContentDisposition': self._content_disposition(
                download_filename
            ),
        }
        async with self._client(
            self._settings.RUSTFS_PUBLIC_ENDPOINT_URL
        ) as client:
            return await client.generate_presigned_url(
                'get_object',
                Params=params,
                ExpiresIn=self._settings.RUSTFS_PRESIGNED_URL_TTL_SECONDS,
            )

    @staticmethod
    def _content_disposition(filename: str | None) -> str:
        if filename is None:
            return 'inline'
        safe_filename = filename.replace('\\', '/').rsplit('/', maxsplit=1)[-1]
        safe_filename = ''.join(
            character
            for character in safe_filename
            if character >= ' ' and character != '\x7f'
        ).strip()
        if not safe_filename:
            safe_filename = 'download'
        encoded_filename = quote(safe_filename, safe='!#$&+-.^_`|~')
        return f"attachment; filename*=UTF-8''{encoded_filename}"


def create_storage() -> IStorage:  # pragma: no cover
    return RustFSStorage()
