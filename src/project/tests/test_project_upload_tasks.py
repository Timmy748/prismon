from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from project import tasks

pytest_plugins = ('project.tests.fixtures.upload_intents',)
EXPECTED_EXPIRED_COUNT = 2


@pytest.mark.asyncio
async def test_finalize_upload_task_use_case_receives_storage_and_object_key(
    monkeypatch, shared_uow
):
    storage = Mock()
    finalize = AsyncMock()
    monkeypatch.setattr(tasks, 'create_storage', lambda: storage)
    monkeypatch.setattr(
        tasks,
        'create_project_unit_of_work',
        lambda: shared_uow,
    )
    monkeypatch.setattr(tasks, 'finalize_upload', finalize)

    await tasks._finalize_upload('uploads/staging-key')

    finalize.assert_awaited_once_with(
        shared_uow, storage, 'uploads/staging-key'
    )


@pytest.mark.asyncio
async def test_expiration_task_queues_each_ready_object_on_long_queue(
    monkeypatch, shared_uow
):
    storage = Mock()
    ready_keys = ['uploads/first', 'uploads/second']
    expire = AsyncMock(return_value=ready_keys)
    sender = Mock()
    monkeypatch.setattr(tasks, 'create_storage', lambda: storage)
    monkeypatch.setattr(
        tasks,
        'create_project_unit_of_work',
        lambda: shared_uow,
    )
    monkeypatch.setattr(
        tasks,
        'get_settings',
        lambda: SimpleNamespace(RUSTFS_UPLOAD_EXPIRATION_GRACE_SECONDS=600),
    )
    monkeypatch.setattr(tasks, 'expire_stale_upload_intents', expire)
    monkeypatch.setattr(tasks, 'send_task', sender)

    count = await tasks._expire_stale_uploads()

    assert count == len(ready_keys)
    expire.assert_awaited_once()
    assert [call.kwargs['args'] for call in sender.call_args_list] == [
        ['uploads/first'],
        ['uploads/second'],
    ]
    assert all(
        call.kwargs['queue'] == 'long_tasks' for call in sender.call_args_list
    )


@pytest.mark.asyncio
async def test_expiration_task_returns_zero_without_ready_uploads(
    monkeypatch, shared_uow
):
    monkeypatch.setattr(tasks, 'create_storage', Mock())
    monkeypatch.setattr(
        tasks,
        'create_project_unit_of_work',
        lambda: shared_uow,
    )
    monkeypatch.setattr(
        tasks,
        'get_settings',
        lambda: SimpleNamespace(RUSTFS_UPLOAD_EXPIRATION_GRACE_SECONDS=0),
    )
    monkeypatch.setattr(
        tasks, 'expire_stale_upload_intents', AsyncMock(return_value=[])
    )
    sender = Mock()
    monkeypatch.setattr(tasks, 'send_task', sender)

    result = await tasks._expire_stale_uploads()

    assert result == 0
    sender.assert_not_called()


def test_celery_entrypoints_run_async_task_implementations(monkeypatch):
    run = Mock(side_effect=[None, 2])
    monkeypatch.setattr(tasks.asyncio, 'run', run)

    finalized = tasks.finalize_upload_task('uploads/key')
    expired = tasks.expire_stale_uploads_task()

    assert finalized is None
    assert expired == EXPECTED_EXPIRED_COUNT
    assert run.call_count == EXPECTED_EXPIRED_COUNT
    for call in run.call_args_list:
        call.args[0].close()


def test_upload_tasks_have_long_queue_names_and_retry_policy():
    finalize = tasks.finalize_upload_task
    expire = tasks.expire_stale_uploads_task

    assert finalize.name == 'project.uploads.finalize'
    assert finalize.autoretry_for == (Exception,)
    assert finalize.retry_kwargs == {'max_retries': 8}
    assert expire.name == 'project.uploads.expire_stale'
    assert expire.retry_kwargs == {'max_retries': 5}
