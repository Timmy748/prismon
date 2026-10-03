# ruff: noqa: PLR2004
import base64
import json
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from project.utils.pagination import decode_cursor, encode_cursor


def test_cursor_round_trip() -> None:
    cursor = (datetime(2026, 10, 3, tzinfo=UTC), 42)
    assert decode_cursor(encode_cursor(cursor)) == cursor


@pytest.mark.parametrize('value', ['bad', 'e30', 'W10sIngiXQ', 'W10sMF0'])
def test_invalid_cursor_is_bad_request(value: str) -> None:
    with pytest.raises(HTTPException) as error:
        decode_cursor(value)
    assert error.value.status_code == 400


def test_naive_cursor_timestamp_is_assumed_utc() -> None:
    payload = (
        base64.urlsafe_b64encode(
            json.dumps(['2026-10-03T12:00:00', 42]).encode()
        )
        .decode()
        .rstrip('=')
    )
    assert decode_cursor(payload) == (datetime(2026, 10, 3, 12, tzinfo=UTC), 42)


def test_cursor_with_invalid_value_types_is_bad_request() -> None:
    payload = base64.urlsafe_b64encode(json.dumps([5, True]).encode())
    with pytest.raises(HTTPException) as error:
        decode_cursor(payload.decode().rstrip('='))
    assert error.value.status_code == 400
