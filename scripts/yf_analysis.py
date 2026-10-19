#!/usr/bin/env python3
"""Study YF (Y on fresh worlds): the registered analysis is the one of study Y (scripts/y_analysis.py, unchanged) applied to the YF protocol and ledger.

  python3 scripts/yf_analysis.py     # -> experiments/results/yf_summary.json

Claims YF1 (= Y1, availability), YF3 (= Y3, audit) and YF4 (= Y4, at most 2 stations) as registered in experiments/PREREGISTRATION_YF.md; Y2 (no clean bay) is not
part of YF (no Y-c runs), so the Y-c block of the output is empty and must be ignored.  The design masks of the selected worlds are the ones of the candidates
(experiments/campaign_yf_candidates_design_fire_masks.json), filtered to the selected worlds: nothing is rendered twice.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import y_analysis as ya  # noqa: E402
from scripts.x_analysis import perceivable_from_masks  # noqa: E402

RES = ROOT / 'experiments/results'
PROTO = ROOT / 'experiments/campaign_yf_protocol.json'
MASKS = ROOT / 'experiments/campaign_yf_candidates_design_fire_masks.json'
LEDGER = RES / 'campaign_YF_ledger.jsonl'


def selected_masks(protocol: dict, masks: list) -> list:
    worlds = set(protocol['yf']['selected'])
    keep = {w + s for w in worlds for s in ('', 'L', 'R')}
    return [m for m in masks if m['key'] in keep]


def main():
    proto = json.loads(PROTO.read_text())
    rows = [json.loads(x) for x in LEDGER.read_text().splitlines() if x.strip()]
    out = ya.analyse(proto, rows, perceivable_from_masks(selected_masks(proto, json.loads(MASKS.read_text()))))
    out['registered'] = 'experiments/PREREGISTRATION_YF.md'
    out['note'] = 'Y2 (the Y-c block) is not part of YF: no Y-c runs'
    (RES / 'yf_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'trials'}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
