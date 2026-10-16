#!/usr/bin/env python3
"""Fail-closed, READ-ONLY Gazebo Transport topic readiness probe.

The normal run NEVER accepts fixtures. A fixture option exists only for testing
and cannot be passed by the live orchestrator. Presence != data freshness.
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.gazebo_transport_contract import validate_static,audit_runtime_topics,GazeboContractError


def run_probe(*, attempts=4, interval=1.0, runner=subprocess.run, sleeper=time.sleep) -> dict:
    last={'ok':False,'missing':['not_checked']}
    for number in range(attempts):
        try:
            p=runner(['gz','topic','-l'],capture_output=True,text=True,timeout=9,check=False)
            if p.returncode!=0:
                last={'ok':False,'missing':['gz_topic_command_failed'], 'returncode':p.returncode,
                      'stderr_excerpt':p.stderr[:300]}
            else:
                last=audit_runtime_topics(p.stdout)
        except (OSError,subprocess.TimeoutExpired,GazeboContractError) as e:
            last={'ok':False,'missing':['gazebo_transport_unavailable'], 'detail':str(e)[:300]}
        if last['ok']:
            last['attempts_used']=number+1
            return last
        if number+1<attempts:
            sleeper(interval)
    last['attempts_used']=attempts
    return last


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--attempts',type=int,default=4)
    p.add_argument('--interval',type=float,default=1.)
    p.add_argument('--output',default=str(ROOT/'outputs/local_runtime_diagnostics/v21_gz_transport.json'))
    a=p.parse_args(argv)
    if not 1<=a.attempts<=20 or not 0<=a.interval<=10:
        p.error('invalid probe attempts/interval')
    try:
        static=validate_static(ROOT/'worlds/rescuemind_test_arena.sdf', ROOT/'configs/ros_gz_bridge_v20.yaml')
        runtime=run_probe(attempts=a.attempts,interval=a.interval)
        result={'ok':runtime['ok'],'static':static,'runtime':runtime}
    except GazeboContractError as e:
        result={'ok':False,'static_error':str(e),'runtime':'not_attempted'}
    output=Path(a.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['ok'] else 4

if __name__=='__main__':raise SystemExit(main())
