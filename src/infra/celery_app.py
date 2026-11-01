from celery import Celery
from kombu import Queue

from infra.settings import get_settings

settings = get_settings()

celery_app = Celery(
    'prismon',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_default_queue='short_tasks',
    task_queues=(Queue('short_tasks'), Queue('long_tasks')),
    task_default_delivery_mode='persistent',
    result_extended=True,
)
