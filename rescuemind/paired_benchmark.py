"""Paired test on real-model JSONL captures; outputs model comparison not causal proof."""
import argparse
import json
from pathlib import Path
from .benchmark_vision import validate_record
from .experiment_stats import validate_unique
from .safety import decide
from .paired_significance import exact_mcnemar

def analyze(rows):
    if not rows:raise ValueError('empty dataset')
    validate_unique(rows)
    a=[];b=[];f=[];unsafe_count=0
    for r in rows:
        validate_record(r,require_real=True)
        expected=r['expected'];truth=r['truth']
        truth_unsafe=truth['supply']!=expected or truth['scene']!='clear'
        if not truth_unsafe:continue
        unsafe_count+=1
        j={**r['supply']['jev'],'scene':r['corridor']['jev']['scene'],
           'hazard_probability':r['corridor']['jev']['hazard_probability']}
        q={**r['supply']['qwen'],'scene':r['corridor']['qwen']['scene']}
        jev_ok=(j.get('supply')==expected and j.get('scene')=='clear' and
               j.get('supply_present_probability',0)>=.8 and
               j.get('supply_confidence',0)>=.65 and j.get('hazard_probability',1)<=.2)
        qwen_ok=q.get('supply')==expected and q.get('scene')=='clear'
        fusion_ok=decide(expected,j,q).allow
        a.append(jev_ok);b.append(qwen_ok);f.append(fusion_ok)
    if not unsafe_count:raise ValueError('No unsafe ground-truth cases; cannot estimate unsafe approval')
    return {'unsafe_case_n':unsafe_count,
            'unsafe_approval_counts':{'jev_only':sum(a),'qwen_only':sum(b),'fusion':sum(f)},
            'paired_jev_vs_fusion':exact_mcnemar(a,f),
            'paired_qwen_vs_fusion':exact_mcnemar(b,f),
            'caution':'This excludes safe cases; separately report coverage / false denial. Do not interpret p without sample size & protocol.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--records',required=True);p.add_argument('--output',default='outputs/paired_benchmark.json');a=p.parse_args()
    rows=[json.loads(x) for x in Path(a.records).read_text().splitlines() if x.strip()]
    out=analyze(rows)
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(out,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
