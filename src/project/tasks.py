import asyncio
from datetime import UTC, datetime, timedelta

from infra.celery_app import celery_app
from infra.settings import get_settings
from infra.tasks import TaskQueue, send_task
from project.storage import create_storage
from project.unit_of_work import create_project_unit_of_work
from project.use_cases.upload_intents import (
    expire_stale_upload_intents,
    finalize_upload,
)


@celery_app.task(
    name='project.uploads.finalize',
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 8},
)
def finalize_upload_task(object_key: str) -> None:
    asyncio.run(_finalize_upload(object_key))


async def _finalize_upload(object_key: str) -> None:
    storage = create_storage()
    async with create_project_unit_of_work() as uow:
        await finalize_upload(uow, storage, object_key)


@celery_app.task(
    name='project.uploads.expire_stale',
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 5},
)
def expire_stale_uploads_task() -> int:
    return asyncio.run(_expire_stale_uploads())


async def _expire_stale_uploads() -> int:
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(
        seconds=settings.RUSTFS_UPLOAD_EXPIRATION_GRACE_SECONDS
    )
    storage = create_storage()
    async with create_project_unit_of_work() as uow:
        ready_to_promote = await expire_stale_upload_intents(
            uow, storage, cutoff
        )

    for object_key in ready_to_promote:
        send_task(
            'project.uploads.finalize',
            args=[object_key],
            queue=TaskQueue.LONG,
        )
    return len(ready_to_promote)
