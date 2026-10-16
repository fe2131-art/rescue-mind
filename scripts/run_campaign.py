#!/usr/bin/env python3
"""Execute the pre-registered 30-trial study (experiments/v23_locked_protocol.json).

Each trial is one full, fresh Gazebo + bridge + guard + local VLM stack run through
scripts/v32_orchestrate.py, in the locked order. Scene truth is used ONLY here
for scoring; it is never passed to the mission or to the VLM. Results append to a
JSONL ledger so an interrupted campaign can resume without re-running trials.
"""
from __future__ import annotations
import argparse
import json
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITEM_JA = {'water': '飲料水', 'medicine': '医療物資'}


def load_protocol(path=None):
    p = json.loads(Path(path or ROOT/'experiments/v23_locked_protocol.json').read_text(encoding='utf8'))
    if p['planned_n'] != len(p['trials']):
        raise SystemExit('protocol corrupted')
    return sorted(p['trials'], key=lambda t: t['order'])


def latest_run_after(before: set[str]) -> Path | None:
    runs = ROOT/'outputs'/'runs'
    new = [d for d in runs.iterdir() if d.is_dir() and d.name not in before] if runs.is_dir() else []
    return max(new, key=lambda d: d.stat().st_mtime) if new else None


def summarize(trial: dict, run_dir: Path | None, rc: int, wall_s: float) -> dict:
    row = {'trial_id': trial['id'], 'order': trial['order'], 'scene': trial['scene'],
           'expected_supply': trial['expected'], 'truth_supply': trial['truth_supply'],
           'expected_action': trial['expected_action'], 'orchestrator_exit': rc,
           'wall_s': round(wall_s, 1), 'run_id': run_dir.name if run_dir else None}
    if run_dir is None:
        row.update(state='NO_RUN_DIR', observed_action='FAILED')
        return row
    try:
        result = json.loads((run_dir/'stack_result.json').read_text(encoding='utf8'))
    except (OSError, ValueError):
        result = {'state': 'MISSING_RESULT'}
    row['state'] = result.get('state')
    row['error'] = result.get('error') or result.get('negative_evidence_failure')
    try:
        mission = json.loads((run_dir/'mission.json').read_text(encoding='utf8'))
    except (OSError, ValueError):
        mission = {}
    cp = mission.get('checkpoint') or {}
    decision = cp.get('decision') or {}
    calls = cp.get('model_calls') or {}
    row['vlm_first'] = decision.get('first_supply')
    row['vlm_second'] = decision.get('second_supply')
    row['vlm_reason'] = decision.get('reason')
    row['vlm_latency_s'] = None
    ev = {e.get('stage'): e for e in mission.get('events', [])}
    if 'checkpoint_frame' in ev and 'checkpoint_decision' in ev:
        row['vlm_latency_s'] = round(ev['checkpoint_decision']['t_wall_s'] - ev['checkpoint_frame']['t_wall_s'], 2)
    row['image_sha256'] = cp.get('image_sha256')
    row['models'] = sorted({c.get('model') for c in calls.values() if isinstance(c, dict)})
    rec = mission.get('recovery') or {}
    row['recovery_searched'] = bool(rec)
    row['final_station'] = mission.get('checkpoint_station')
    if rec:
        fd = (rec.get('first_checkpoint') or {}).get('decision') or {}
        row['first_vlm'] = [fd.get('first_supply'), fd.get('second_supply')]
    row['intent_backend'] = (mission.get('intent_gate') or {}).get('backend')
    row['intent_item'] = (mission.get('intent') or {}).get('item')
    row['explanations'] = [e.get('text_ja') for e in mission.get('events', []) if e.get('stage', '').endswith('checkpoint_explanation')]
    if row['state'] == 'COMPLETED':
        row['observed_action'] = 'ALLOW_AFTER_SEARCH' if rec else 'ALLOW'
    elif row['state'] == 'COMPLETED_EXPECTED_DENIAL':
        row['observed_action'] = ('DENY_HAZARD' if decision.get('reason') == 'visible_hazard_at_checkpoint' and not rec
                                  else 'DENY')
    elif decision.get('allow') is False:
        row['observed_action'] = 'DENY_UNVERIFIED'
    else:
        row['observed_action'] = 'FAILED'
    expected = trial['expected_action']
    want = {'DELIVER_AFTER_SEARCH': 'ALLOW_AFTER_SEARCH'}.get(expected, expected)
    row['correct'] = row['observed_action'] == want
    return row


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ledger', default=str(ROOT/'experiments/results/campaign_ledger.jsonl'))
    ap.add_argument('--local-mode', choices=['single', 'dual'], default='single')
    ap.add_argument('--only', nargs='*', help='trial IDs to run (default: all not yet in ledger)')
    ap.add_argument('--no-rosbag', action='store_true')
    ap.add_argument('--retries', type=int, default=1, help='re-run a trial whose stack FAILED for infra reasons')
    ap.add_argument('--protocol', default=None, help='protocol JSON (default: v23 locked protocol)')
    ap.add_argument('stack_args', nargs='*', help='extra orchestrator flags after "--", e.g. -- --recovery --explain')
    a = ap.parse_args(argv)
    ledger = Path(a.ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if ledger.is_file():
        for line in ledger.read_text(encoding='utf8').splitlines():
            r = json.loads(line)
            if r.get('local_mode', 'single') == a.local_mode and r.get('final', True):
                done.add(r['trial_id'])
    for trial in load_protocol(a.protocol):
        if a.only and trial['id'] not in a.only:
            continue
        if not a.only and trial['id'] in done:
            continue
        for attempt in range(a.retries + 1):
            runs = ROOT/'outputs'/'runs'
            before = {d.name for d in runs.iterdir()} if runs.is_dir() else set()
            cmd = [sys.executable, str(ROOT/'scripts/v32_orchestrate.py'), '--run', '--scenario', 'live',
                   '--scene', trial['scene'], '--local-mode', a.local_mode,
                   '--instruction', trial.get('instruction') or f"避難所Bに{ITEM_JA[trial['expected']]}を届けて"]
            for key, flag in (('lighting', '--lighting'), ('hazard_at', '--hazard-at'), ('distractor_at', '--distractor-at')):
                if trial.get(key) and not (key == 'lighting' and trial[key] == 'default'):
                    cmd += [flag, trial[key]]
            cmd += a.stack_args
            if not a.no_rosbag:
                cmd.append('--capture-rosbag')
            started = time.monotonic()
            proc = subprocess.Popen(cmd, cwd=ROOT)
            try:
                rc = proc.wait()
            except KeyboardInterrupt:
                # Never SIGKILL the orchestrator: forward SIGINT so it tears its stack down.
                proc.send_signal(signal.SIGINT)
                proc.wait(timeout=120)
                raise
            row = summarize(trial, latest_run_after(before), rc, time.monotonic() - started)
            row['local_mode'] = a.local_mode
            row['stack_args'] = a.stack_args
            row['instruction'] = trial.get('instruction')
            row['attempt'] = attempt + 1
            infra_failure = row['observed_action'] == 'FAILED' and row.get('vlm_reason') is None
            row['final'] = not (infra_failure and attempt < a.retries)
            with ledger.open('a', encoding='utf8') as f:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
            print(json.dumps(row, ensure_ascii=False), flush=True)
            if row['final']:
                break
            time.sleep(3)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
