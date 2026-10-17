"""Where the per-run records behind a few paper figures live.

`outputs/runs/<run_id>/` is Git-ignored (it also holds rosbags and logs).  The small subset that figures
and tables actually read (mission.json, stack_result.json, the check images) is committed under
`experiments/evidence/runs/<run_id>/`; `scripts/export_run_evidence.py` copies it from `outputs/runs/`.
`run_dir()` prefers the full record and falls back to the committed copy.  Set RESCUEMIND_RUNS_DIR to
point at another full-record directory (e.g. a non-existent one to test the fallback).
"""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FULL = Path(os.environ['RESCUEMIND_RUNS_DIR']) if os.environ.get('RESCUEMIND_RUNS_DIR') else ROOT / 'outputs/runs'
COMMITTED = ROOT / 'experiments/evidence/runs'


def run_dir(run_id: str, need: str = 'mission.json') -> Path:
    """Directory holding run `run_id`: the full record if it has `need`, else the committed excerpt."""
    for base in (FULL, COMMITTED):
        d = base / run_id
        if (d / need).is_file():
            return d
    return FULL / run_id   # neither exists: callers test for their files and report it
