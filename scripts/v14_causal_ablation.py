#!/usr/bin/env python3
"""Synthetic/counterfactual policy ablation, NOT an evaluation of real VLMs.

All inputs are hand-constructed.  Measured outputs are decisions made by the
software policy, not VLM classification accuracy, robot success, or safety.
"""
from __future__ import annotations
import csv
import json
from copy import deepcopy
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.checkpoint import decide_checkpoint


def cases():
    j={'real_model':True,'model':'jev-1.14.0', 'supply':'water',
       'supply_confidence':.92, 'supply_present_probability':.94,
       'hazard_probability':.08,'scene':'clear'}
    q={'real_model':True,'model':'qwen3.8-omni-flash', 'supply':'water', 'scene':'clear'}
    variants=[
        ('correct_observation',{}, {}, True),
        ('jev_wrong_supply',{'supply':'medicine'},{},False),
        ('qwen_wrong_supply',{}, {'supply':'medicine'},False),
        ('both_wrong_supply',{'supply':'medicine'},{'supply':'medicine'},False),
        ('jev_hazard',{'hazard_probability':.89},{},False),
        ('jev_scene_hazard',{'scene':'hazard'},{},False),
        ('qwen_scene_hazard',{}, {'scene':'hazard'},False),
        ('jev_low_confidence',{'supply_confidence':.20},{},False),
        ('jev_low_presence',{'supply_present_probability':.15},{},False),
        ('jev_invalid_probability',{'hazard_probability':float('nan')},{},False),
        ('jev_model_mismatch',{'model':'jev-latest'},{},False),
        ('qwen_model_mismatch',{}, {'model':'old-vlm'},False),
    ]
    for name,jdelta,qdelta,safe in variants:
        jj=deepcopy(j);qq=deepcopy(q);jj.update(jdelta);qq.update(qdelta)
        yield name,jj,qq,safe


def evaluate():
    rows=[]
    for scenario,j,q,is_permitted in cases():
        # Naive baselines deliberately ignore data the dual policy checks;
        # they illustrate why safety gating matters, not model accuracy.
        jev_label_only=j['supply']=='water'
        qwen_label_only=q['supply']=='water'
        fused=decide_checkpoint('water',j,q)
        rows.append({'scenario':scenario,'oracle_permission_synthetic':is_permitted,
                     'jev_label_only':jev_label_only,'qwen_label_only':qwen_label_only,
                     'dual_safety_gate':fused.allow,'dual_reason':fused.reason})
    totals={}
    for method in ('jev_label_only','qwen_label_only','dual_safety_gate'):
        totals[method]={
            'false_approvals':sum(r[method] and not r['oracle_permission_synthetic'] for r in rows),
            'true_approvals':sum(r[method] and r['oracle_permission_synthetic'] for r in rows),
            'false_rejections':sum(not r[method] and r['oracle_permission_synthetic'] for r in rows),
        }
    return rows,totals


def main():
    rows,totals=evaluate()
    dest=ROOT/'outputs/release'
    dest.mkdir(parents=True,exist_ok=True)
    with (dest/'v14_synthetic_ablation.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={'kind':'HAND_CONSTRUCTED_COUNTERFACTUAL_POLICY_ABLATION',
             'not_evidence_of':'real model accuracy, Gazebo robot execution, or deployed safety',
             'number_of_synthetic_cases':len(rows),'policy_comparison':totals}
    (dest/'v14_synthetic_ablation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__ == '__main__':main()
