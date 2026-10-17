#!/usr/bin/env python3
"""Copy the small part of outputs/runs/<run_id>/ that figures read into experiments/evidence/runs/<run_id>/,
and export the per-run timing fields behind tab_timing to experiments/results/timing_runs.json.

  python3 scripts/export_run_evidence.py

Copied per run: mission.json, stack_result.json, top-level *.jpg (check images).  No rosbag, log or video.
Absolute paths in the copied JSON are made repo-relative (originals are untouched).
"""
from __future__ import annotations
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_paths import FULL, COMMITTED  # noqa: E402

RUNS = {
    '9d73663832c94f16': 'fig_lookaround; operator_report_hidden_fire',
    'b4fcd9d164444db7': 'operator_report_recover',
    '4e5461e9e58542c4': 'fig_h_case (M0)',
    '54c52d274181424a': 'fig_h_case (M2); operator_report_memory_case',
}
PHASE_STAGES = ['supply_station', 'camera_aim_aligned', 'checkpoint_stationary_verified', 'checkpoint_frame',
                'checkpoint_decision', 'checkpoint_explanation', 'shelter_approach']
ABS = re.compile(r'/home/[^/\s"]+/work/rescue-mind/?')


def scrub(text: str) -> str:
    text = ABS.sub('', text)
    return re.sub(r'/home/[^/\s"]+', '~', text)


def main():
    for rid in RUNS:
        src, dst = FULL / rid, COMMITTED / rid
        dst.mkdir(parents=True, exist_ok=True)
        for f in ['mission.json', 'stack_result.json', *sorted(p.name for p in src.glob('*.jpg'))]:
            if not (src / f).is_file():
                continue
            if f.endswith('.json'):
                (dst / f).write_text(scrub((src / f).read_text(encoding='utf8')), encoding='utf8')
            else:
                shutil.copy2(src / f, dst / f)
    # timing: delivered (ALLOW) missions of campaigns D and E, stage -> wall time
    out = {}
    for name in ('campaign_D_ledger.jsonl', 'campaign_E_ledger.jsonl'):
        f = ROOT / 'experiments/results' / name
        if not f.is_file():
            continue
        for line in f.read_text().splitlines():
            r = json.loads(line)
            mf = FULL / r['run_id'] / 'mission.json'
            if r['observed_action'] != 'ALLOW' or not mf.is_file():
                continue
            ev = {e['stage']: e.get('t_wall_s') for e in json.loads(mf.read_text())['events']}
            out[r['run_id']] = {k: ev[k] for k in PHASE_STAGES if k in ev}
    (ROOT / 'experiments/results/timing_runs.json').write_text(json.dumps(out, indent=0, sort_keys=True) + '\n')
    print(f'{len(RUNS)} runs -> {COMMITTED}; {len(out)} timing runs')


if __name__ == '__main__':
    main()
