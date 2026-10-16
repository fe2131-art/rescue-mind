#!/usr/bin/env python3
"""ROS graph publisher identity preflight (NOT authentication or runtime safety proof)."""
import json
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.ros_graph_contract import assert_guard_topology


def read_topic(topic: str) -> str:
    return subprocess.run(['ros2','topic','info',topic,'-v'],check=True,
                          capture_output=True,text=True,timeout=12).stdout


def main():
    result={'scope':'ROS live graph diagnostic only','guard_only_publisher':False}
    try:
        cmd=read_topic('/cmd_vel')
        ready=read_topic('/rescuemind/guard_ready')
        assert_guard_topology(cmd,ready)
        result['guard_only_publisher']=True
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as error:
        result['failure']=type(error).__name__+': '+str(error)
    dest=ROOT/'outputs/local_runtime_diagnostics/v13_guard_graph.json'
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['guard_only_publisher'] else 5)

if __name__=='__main__':main()
