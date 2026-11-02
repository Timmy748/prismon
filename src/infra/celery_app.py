from datetime import timedelta

from celery import Celery
from kombu import Exchange, Queue

from infra.settings import get_settings

settings = get_settings()

celery_app = Celery(
    'prismon',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_default_queue='short_tasks',
    task_queues=(
        Queue(
            'short_tasks',
            exchange=Exchange('short_tasks'),
            routing_key='short_tasks',
        ),
        Queue(
            'long_tasks',
            exchange=Exchange('long_tasks'),
            routing_key='long_tasks',
        ),
    ),
    task_default_delivery_mode='persistent',
    result_extended=True,
    imports=('project.tasks',),
    beat_schedule={
        'expire-stale-project-uploads': {
            'task': 'project.uploads.expire_stale',
            'schedule': timedelta(seconds=60),
            'options': {'queue': 'long_tasks'},
        },
    },
)
