"""Exhaustive combinatorial SOFTWARE contract check, NOT visual-model accuracy.

Simulates input JSON dictionaries only. It does NOT infer an image and does
not establish real-world error rates or calibrated confidence thresholds.
"""
from __future__ import annotations
import itertools
import json
from collections import Counter
from pathlib import Path
from rescuemind.checkpoint import decide_checkpoint

def run():
    reasons=Counter()
    allowed=[]
    n=0
    for js,qs,hazard,jscene,qscene,present,conf in itertools.product(
            ('water','medicine','other'),('water','medicine','other'),
            (.04,.5,float('nan')),('unknown','clear','hazard'),('unknown','clear','hazard'),(.95,.3),(.92,.4)):
        j={'model':'jev-1.14.0','real_model':True,'supply':js,'supply_confidence':conf,
           'supply_present_probability':present,'hazard_probability':hazard,'scene':jscene}
        q={'model':'qwen3.8-omni-flash','real_model':True,'supply':qs,'scene':qscene}
        d=decide_checkpoint('water',j,q)
        n+=1;reasons[d.reason]+=1
        if d.allow:
            assert js==qs=='water' and hazard<.35 and jscene!='hazard' and qscene!='hazard' and present>=.8 and conf>=.65
            allowed.append({'jev_supply':js,'qwen_supply':qs,'hazard':hazard,'jev_scene':jscene,'qwen_scene':qscene,'presence':present,'confidence':conf})
    return {'kind':'PURE_SYNTHETIC_CONTRACT_TEST_NOT_MODEL_ACCURACY',
            'cases':n,'allowed':len(allowed),'rejected':n-len(allowed),
            'reasons':dict(sorted(reasons.items())),'sample_allowed':allowed[:3],
            'real_jev_calls':0,'real_qwen_calls':0}

if __name__=='__main__':
    result=run()
    out=Path('outputs/release/v09_fault_matrix.json');out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))
