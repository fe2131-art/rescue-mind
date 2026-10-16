#!/usr/bin/env python3
"""Deterministic integration checks, logs MUST be labeled scripted model fixtures."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.closed_loop_twin import simulate

def main():
    out=ROOT/'verification/v17'
    out.mkdir(exist_ok=True,parents=True)
    scenarios=['nominal','ai_denied','lidar_block','command_loss','camera_freeze','odom_freeze']
    rows=[]
    for s in scenarios:
        r=simulate(s).as_dict()
        (out/f'closed_loop_{s}.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
        rows.append({k:v for k,v in r.items() if k not in ('trace',)})
    assert rows[0]['mission_completed'] and not any(x['mission_completed'] for x in rows[1:]),rows
    assert rows[1]['station_reached'] and not rows[1]['shelter_reached']
    assert all(x['stop_delay_s']<=2.2 for x in rows[2:])
    summary={'label':'SCRIPTED OFFLINE CLOSED LOOP (NO VLM/Gazebo/ROS API)',
             'cases':len(rows),'expected_outcomes_matched':len(rows),'runs':rows}
    (out/'campaign_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'cases':len(rows),'matched':len(rows),'statuses':[(x['scenario'],x['terminal_reason']) for x in rows]},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
