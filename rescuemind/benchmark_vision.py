"""Run an auditable selective-decision benchmark on labeled *real* API records.

No demo/mock inputs are silently scored as model achievements.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from statistics import mean
from .safety import decide
from .experiment_stats import validate_unique, enrich

LABELS = {'water','medicine','other'}
SCENES = {'clear','hazard','unknown'}


def validate_record(row:dict, require_real:bool=True)->None:
    if not isinstance(row,dict) or not {'id','truth','expected','supply','corridor'} <= row.keys():
        raise ValueError('Missing benchmark record fields')
    truth=row['truth']
    if row['expected'] not in {'water','medicine'} or truth.get('supply') not in LABELS or truth.get('scene') not in SCENES:
        raise ValueError('Invalid truth labels')
    for place in ('supply','corridor'):
        for model in ('jev','qwen'):
            if not isinstance(row[place].get(model),dict):
                raise ValueError(f'Missing {place}.{model}')
            if require_real and not row[place][model].get('real_model'):
                raise ValueError('Only captured real-model records can be benchmarked')
    if require_real and row.get('provenance') != 'live_api_capture':
        raise ValueError('No live API capture provenance; demo values are not benchmark evidence')


def aggregate(records:list[dict], require_real:bool=True)->dict:
    if not records:
        raise ValueError('No benchmark records supplied')
    validate_unique(records)
    modes = ('jev_only','qwen_only','fusion')
    scores = {m: {'approved': 0,'correct_approved': 0,'unsafe_approved': 0,'false_denial': 0} for m in modes}
    for row in records:
        validate_record(row,require_real)
        expected=row['expected']; t=row['truth']; ground_ok=t['supply']==expected and t['scene']=='clear'
        j={**row['supply']['jev'], 'scene':row['corridor']['jev']['scene'], 'hazard_probability':row['corridor']['jev']['hazard_probability']}
        q={**row['supply']['qwen'], 'scene':row['corridor']['qwen']['scene']}
        jev_ok=(j.get('supply')==expected and j.get('scene')=='clear' and
                j.get('supply_present_probability',0)>=.8 and j.get('supply_confidence',0)>=.65 and
                j.get('hazard_probability',1)<=.20)
        qwen_ok=q.get('supply')==expected and q.get('scene')=='clear'
        approved={'jev_only':jev_ok,'qwen_only':qwen_ok,'fusion':decide(expected,j,q).allow}
        for mode in modes:
            sc=scores[mode]
            if approved[mode]:
                sc['approved']+=1
                sc['correct_approved']+=int(ground_ok)
                sc['unsafe_approved']+=int(not ground_ok)
            else:
                sc['false_denial']+=int(ground_ok)
    n=len(records)
    out={}
    for mode,d in scores.items():
        approvals=d['approved']
        out[mode]={**d, 'n':n,'coverage':round(approvals/n,4),
                   'precision_when_approved':round(d['correct_approved']/approvals,4) if approvals else None,
                   'unsafe_approval_rate_over_all_cases':round(d['unsafe_approved']/n,4),
                   'false_denial_rate_over_all_cases':round(d['false_denial']/n,4)}
    enrich(out)
    return {'method':'Wilson 95% descriptive intervals; assumes independent cases; no performance guarantee',
            'n_unique_cases':n,'results':out}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--records',required=True,help='JSONL saved by record_real_case.py')
    parser.add_argument('--output',default='outputs/real_benchmark.json')
    a=parser.parse_args()
    lines=[x for x in Path(a.records).read_text(encoding='utf-8').splitlines() if x.strip()]
    records=[json.loads(x) for x in lines]
    result=aggregate(records)
    p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
