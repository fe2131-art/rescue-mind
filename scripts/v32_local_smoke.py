#!/usr/bin/env python3
"""Real GPU inference smoke on an image file, without ROS / robot motion.

Do not use bundled schematic fixtures as recognition accuracy evidence.
"""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rescuemind.local_vision import verify_station_local

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--image',type=Path,required=True)
    p.add_argument('--expected',choices=['water','medicine'],default='water')
    p.add_argument('--mode',choices=['single','dual'],default='single')
    p.add_argument('--out',type=Path,default=None)
    a=p.parse_args();start=time.monotonic()
    outcome=verify_station_local(a.image,a.expected,mode=a.mode)
    report={'scope':'ACTUAL_LOCAL_MODEL_IF_CONNECTED_NOT_ROS_GAZEBO','elapsed_s':round(time.monotonic()-start,3),
            **outcome}
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['decision']['allow'] else 3  # denial is NOT an infrastructure crash
if __name__=='__main__':raise SystemExit(main())
