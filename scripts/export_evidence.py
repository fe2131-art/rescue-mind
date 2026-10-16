#!/usr/bin/env python3
"""Copy a compact, auditable subset of each campaign run into the repository.

outputs/runs/<run_id>/ holds GBs (rosbag2 MCAP, logs).  For the public repo we keep,
per run: stack_result.json, mission.json, the exact checkpoint JPEG the VLM saw,
the rosbag metadata.yaml, and a 5 Hz down-sampled Gazebo ground-truth track.
Image SHA-256 in mission.json lets anyone verify the JPEG is the one judged.
"""
from __future__ import annotations
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / 'outputs/runs'
DEST = ROOT / 'experiments/results/evidence'


def scrub(text: str) -> str:
    import re
    return re.sub(r'/home/[^/\s"\']+', '/home/<user>', text.replace(str(ROOT), '<repo>'))


def export(run_id: str) -> bool:
    src = RUNS / run_id
    if not (src / 'stack_result.json').is_file():
        return False
    out = DEST / run_id
    out.mkdir(parents=True, exist_ok=True)
    for name in ('stack_result.json', 'mission.json'):
        if (src / name).is_file():
            # strip host paths (they contain the local user name) before publishing
            text = (src / name).read_text(encoding='utf8').replace(str(ROOT), '<repo>')
            (out / name).write_text(scrub(text), encoding='utf8')
    if (src / 'checkpoint.jpg').is_file():
        shutil.copy2(src / 'checkpoint.jpg', out / 'checkpoint.jpg')
    meta = src / 'rosbag2' / 'metadata.yaml'
    if meta.is_file():
        (out / 'rosbag2_metadata.yaml').write_text(scrub(meta.read_text(encoding='utf8')), encoding='utf8')
    track, last = [], None
    tele = src / 'independent_ros_topics.jsonl'
    if tele.is_file():
        for line in tele.read_text(encoding='utf8').splitlines():
            r = json.loads(line)
            if r.get('kind') == 'ground_truth' and (last is None or r['ros_stamp_ns'] - last >= 200_000_000):
                track.append([round(r['x'], 3), round(r['y'], 3)])
                last = r['ros_stamp_ns']
    (out / 'ground_truth_xy.json').write_text(json.dumps(track) + '\n')
    return True


def main(argv=None):
    ids = (argv if argv is not None else sys.argv[1:])
    if not ids:
        ledger = ROOT / 'experiments/results/campaign_ledger.jsonl'
        ids = [json.loads(x)['run_id'] for x in ledger.read_text().splitlines() if json.loads(x).get('run_id')]
    n = sum(export(i) for i in ids)
    print(f'exported {n} runs to {DEST}')


if __name__ == '__main__':
    main()
