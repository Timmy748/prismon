import base64
import json
from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from fastapi import HTTPException

from agents.dtos.page import PaginationDTO
from agents.utils.pagination import decode_cursor, encode_cursor, pagination_dto


def test_encode_cursor_returns_none_for_missing_cursor():
    cursor = None

    result = encode_cursor(cursor)

    assert result is None


def test_decode_cursor_returns_none_for_missing_cursor():
    cursor = None

    result = decode_cursor(cursor)

    assert result is None


def test_encode_and_decode_cursor_roundtrip():
    cursor = (datetime(2025, 2, 3, 4, 5, 6, tzinfo=UTC), 12)

    encoded = encode_cursor(cursor)
    result = decode_cursor(encoded)

    assert result == cursor


def test_decode_cursor_assigns_utc_to_timestamp_without_timezone():
    payload = json.dumps(['2025-02-03T04:05:06', 12]).encode()
    cursor = base64.urlsafe_b64encode(payload).decode().rstrip('=')

    result = decode_cursor(cursor)

    assert result == (datetime(2025, 2, 3, 4, 5, 6, tzinfo=UTC), 12)


@pytest.mark.parametrize(
    'cursor',
    [
        '%%%not-base64%%%',
        base64.urlsafe_b64encode(b'{bad json').decode().rstrip('='),
        base64.urlsafe_b64encode(json.dumps({'timestamp': 'now'}).encode())
        .decode()
        .rstrip('='),
        base64.urlsafe_b64encode(json.dumps(['now']).encode())
        .decode()
        .rstrip('='),
        base64.urlsafe_b64encode(json.dumps([12, 1]).encode())
        .decode()
        .rstrip('='),
        base64.urlsafe_b64encode(json.dumps(['not-a-date', 1]).encode())
        .decode()
        .rstrip('='),
        base64.urlsafe_b64encode(
            json.dumps(['2025-01-01T00:00:00', 0]).encode()
        )
        .decode()
        .rstrip('='),
        base64.urlsafe_b64encode(
            json.dumps(['2025-01-01T00:00:00', True]).encode()
        )
        .decode()
        .rstrip('='),
    ],
)
def test_decode_cursor_rejects_invalid_cursor_formats(cursor):
    invalid_cursor = cursor

    with pytest.raises(HTTPException) as error:
        decode_cursor(invalid_cursor)

    assert error.value.status_code == HTTPStatus.BAD_REQUEST


def test_pagination_dto_decodes_cursor_and_keeps_limit():
    decoded_cursor = (datetime(2025, 2, 3, 4, 5, 6, tzinfo=UTC), 12)
    cursor = encode_cursor(decoded_cursor)

    result = pagination_dto(cursor, limit=25)

    assert result == PaginationDTO(cursor=decoded_cursor, limit=25)


def test_pagination_dto_accepts_missing_cursor():
    cursor = None

    result = pagination_dto(cursor, limit=15)

    assert result == PaginationDTO(cursor=None, limit=15)
