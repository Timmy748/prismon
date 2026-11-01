import asyncio
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import Mock

from infra import app as app_module


def test_unhandled_exception_is_logged_and_returns_internal_server_error(
    monkeypatch,
):
    logger = Mock()
    monkeypatch.setattr(app_module, 'logger', logger)
    request = SimpleNamespace(
        method='POST',
        url=SimpleNamespace(path='/projects/1/api-keys'),
    )
    error = ValueError('request failed')

    response = asyncio.run(
        app_module.handle_unhandled_exception(request, error)
    )

    logger.error.assert_called_once()
    assert logger.error.call_args.args == (
        'Unhandled API exception: method=%s path=%s',
        'POST',
        '/projects/1/api-keys',
    )
    assert logger.error.call_args.kwargs['exc_info'] == (
        ValueError,
        error,
        error.__traceback__,
    )
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.body == b'Internal Server Error'
