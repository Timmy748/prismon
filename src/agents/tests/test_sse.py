import json

import pytest

from agents.utils.sse import format_sse


def test_format_sse_encodes_unicode_as_compact_json():
    result = format_sse('token', 'olá 🌎')

    assert result == 'event: token\ndata: "olá 🌎"\n\n'


def test_format_sse_serializes_schema_payload():
    result = format_sse('done', {'id': 7, 'text': 'resposta'})

    assert json.loads(result.split('data: ', maxsplit=1)[1]) == {
        'id': 7,
        'text': 'resposta',
    }


@pytest.mark.parametrize('event', ['', 'bad\nevent', 'bad\revent'])
def test_format_sse_rejects_empty_or_multiline_event_name(event):
    with pytest.raises(ValueError, match='event name'):
        format_sse(event, {})
