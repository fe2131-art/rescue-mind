#!/usr/bin/env python3
"""12+ deterministic adverse checkpoint camera inputs; SYNTHETIC ONLY."""
import json,sys
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.image_acquisition import CheckpointAcquisitionGate,AcquisitionRejected

def msg(stamp,style='pattern',enc='rgb8',truncate=0,padding=0):
    w,h=320,240
    lines=[]
    for y in range(h):
        row=bytearray()
        for x in range(w):
            v=20+(x*3+y*5)%200 if style=='pattern' else {'black':0,'white':255,'flat_gray':120,'near_black':1}.get(style,40)
            row.extend((v,v,v))
        row.extend(bytes(padding));lines.append(bytes(row))
    raw=b''.join(lines)
    if truncate:raw=raw[:-truncate]
    return NS(width=w,height=h,step=w*3+padding,data=raw,encoding=enc,header=NS(stamp=NS(sec=stamp,nanosec=0)))

def case(name):
    g=CheckpointAcquisitionGate(10_000_000_000,12.5)
    if name=='valid_pattern':
        g.observe(msg(11),12.7);return g.observe(msg(12),13.0)
    if name=='valid_padding':
        g.observe(msg(11,padding=4),12.7);return g.observe(msg(12,padding=4),13.0)
    if name=='blackout':g.observe(msg(11,'black'),12.7)
    if name=='whiteout':g.observe(msg(11,'white'),12.7)
    if name=='flat_gray':g.observe(msg(11,'flat_gray'),12.7)
    if name=='near_black':g.observe(msg(11,'near_black'),12.7)
    if name=='broken_payload':g.observe(msg(11,truncate=9),12.7)
    if name=='unsupported_encoding':g.observe(msg(11,enc='bayer_rggb8'),12.7)
    if name=='regressed_stamp':g.observe(msg(12),12.7);g.observe(msg(11),13.)
    if name=='stale_prior_stamp':return g.observe(msg(9),12.7)
    if name=='pre_dwell_frame':return g.observe(msg(11),12.1)
    if name=='duplicate_stamp':g.observe(msg(11),12.7);return g.observe(msg(11),13.)
    if name=='short_interval':g.observe(msg(11),12.7);return g.observe(msg(12),12.75)
    if name=='missing_second_frame':g.observe(msg(11),12.7);return g.frame is not None
    raise ValueError(name)

EXPECTED={
    'valid_pattern':'ACCEPT','valid_padding':'ACCEPT',
    'blackout':'REJECT','whiteout':'REJECT','flat_gray':'REJECT','near_black':'REJECT',
    'broken_payload':'REJECT','unsupported_encoding':'REJECT',
    'regressed_stamp':'REJECT','stale_prior_stamp':'REJECT','pre_dwell_frame':'REJECT',
    'duplicate_stamp':'REJECT','short_interval':'REJECT','missing_second_frame':'REJECT'}

def run():
    results=[]
    for name,expected in EXPECTED.items():
        try:
            passed=case(name)
            observed='ACCEPT' if passed else 'REJECT'
            reason='accepted' if passed else 'not_enough_valid_distinct_frames'
        except (AcquisitionRejected,ValueError) as ex:
            observed='REJECT';reason=str(ex)
        results.append({'scenario':name,'expected':expected,'actual':observed,
                        'matched':observed==expected,'reason':reason})
    report={'scope':'SYNTHETIC_DETERMINISTIC_FRAME_PAYLOAD_NOT_GAZEBO_OR_JEV',
            'total':len(results),'matched':sum(r['matched'] for r in results),
            'results':results,'actual_gazebo_camera':'NOT_TESTED',
            'actual_jev_qwen_inference':'NOT_TESTED'}
    dest=ROOT/'verification/v27';dest.mkdir(parents=True,exist_ok=True)
    (dest/'synthetic_camera_campaign.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if report['total']!=report['matched']:raise SystemExit(2)
    return report
if __name__=='__main__':run()
