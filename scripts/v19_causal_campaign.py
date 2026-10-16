#!/usr/bin/env python3
"""Deterministic synthetic chronological attack suite; no ROS/API/Gazebo calls."""
from __future__ import annotations
import json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from test_v19_causal_evidence import fixtures,ST,SH
from rescuemind.causal_evidence import audit_causal,CausalEvidenceError

SCENARIOS={
    'valid':True,
    'decision_early':False,
    'decision_deny':False,
    'anchor_missing':False,
    'premature_movement':False,
    'premature_shelter':False,
    'no_post_shelter':False,
    'missing_dwell':False,
    'backward_clock':False,
    'run_mismatch':False,
}

def main():
    rows=[]
    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp)
        for scenario,expected in SCENARIOS.items():
            mission,ros=fixtures(folder,scenario)
            try:
                result=audit_causal(mission,ros,station=ST,shelter=SH)
                allowed=bool(result['pass']); reason='accepted'
            except CausalEvidenceError as exc:
                allowed=False;reason=str(exc)
            rows.append({'scenario':scenario,'expected_allow':expected,
                         'observed_allow':allowed,'matched':expected==allowed,'reason':reason})
    outcome={'suite':'SYNTHETIC_ONLY_NOT_REAL_ROS_OR_VLM','total':len(rows),
             'matched':sum(r['matched'] for r in rows),'cases':rows}
    p=ROOT/'verification/v19/v19_synthetic_chronology_campaign.json'
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(outcome,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(outcome,ensure_ascii=False,indent=2))
    return 0 if outcome['matched']==outcome['total'] else 1

if __name__=='__main__':raise SystemExit(main())
