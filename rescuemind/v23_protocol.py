"""Pre-registered, balanced experimental order for paired Jev/Qwen recognition.

The schedule is deterministic for a fixed seed and saved BEFORE collecting frames.
It is not itself evidence of Gazebo execution or model performance.
"""
from __future__ import annotations
import hashlib
import json
import random
from pathlib import Path

SCENES=('nominal','swapped','empty')
ITEMS=('water','medicine')


def truth(scene:str,item:str)->str:
    if scene not in SCENES or item not in ITEMS:
        raise ValueError('unsupported experiment condition')
    if scene=='empty':return 'other'
    if scene=='nominal':return item
    return 'medicine' if item=='water' else 'water'


def make_protocol(repetitions:int=5,seed:int=20261016)->dict:
    if type(repetitions)!=int or not 1<=repetitions<=100:
        raise ValueError('repetitions must be integer between 1 and 100')
    if type(seed)!=int or not 0<=seed<2**32:
        raise ValueError('seed must be uint32')
    conditions=[(scene,item,rep) for rep in range(1,repetitions+1) for scene in SCENES for item in ITEMS]
    random.Random(seed).shuffle(conditions)
    trials=[]
    for i,(scene,item,rep) in enumerate(conditions,1):
        trials.append({'id':f'R{i:03d}', 'order':i,'scene':scene,'expected':item,
                       'repeat':rep,'truth_supply':truth(scene,item),
                       'truth_scene':'clear', 'expected_action':'ALLOW' if scene=='nominal' else 'DENY'})
    obj={'schema':'rescuemind_v23_protocol_v1','study':'on_site_supply_recognition',
         'seed':seed,'repetitions_per_scene_item':repetitions,
         'planned_n':len(trials),
         'scene_sdf_invariants':'checked_by_scene_variants.audit_scenarios',
         'inference_input_policy':'Never send scene label, truth label, or outcome to either model; supply only image and generic decision prompts.',
         'truth_source':'SDF scene configuration; verify rendered frames by a human before scoring',
         'trials':trials}
    return obj


def validate_protocol(p:dict)->None:
    if p.get('schema')!='rescuemind_v23_protocol_v1':raise ValueError('wrong schema')
    reps=p.get('repetitions_per_scene_item')
    if type(reps)!=int or not 1<=reps<=100:raise ValueError('bad repetitions')
    expected=make_protocol(reps,p.get('seed'))
    if p!=expected:raise ValueError('protocol changed after preregistration or corrupted')


def dump_protocol(path:Path,repetitions:int=5,seed:int=20261016)->dict:
    p=make_protocol(repetitions,seed)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        try:
            previous=json.loads(path.read_text(encoding='utf-8'))
        except (ValueError,OSError) as exc:
            raise ValueError('existing protocol corrupted; refuse overwrite') from exc
        if previous!=p:
            raise ValueError('protocol already registered; refusing to overwrite a different seed or plan')
        return p
    path.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return p
