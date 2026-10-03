import base64
import json
from datetime import UTC, datetime
from http import HTTPStatus

from fastapi import HTTPException
from pydantic import BaseModel

from project.dtos.page import CursorPage, PaginationDTO


class PageSchema[T](BaseModel):
    items: list[T]
    limit: int
    more: bool
    cursor: str | None


def encode_cursor(cursor: tuple[datetime, int] | None) -> str | None:
    if cursor is None:
        return None
    payload = json.dumps(
        [cursor[0].isoformat(), cursor[1]], separators=(',', ':')
    )
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')


def decode_cursor(cursor: str | None) -> tuple[datetime, int] | None:
    if cursor is None:
        return None
    try:
        padded = cursor + '=' * (-len(cursor) % 4)
        value = json.loads(
            base64.b64decode(padded, altchars=b'-_', validate=True)
        )
        expect_len = 2

        if not isinstance(value, list) or len(value) != expect_len:
            raise ValueError('invalid cursor payload')

        ts_str, item_id = value

        if (
            not isinstance(ts_str, str)
            or type(item_id) is not int
            or item_id < 1
        ):
            raise ValueError('invalid cursor payload')
        timestamp = datetime.fromisoformat(ts_str)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        return timestamp, item_id

    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail='Invalid cursor'
        ) from error


def page_schema[T](page: CursorPage[T]) -> PageSchema[T]:
    return PageSchema(
        items=page.items,
        limit=page.pagination.limit,
        more=page.pagination.more,
        cursor=encode_cursor(page.pagination.cursor),
    )


def pagination_dto(cursor: str | None, limit: int) -> PaginationDTO:
    return PaginationDTO(cursor=decode_cursor(cursor), limit=limit)
