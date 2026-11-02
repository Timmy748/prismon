# ruff: noqa: PLR2004

from unittest.mock import Mock

from celery.result import AsyncResult

from infra import tasks
from infra.celery_app import celery_app
from infra.settings import get_settings
from infra.tasks import TaskQueue


def test_celery_app_uses_configured_broker_and_result_backend():
    settings = get_settings()

    assert celery_app.conf.broker_url == settings.CELERY_BROKER_URL
    assert celery_app.conf.result_backend == settings.CELERY_RESULT_BACKEND


def test_celery_app_registers_short_and_long_queues_with_short_default():
    queues = {queue.name: queue for queue in celery_app.conf.task_queues}

    assert list(queues) == ['short_tasks', 'long_tasks']
    assert celery_app.conf.task_default_queue == 'short_tasks'
    assert queues['short_tasks'].exchange.name == 'short_tasks'
    assert queues['short_tasks'].routing_key == 'short_tasks'
    assert queues['long_tasks'].exchange.name == 'long_tasks'
    assert queues['long_tasks'].routing_key == 'long_tasks'


def test_celery_imports_upload_tasks_and_schedules_expiration_on_long_queue():
    schedule = celery_app.conf.beat_schedule['expire-stale-project-uploads']

    assert celery_app.conf.imports == ('project.tasks',)
    assert schedule['task'] == 'project.uploads.expire_stale'
    assert schedule['schedule'].total_seconds() == 60
    assert schedule['options'] == {'queue': 'long_tasks'}


def test_send_task_uses_short_queue_and_forwards_arguments_and_options(
    monkeypatch,
):
    expected_result = AsyncResult('task-id', app=celery_app)
    send_task = Mock(return_value=expected_result)
    monkeypatch.setattr(tasks.celery_app, 'send_task', send_task)
    args = ['user@example.com']
    kwargs = {'subject': 'Welcome'}

    result = tasks.send_task(
        'emails.send',
        args=args,
        kwargs=kwargs,
        countdown=10,
    )

    send_task.assert_called_once_with(
        'emails.send',
        args=args,
        kwargs=kwargs,
        queue='short_tasks',
        countdown=10,
    )
    assert result is expected_result


def test_send_task_uses_long_queue_when_requested(monkeypatch):
    expected_result = AsyncResult('task-id', app=celery_app)
    send_task = Mock(return_value=expected_result)
    monkeypatch.setattr(tasks.celery_app, 'send_task', send_task)

    result = tasks.send_task('reports.generate', queue=TaskQueue.LONG)

    send_task.assert_called_once_with(
        'reports.generate',
        args=None,
        kwargs=None,
        queue='long_tasks',
    )
    assert result is expected_result


# placeholder
