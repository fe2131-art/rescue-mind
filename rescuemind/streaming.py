"""Strict SSE decoder for OpenAI-compatible streaming chat completions.

Offline-contract-tested only; external API streaming needs a credentialed smoke test.
"""
from __future__ import annotations
import json
from typing import Iterable

class StreamError(ValueError):
    pass


def accumulate_chat_chunks(lines: Iterable[bytes | str], max_bytes: int = 2_000_000) -> dict:
    """Consume `data: {...}` SSE lines; require [DONE] and a complete answer.

    `usage` is optionally copied, but only emitted *content*, never reasoning,
    is used as the JSON classification. Server model id must remain stable.
    """
    model = None
    pieces: list[str] = []
    usage = {}
    count = 0
    done = False
    seen_stop = False
    for raw in lines:
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8', 'strict')
        count += len(raw.encode('utf-8'))
        if count > max_bytes:
            raise StreamError('SSE response larger than cap')
        line = raw.strip()
        if not line or line.startswith(':') or line.startswith('event:'):
            continue
        if not line.startswith('data:'):
            raise StreamError('Unexpected SSE line')
        data = line[5:].strip()
        if data == '[DONE]':
            done = True
            break
        try:
            event = json.loads(data)
        except (ValueError, TypeError) as exc:
            raise StreamError('Non-JSON SSE data') from exc
        if not isinstance(event, dict) or event.get('error'):
            raise StreamError('SSE API error')
        event_model = event.get('model')
        if event_model:
            if model and model != event_model:
                raise StreamError('Changed model mid-stream')
            model = event_model
        if isinstance(event.get('usage'), dict):
            usage = event['usage']
        choices = event.get('choices') or []
        if not isinstance(choices, list):
            raise StreamError('Malformed SSE choices')
        for ch in choices:
            if ch.get('index', 0) != 0:
                continue
            delta = ch.get('delta') or {}
            content = delta.get('content')
            if isinstance(content, str):
                pieces.append(content)
            if ch.get('finish_reason') == 'stop':
                seen_stop = True
    if not done or not seen_stop or not model or not pieces:
        raise StreamError('Incomplete SSE response: no DONE/stop/model/content')
    return {'model': model, 'choices': [{'message': {'content': ''.join(pieces)}}], 'usage': usage}
