from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any

from celery.result import AsyncResult

from infra.celery_app import celery_app


class TaskQueue(StrEnum):
    SHORT = 'short_tasks'
    LONG = 'long_tasks'


def send_task(
    name: str,
    args: Sequence[Any] | None = None,
    kwargs: Mapping[str, Any] | None = None,
    queue: TaskQueue = TaskQueue.SHORT,
    **options: Any,
) -> AsyncResult:
    return celery_app.send_task(
        name,
        args=args,
        kwargs=kwargs,
        queue=queue.value,
        **options,
    )
