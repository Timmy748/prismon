import hmac
from collections.abc import Callable
from http import HTTPStatus
from urllib.parse import unquote_plus

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response

from infra.logs import get_logger
from infra.settings import get_settings
from infra.tasks import TaskQueue, send_task
from project.unit_of_work import IProjectUnitOfWork, create_project_unit_of_work
from project.use_cases.upload_notifications import should_finalize_upload

logger = get_logger(__name__)


def _has_valid_token(authorization: str | None, expected_token: str) -> bool:
    scheme, separator, provided_token = (authorization or '').partition(' ')
    return (
        scheme.lower() == 'bearer'
        and bool(separator)
        and hmac.compare_digest(provided_token, expected_token)
    )


def _upload_keys(payload: dict, bucket_name: str) -> list[str]:
    records = payload.get('Records')
    if not isinstance(records, list):
        raise ValueError('RustFS event payload must contain Records')

    keys = []
    for record in records:
        if not isinstance(record, dict):
            continue
        event_name = record.get('eventName') or payload.get('EventName')
        if not isinstance(event_name, str) or not event_name.startswith(
            's3:ObjectCreated:'
        ):
            continue
        storage_record = record.get('s3')
        if not isinstance(storage_record, dict):
            continue
        bucket_record = storage_record.get('bucket')
        object_record = storage_record.get('object')
        if not isinstance(bucket_record, dict) or not isinstance(
            object_record, dict
        ):
            continue
        if bucket_record.get('name') != bucket_name:
            continue
        encoded_key = object_record.get('key')
        if not isinstance(encoded_key, str):
            continue
        object_key = unquote_plus(encoded_key)
        if object_key.startswith('uploads/'):
            keys.append(object_key)
    return keys


def _enqueue_upload_finalization(object_key: str) -> None:
    send_task(
        'project.uploads.finalize',
        args=[object_key],
        queue=TaskQueue.LONG,
    )


def create_rustfs_webhook_router(
    unit_of_work_factory: Callable[[], IProjectUnitOfWork] = (
        create_project_unit_of_work
    ),
) -> APIRouter:
    router = APIRouter()

    @router.post('/internal/webhooks/rustfs', include_in_schema=False)
    async def receive_rustfs_event(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> Response:
        settings = get_settings()
        expected_token = settings.RUSTFS_WEBHOOK_AUTH_TOKEN.get_secret_value()
        if not expected_token:
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                detail='RustFS webhook is not configured',
            )
        if not _has_valid_token(authorization, expected_token):
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail='Invalid webhook token',
            )

        try:
            payload = await request.json()
        except ValueError as error:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail='Invalid RustFS event payload',
            ) from error
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail='Invalid RustFS event payload',
            )
        try:
            object_keys = _upload_keys(payload, settings.RUSTFS_BUCKET)
        except ValueError as error:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=str(error),
            ) from error

        for object_key in object_keys:
            async with unit_of_work_factory() as unit_of_work:
                should_finalize = await should_finalize_upload(
                    unit_of_work, object_key
                )
            if should_finalize:
                try:
                    _enqueue_upload_finalization(object_key)
                    logger.info(
                        'RustFS upload queued for finalization: key=%s',
                        object_key,
                    )
                except Exception as error:
                    logger.exception(
                        'Failed to enqueue upload finalization: key=%s',
                        object_key,
                    )
                    raise HTTPException(
                        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                        detail='Could not queue upload finalization',
                    ) from error
            else:
                logger.warning(
                    'RustFS upload notification ignored: no active intent '
                    'or completion event for key=%s',
                    object_key,
                )

        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router


router = create_rustfs_webhook_router()
