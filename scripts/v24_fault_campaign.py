#!/usr/bin/env python3
"""OFFLINE synthetic fault cases; does not attest Jev, Qwen or Gazebo."""
from __future__ import annotations
import copy,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tests.test_v24_negative_outcome import setup,RUN,WAYPOINTS
from rescuemind.v24_trial_outcome import classify_negative_run,TrialClassificationError
from rescuemind.v24_run_registry import RunRegistrationError

def main():
    rows=[]
    for label,mutate,allowed in [
        ('verified_denial_fixture',None,True),
        ('wrong_scene', lambda m,r,p:setattr(p,'scene','nominal'),False),
        ('absent_ai_checkpoint',lambda m,r,p: m.update(checkpoint=None),False),
        ('no_hold_event',lambda m,r,p: m.update(events=[x for x in m['events'] if x.get('stage')!='checkpoint_denial_dwell_finished']),False),
        ('early_hold',lambda m,r,p:next(x for x in m['events'] if x.get('stage')=='checkpoint_denial_dwell_finished').update(t_wall_s=7.1),False),
        ('nonzero_stop_cmd',lambda m,r,p:next(x for x in m['events'] if x.get('stage')=='checkpoint_denial_dwell_finished').update(commanded_linear=.3),False),
        ('no_jev',lambda m,r,p: m['checkpoint']['model_calls']['jev'].update(real_model=False),False),
        ('false_arrival',lambda m,r,p:next(x for x in m['events'] if x.get('stage')=='supply_station').update(arrived=False),False),
        ('left_station',lambda m,r,p: r[-1].update(x=2.15,y=-1.12),False),
    ]:
        with tempfile.TemporaryDirectory() as td:
            directory=Path(td)/RUN;directory.mkdir()
            mp,rp,mission,trace=setup(directory)
            obj=type('scenario',(),{'scene':'swapped'})()
            if mutate:
                mutate(mission,trace,obj)
                mp.write_text(json.dumps(mission))
                rp.write_text('\n'.join(json.dumps(t) for t in trace)+'\n')
            try:
                classify_negative_run(directory,scene=obj.scene,run_id=RUN,waypoints=WAYPOINTS)
                actual=True
            except (ValueError,OSError,KeyError,TypeError):
                actual=False
            rows.append({'fault':label,'expected':allowed,'accepted':actual,'matched':actual==allowed})
    out=ROOT/'verification/v24/v24_synthetic_fault_campaign.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'scope':'ARTIFICIAL_MOCKED_LOGS_NOT_ROBOT_MODEL_EVIDENCE','n':len(rows),'all_match':all(r['matched'] for r in rows),'cases':rows},indent=2)+'\n')
    print(json.dumps({'n':len(rows),'matched':sum(r['matched'] for r in rows),'scope':'OFFLINE_SYNTHETIC'},indent=2))
    return 0 if all(r['matched'] for r in rows) else 2
if __name__=='__main__': raise SystemExit(main())
