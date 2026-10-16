#!/usr/bin/env python3
"""Was the fire actually in the camera view when the checkpoint frame was taken? (campaign E registration)

  python3 scripts/fire_visibility_check.py experiments/results/campaign_E_ledger.jsonl [--protocol experiments/campaign_e_protocol.json]

For every final trial with a fire, take the Gazebo ground-truth pose at the moment the checkpoint frame
at the burning station was captured and classify the fire as visible / hidden / ambiguous with the same
geometry as the T1 labels (rescuemind.robust_scenes.hazard_visibility).
"""
from __future__ import annotations
import argparse
import bisect
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind.robust_scenes import hazard_visibility, hazard_xy  # noqa: E402


def pose_at(run_dir: Path, unix_ns: int):
    ts, poses = [], []
    for line in (run_dir / 'independent_ros_topics.jsonl').read_text().splitlines():
        r = json.loads(line)
        if r.get('kind') == 'ground_truth':
            yaw = math.atan2(2 * (r['qw'] * r['qz'] + r['qx'] * r['qy']), 1 - 2 * (r['qy'] ** 2 + r['qz'] ** 2))
            ts.append(r['wall_unix_ns']); poses.append((r['x'], r['y'], yaw))
    i = min(max(bisect.bisect_left(ts, unix_ns), 0), len(ts) - 1)
    if i and abs(ts[i - 1] - unix_ns) < abs(ts[i] - unix_ns):
        i -= 1
    return poses[i], abs(ts[i] - unix_ns) / 1e9


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ledger')
    ap.add_argument('--protocol', default=None)
    a = ap.parse_args()
    proto = {}
    if a.protocol:
        proto = {t['id']: t for t in json.loads(Path(a.protocol).read_text())['trials']}
    out = []
    for line in Path(a.ledger).read_text().splitlines():
        r = json.loads(line)
        if not r.get('final', True) or not r.get('run_id'):
            continue
        t = proto.get(r['trial_id'], {})
        spec = t.get('world_spec') or {}
        fire_at = spec.get('hazard_at') or t.get('hazard_at')
        if not fire_at:
            continue
        geom = tuple(spec.get('hazard_geom') or (0.75, 0.5))
        run = ROOT / 'outputs/runs' / r['run_id']
        m = json.loads((run / 'mission.json').read_text())
        final_station = m.get('checkpoint_station')
        stage = 'checkpoint_frame' if final_station == fire_at else 'recovery_checkpoint_frame'
        ev = next((e for e in m['events'] if e.get('stage') == stage), None)
        if ev is None:
            out.append({'trial_id': r['trial_id'], 'fire_at': fire_at, 'visibility': 'not_checked_at_burning_station'})
            continue
        (x, y, yaw), dt = pose_at(run, m['mission_start_unix_ns'] + int(ev['t_wall_s'] * 1e9))
        vis = hazard_visibility(fire_at, fire_at, (x, y), yaw, hazard_xy(fire_at, *geom))
        out.append({'trial_id': r['trial_id'], 'run_id': r['run_id'], 'fire_at': fire_at, 'stage': stage,
                    'pose': [round(x, 3), round(y, 3), round(yaw, 3)], 'pose_dt_s': round(dt, 3),
                    'visibility': vis, 'observed_action': r['observed_action'], 'correct': r['correct']})
    for o in out:
        print(json.dumps(o))
    dest = Path(a.ledger).with_name(Path(a.ledger).stem + '_fire_visibility.json')
    dest.write_text(json.dumps(out, indent=1) + '\n')
    print('saved', dest)


if __name__ == '__main__':
    main()
