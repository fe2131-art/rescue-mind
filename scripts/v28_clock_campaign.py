#!/usr/bin/env python3
"""14 predetermined artificial conditions for camera vs sim-clock contract.

Not a real simulator run, not a test of model accuracy.
"""
import json,sys
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.camera_clock_gate import CameraClockGate,CameraClockRejected
from rescuemind.v28_clock_evidence import audit_clock_capture,ClockEvidenceError


def img(ns):return NS(header=NS(stamp=NS(sec=ns//10**9,nanosec=ns%10**9)))
def gate():
 g=CameraClockGate()
 for t in range(10,14):g.clock(t,0,float(t))
 return g

def receipt():
 return {'run_type':'jev_qwen_live_mission','events':[
 {'stage':'checkpoint_stationary_verified','t_wall_s':2.},
 {'stage':'checkpoint_image_quality_verified','t_wall_s':2.8,'ros_stamps_ns':[11_100_000_000,12_850_000_000]},
 {'stage':'checkpoint_camera_sim_clock_verified','t_wall_s':2.8,'basis':'Gazebo_clock_vs_camera_ROS_stamp',
  'sim_clock_ns':13_000_000_000,'camera_ros_stamp_ns':12_850_000_000,
  'camera_lag_to_sim_clock_s':.15,'clock_callback_idle_s':.05,'clock_progress_idle_s':.05,
  'clock_advances':3,'limits_s':{'max_lag':1.2,'max_lead':.25,'max_clock_idle':.9}},
 {'stage':'checkpoint_frame','t_wall_s':2.9,'ros_acquisition_stamp_ns':12_850_000_000},
 {'stage':'checkpoint_decision','t_wall_s':4.,'allow':False}]}

def case(name, fn, expected):
 try:fn();observed='ACCEPT'
 except (CameraClockRejected,ClockEvidenceError):observed='DENY'
 return {'case':name,'expected':expected,'observed':observed,'matched':expected==observed}

cases=[
 case('recent_camera_stamp',lambda:gate().check_frame(img(12_850_000_000),13.05),'ACCEPT'),
 case('old_increasing_frame',lambda:gate().check_frame(img(10_500_000_000),13.05),'DENY'),
 case('future_sim_stamp',lambda:gate().check_frame(img(13_900_000_000),13.05),'DENY'),
 case('invalid_ros_stamp',lambda:gate().check_frame(img(0),13.05),'DENY'),
 case('late_clock_callback',lambda:gate().check_frame(img(12_950_000_000),14.2),'DENY'),
 case('gazebo_clock_rewind',lambda:gate().clock(10,0,13.05),'DENY'),
 case('camera_missing_clock',lambda:CameraClockGate().check_frame(img(12_000_000_000),13.05),'DENY'),
 case('audit_valid',lambda:audit_clock_capture(receipt()),'ACCEPT'),
]
for name,mutation in [
 ('audit_missing_event',lambda r:r['events'].pop(2)),
 ('audit_frame_stamp_changed',lambda r:r['events'][3].update(ros_acquisition_stamp_ns=123)),
 ('audit_forged_lag',lambda r:r['events'][2].update(camera_lag_to_sim_clock_s=0.)),
 ('audit_stale_clock',lambda r:r['events'][2].update(clock_progress_idle_s=1.5)),
 ('audit_weakened_limits',lambda r:r['events'][2]['limits_s'].update(max_lag=12.)),
 ('audit_wrong_time_basis',lambda r:r['events'][2].update(basis='unix_wall_time')),
]:
 def run(mutation=mutation):
  r=receipt();mutation(r);audit_clock_capture(r)
 cases.append(case(name,run,'DENY'))
report={'release':'2.8.0','source':'DETERMINISTIC_SYNTHETIC_NO_GAZEBO_NO_REAL_VLM',
        'total':len(cases),'matched':sum(x['matched'] for x in cases), 'cases':cases}
folder=ROOT/'verification/v28';folder.mkdir(exist_ok=True,parents=True)
(folder/'clock_fault_campaign.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
if report['matched']!=report['total']:sys.exit(1)
