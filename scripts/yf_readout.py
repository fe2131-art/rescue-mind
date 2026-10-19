#!/usr/bin/env python3
"""Study YF readout of the saved model outputs (post hoc, descriptive; I-43).  NOT a registered analysis.  Same reading as scripts/y_readout.py, on the YF ledger and summary:
the hazard probability of the first check at the steered station and the largest probability behind each recorded refusal, against the thresholds in force (0.05; 0.01 under
scrutiny).  It gives the cause class of every run that was not as designed and of the one run that visited four stations.

  python3 scripts/yf_readout.py [--runs outputs/runs]      # -> experiments/results/yf_readout.json
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import y_readout as yr  # noqa: E402

RES = ROOT / 'experiments/results'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', default=str(ROOT / 'outputs/runs'))
    a = ap.parse_args()
    summary = json.loads((RES / 'yf_summary.json').read_text(encoding='utf8'))
    rows = yr.readout(RES / 'campaign_YF_ledger.jsonl', Path(a.runs), summary)
    (RES / 'yf_readout.json').write_text(json.dumps({'note': 'post hoc, descriptive (I-43); not a registered analysis', 'rows': rows}, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    for r in rows:
        if not r['as_designed'] or r['arm'] == 'scrutiny_hc' or r['unsafe_delivery']:
            print(r['trial_id'], r['world'], r['arm'], r['expected'], '->', r['observed'], 'haz', r['hazard_refusals'], 'caut', r['caution_refusals'],
                  'last', r.get('last_check_station'), r.get('last_check_hazard_prob'))


if __name__ == '__main__':
    main()
