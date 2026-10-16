#!/usr/bin/env python3
"""Deterministic artificial Jev/Qwen response study. NO REAL MODEL CALLS.
A null box is deliberately irrelevant: the live supply classification no longer
requests experimental localization. This does not measure accuracy.
"""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rescuemind import jev
from rescuemind.checkpoint import decide_checkpoint

rows=[
 ('nominal_water','water',.98,'water','water',True),
 ('nominal_medicine','medicine',.98,'medicine','medicine',True),
 ('empty_water_station','other',.02,'other','water',False),
 ('empty_medicine_station','other',.03,'other','medicine',False),
 ('swapped_water_station','medicine',.98,'medicine','water',False),
 ('swapped_medicine_station','water',.98,'water','medicine',False),
 ('qwen_disagrees_water','water',.95,'medicine','water',False),
 ('qwen_disagrees_medicine','medicine',.95,'water','medicine',False),
 ('jev_low_presence_water','water',.07,'water','water',False),
 ('jev_low_presence_medicine','medicine',.07,'medicine','medicine',False),
]
results=[]
for name,supply,presence,q_supply,expected,allow in rows:
    # Emulate strictly the expected transport envelope, not actual API predictions.
    wire={'model':jev.MODEL_ID,'answers':{
        'supply':{'type':'choice','choice':supply,'confidence':.93},
        'visible_supply':{'type':'noul','noul':presence},
        'scene':{'type':'choice','choice':'unknown'},
        'hazard':{'type':'noul','noul':.02},
    }}
    j=jev.parse_response(wire,require_box=False)
    q={'real_model':True,'model':'qwen3.8-omni-flash','supply':q_supply,'scene':'unknown'}
    decision=decide_checkpoint(expected,j,q)
    results.append({'case':name,'expect_allow':allow,'actual_allow':decision.allow,'reason':decision.reason,
                    'model_calls':'NONE: synthetic response envelope'})
count=sum(r['actual_allow']==r['expect_allow'] for r in results)
out={'scope':'PURE_SYNTHETIC_TRANSPORT_RESPONSE_CONTRACT_NO_ACTUAL_JEV_QWEN_ACCURACY',
     'total':len(results),'matched':count,'cases':results}
path=Path(__file__).resolve().parents[1]/'verification/v29/jev_checkpoint_campaign.json'
path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'total':len(results),'matched':count,'scope':out['scope']}))
if count!=len(results):raise SystemExit(1)
