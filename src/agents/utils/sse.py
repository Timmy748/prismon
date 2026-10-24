import json
from typing import Any

from fastapi.encoders import jsonable_encoder

from core.logs import get_logger

logger = get_logger(__name__)


def format_sse(event: str, data: Any) -> str:
    if not event or any(char in event for char in '\r\n'):
        logger.warning('Rejected invalid server-sent event name')
        raise ValueError('SSE event name must be non-empty and single-line')

    encoded_data = json.dumps(
        jsonable_encoder(data), ensure_ascii=False, separators=(',', ':')
    )
    return f'event: {event}\ndata: {encoded_data}\n\n'
