"""Enumerate synthetic on-site model disagreements. NEVER report as model accuracy."""
from __future__ import annotations
import itertools
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.checkpoint import decide_checkpoint


def run():
    cases=[]
    for jlabel,qlabel,conf,presence,jreal,qreal in itertools.product(
        ('water','medicine','other'),('water','medicine','other'),(.4,.9),(.4,.9),(False,True),(False,True)):
        j={'real_model':jreal,'model':'jev-1.14.0','supply':jlabel,
           'supply_confidence':conf,'supply_present_probability':presence}
        q={'real_model':qreal,'model':'qwen3.8-omni-flash','supply':qlabel}
        decision=decide_checkpoint('water',j,q)
        cases.append({'jev_label':jlabel,'qwen_label':qlabel,'jev_confidence':conf,
            'jev_presence':presence,'jev_real_flag':jreal,'qwen_real_flag':qreal,
            'allow':decision.allow,'reason':decision.reason})
    return {'category':'synthetic_fault_matrix_NOT_actual_Jev_or_Qwen_performance',
            'n_cases':len(cases),'n_allow':sum(c['allow'] for c in cases),
            'n_reject':sum(not c['allow'] for c in cases),'cases':cases}

if __name__=='__main__':
    result=run()
    p=Path('outputs/release/v07_checkpoint_fault_matrix.json')
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},ensure_ascii=False))
