"""Capture real Jev/Qwen outputs into a hand-labeled evaluation set.

Never commit actual indoor camera frames or personal data without review.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time
from . import jev,qwen35


def record(supply_image:str,corridor_image:str,expected:str,truth_supply:str,truth_scene:str,
           qwen_model:str,output:str,case_id:str,endpoint:str=qwen35.DEFAULT_ENDPOINT)->dict:
    if not Path(supply_image).is_file() or not Path(corridor_image).is_file():
        raise FileNotFoundError('Provide both real, distinct images')
    from .multimodal_demo import run
    start=time.perf_counter()
    response=run(supply_image,expected,qwen_model=qwen_model,endpoint=endpoint,corridor_image=corridor_image)
    latency=time.perf_counter()-start
    row={'id':case_id,'created_utc':datetime.now(timezone.utc).isoformat(),
         'provenance':'live_api_capture','expected':expected,
         'truth':{'supply':truth_supply,'scene':truth_scene},
         'image_sha256':{'supply':hashlib.sha256(Path(supply_image).read_bytes()).hexdigest(),
                         'corridor':hashlib.sha256(Path(corridor_image).read_bytes()).hexdigest()},
         'supply':response['supply'],'corridor':response['corridor'],
         'gate':response['gate'],'wall_sec':round(latency,3)}
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    return row


def main():
    p=argparse.ArgumentParser()
    for name in ('supply-image','corridor-image','expected','truth-supply','truth-scene','id'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--qwen-model',default='qwen3.8-omni-flash')
    p.add_argument('--endpoint',default=qwen35.DEFAULT_ENDPOINT)
    p.add_argument('--output',default='outputs/real_captures.jsonl')
    a=p.parse_args()
    if a.expected not in {'water','medicine'} or a.truth_supply not in {'water','medicine','other'} or a.truth_scene not in {'clear','hazard','unknown'}:
        p.error('Invalid annotations')
    row=record(a.supply_image,a.corridor_image,a.expected,a.truth_supply,a.truth_scene,a.qwen_model,a.output,a.id,a.endpoint)
    print(json.dumps({'id':row['id'],'gate':row['gate'],'wall_sec':row['wall_sec']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
