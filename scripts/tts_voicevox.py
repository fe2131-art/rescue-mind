#!/usr/bin/env python3
"""I-07: Japanese narration via a local VOICEVOX engine (docker, 127.0.0.1:50021).

  docker run --rm -d -p 127.0.0.1:50021:50021 voicevox/voicevox_engine:cpu-latest

Synthesised clips are cached by (speaker, text) hash under outputs/narration/.
Credit required in the video/description: "VOICEVOX:<speaker name>".
"""
from __future__ import annotations
import hashlib
import json
import urllib.parse
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'outputs/narration'
ENGINE = 'http://127.0.0.1:50021'


def speakers() -> list:
    with urllib.request.urlopen(ENGINE + '/speakers', timeout=10) as f:
        return json.load(f)


def synthesize(text: str, speaker: int, *, speed: float = 1.12) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f'{speaker}|{speed}|{text}'.encode()).hexdigest()[:16]
    out = CACHE / f'{key}.wav'
    if out.is_file():
        return out
    q = urllib.parse.urlencode({'text': text, 'speaker': speaker})
    req = urllib.request.Request(f'{ENGINE}/audio_query?{q}', method='POST')
    with urllib.request.urlopen(req, timeout=60) as f:
        query = json.load(f)
    query['speedScale'] = speed
    query['prePhonemeLength'] = 0.05
    query['postPhonemeLength'] = 0.15
    req = urllib.request.Request(f'{ENGINE}/synthesis?speaker={speaker}', data=json.dumps(query).encode(),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=120) as f:
        out.write_bytes(f.read())
    return out


def duration(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


if __name__ == '__main__':
    for sp in speakers():
        print(sp['name'], [(s['name'], s['id']) for s in sp['styles']])
