#!/usr/bin/env python3
"""Gating logic of scripts/finalize_results.sh (pure stdlib, no side effects).  Prints one line: 'OK <note>' or 'SKIP <reason>'.
Exit code is always 0.  ALLOW_PARTIAL=1 turns an incomplete-count SKIP into OK (missing files still SKIP).

  finalize_gate.py ledger  LEDGER PROTOCOL [REQUIRED_FILE ...]   planned_n final rows in LEDGER (rows without 'final' count as final)
  finalize_gate.py devsets LABELS_JSONL TAG [TAG ...]             experiments/results/devset_<TAG>.json each present, n > 0 and covering every
                                                                  image of LABELS_JSONL (when that file exists; else only n > 0)
  finalize_gate.py q                                               study Q: scripts/q_analysis.py, the preregistration, the sample and a full score file
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
PARTIAL = os.environ.get('ALLOW_PARTIAL', '0') == '1'


def out(ok, msg):
    print(('OK ' if ok else 'SKIP ') + msg)
    sys.exit(0)


def jl(p):
    return [json.loads(x) for x in Path(p).read_text(encoding='utf8').splitlines() if x.strip()]


def ledger(argv):
    led, proto, req = ROOT / argv[0], ROOT / argv[1], argv[2:]
    missing = [r for r in [argv[0], argv[1], *req] if not (ROOT / r).is_file()]
    if missing:
        out(False, 'missing ' + ', '.join(missing))
    planned = json.loads(proto.read_text(encoding='utf8'))['planned_n']
    have = sum(1 for r in jl(led) if r.get('final', True))
    if have < planned and not PARTIAL:
        out(False, f'incomplete {have}/{planned} final rows (ALLOW_PARTIAL=1 to force)')
    out(True, f'{have}/{planned} final rows')


def devsets(argv):
    labels, tags = ROOT / argv[0], argv[1:]
    want = None
    if labels.is_file():
        want = {r.get('image') or r.get('file') or r.get('name') for r in jl(labels)} - {None}
    notes = []
    for t in tags:
        f = RES / f'devset_{t}.json'
        if not f.is_file():
            out(False, f'missing devset_{t}.json')
        try:
            d = json.loads(f.read_text(encoding='utf8'))
        except Exception as e:  # noqa: BLE001
            out(False, f'devset_{t}.json unreadable ({e})')
        recs = d.get('records', [])
        if not recs:
            out(False, f'devset_{t}.json has no records')
        if want:
            got = {r.get('image') for r in recs}
            if len(want - got) and not PARTIAL:
                out(False, f'devset_{t}.json covers {len(want & got)}/{len(want)} images (ALLOW_PARTIAL=1 to force)')
        notes.append(f'{t}:{len(recs)}')
    out(True, ' '.join(notes))


def q(argv):
    need = ['scripts/q_analysis.py', 'experiments/PREREGISTRATION_Q.md', 'experiments/q_sample_final.json']
    missing = [r for r in need if not (ROOT / r).is_file()]
    sc = RES / 'q_scores_qwen9b_v35.jsonl'
    if not sc.is_file():
        missing.append('experiments/results/q_scores_qwen9b_v35.jsonl')
    if missing:
        out(False, 'study Q not merged/run (missing ' + ', '.join(missing) + ')')
    sample = json.loads((ROOT / need[2]).read_text(encoding='utf8'))
    n_want = len(sample.get('images', sample.get('items', sample))) if isinstance(sample, (dict, list)) else 0
    have = len(jl(sc))
    if n_want and have < n_want and not PARTIAL:
        out(False, f'incomplete {have}/{n_want} Q score rows (ALLOW_PARTIAL=1 to force)')
    out(True, f'{have}/{n_want} score rows')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    {'ledger': ledger, 'devsets': devsets, 'q': q}.get(cmd, lambda a: out(False, 'bad gate command'))(sys.argv[2:])
