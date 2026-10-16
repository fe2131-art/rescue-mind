"""Software-policy counterfactuals with synthetic model outcomes (NOT AI accuracy)."""
from __future__ import annotations
import json
import sys
from itertools import product
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.checkpoint import decide_checkpoint


def run():
    cases=[]
    for actual_supply,j_label,q_label,high_conf,high_presence in product(
        ('water','medicine','none'),('water','medicine','other'),('water','medicine','other'),(False,True),(False,True)):
        expected='water'
        jev={'real_model':True,'model':'jev-1.14.0','supply':j_label,
             'supply_confidence':.92 if high_conf else .38,
             'supply_present_probability':.96 if high_presence else .21}
        qwen={'real_model':True,'model':'qwen3.8-omni-flash','supply':q_label}
        policies={'always_continue':True,
                  'jev_only':jev['supply']=='water' and high_conf and high_presence,
                  'jev_plus_qwen':decide_checkpoint(expected,jev,qwen).allow}
        cases.append({'actual_supply':actual_supply,'jev_label':j_label,'qwen_label':q_label,
                      'confidence_high':high_conf,'presence_high':high_presence,'policies':policies,
                      'oracle_correct_to_continue':actual_supply==expected})
    stats={}
    for p in ('always_continue','jev_only','jev_plus_qwen'):
        unsafe=[c for c in cases if not c['oracle_correct_to_continue']]
        safe=[c for c in cases if c['oracle_correct_to_continue']]
        stats[p]={'allow_total':sum(c['policies'][p] for c in cases),
                  'unsafe_allow_count':sum(c['policies'][p] for c in unsafe),
                  'safe_refusal_count':sum(not c['policies'][p] for c in safe)}
    return {'kind':'SYNTHETIC_LOGIC_ABLATION_NOT_REAL_VLM_MODEL_MEASUREMENTS',
            'n_cases':len(cases),'policies':stats,
            'warning':'Enumerated artificial labels, not sampled real imagery; do not interpret these fractions as model safety or accuracy.',
            'cases':cases}

if __name__=='__main__':
    result=run()
    p=ROOT/'outputs/release/v08_counterfactual_software.json'
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))
