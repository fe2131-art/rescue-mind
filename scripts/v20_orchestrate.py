#!/usr/bin/env python3
"""v2.0 Gazebo -> bridge -> guard -> live sensor quality gate -> mission.

--plan prints exact commands without requiring ROS/Gazebo/API keys.
--run executes on the USER'S Ubuntu ROS 2 Jazzy machine; not validated in this
container.  Every child and attempted readiness check logs in a unique folder.
The direct-drive motion-check has no AI and cannot be submitted as AI proof.
"""
from __future__ import annotations
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind.stack_supervisor import ManagedCommand, Supervisor, StackFailure


def shell_exec(args: list[str]) -> tuple[str, ...]:
    """Source ROS environment for commands using apt-installed ROS modules."""
    command = 'source /opt/ros/jazzy/setup.bash && '
    command += 'source ' + shlex.quote(str(ROOT/'.venv/bin/activate')) + ' && '
    command += 'exec ' + shlex.join(args)
    return ('bash', '-c', command)


def build_plan(scenario: str, instruction: str, *, mission_timeout: int,
               evidence_dir: Path | None = None, capture_rosbag: bool = False) -> dict:
    if scenario not in ('motion-check', 'live'):
        raise ValueError('invalid scenario')
    script = str(ROOT/'ros/gazebo_waypoint_mission.py')
    cmd = ['python3', script, '--motion-check'] if scenario == 'motion-check' else \
          ['python3', script, '--run-live', '--instruction', instruction]
    cmd += ['--stage-timeout', '120']
    if evidence_dir is not None:
        cmd += ['--run-id', evidence_dir.name, '--out', str(evidence_dir/'mission.json'),
                '--checkpoint-image', str(evidence_dir/'checkpoint.jpg')]
    services = [
        ManagedCommand('gazebo', ('gz', 'sim', '-r', '-v', '4', str(ROOT/'worlds/rescuemind_test_arena.sdf'))),
        ManagedCommand('bridge', ('bash', str(ROOT/'scripts/bridge_direct_gazebo.sh'))),
        ManagedCommand('velocity_guard', ('bash', str(ROOT/'scripts/start_velocity_guard.sh'))),
    ]
    if evidence_dir is not None:
        services.append(ManagedCommand('independent_odom_recorder', shell_exec([
            'python3', str(ROOT/'ros/odom_evidence_recorder.py'),
            '--out', str(evidence_dir/'independent_ros_topics.jsonl'),
            '--run-id', evidence_dir.name])))
    if capture_rosbag and evidence_dir is not None:
        services.append(ManagedCommand('rosbag_recorder', shell_exec([
            'ros2', 'bag', 'record', '-o', str(evidence_dir/'rosbag2'), '--use-sim-time', '--topics',
            '/clock', '/odom', '/cmd_vel', '/rescuemind/cmd_vel_request',
            '/camera', '/scan', '/rescuemind/guard_ready'])))
    return {
        'scenario': scenario,
        'prerequisites': ['Ubuntu 24.04', 'ROS 2 Jazzy + ros_gz_bridge',
                          'Gazebo Harmonic', 'project .venv from setup_ubuntu_jazzy.sh'],
        'services': services,
        'readiness': ('bash', str(ROOT/'scripts/v20_live_readiness.sh')),
        'mission': ManagedCommand('mission', shell_exec(cmd)),
        'mission_timeout': mission_timeout,
    }


def check_prerequisites(scenario: str, *, capture_rosbag: bool = False):
    missing = []
    # ros2 CLI may be absent from the caller's PATH before source; child
    # commands source Jazzy explicitly. Check the same shell contract instead.
    if shutil.which('gz') is None:
        missing.append('gz')
    if Path('/opt/ros/jazzy/setup.bash').is_file():
        status=subprocess.run(('bash','-c','source /opt/ros/jazzy/setup.bash && command -v ros2 >/dev/null && python3 -c "import rclpy"'),
                              capture_output=True,text=True,timeout=15)
        if status.returncode!=0:
            missing.append('ROS Jazzy sourced CLI/rclpy')
    else:
        missing.append('ROS Jazzy installation')
    if not (Path('/opt/ros/jazzy/setup.bash').is_file()):
        missing.append('/opt/ros/jazzy/setup.bash')
    if not (ROOT/'.venv/bin/activate').is_file():
        missing.append('.venv/bin/activate (run bash scripts/setup_ubuntu_jazzy.sh)')
    if capture_rosbag and Path('/opt/ros/jazzy/setup.bash').is_file():
        check_bag=subprocess.run(('bash','-c','source /opt/ros/jazzy/setup.bash && ros2 bag record --help >/dev/null'),
                                 capture_output=True,text=True,timeout=20)
        if check_bag.returncode!=0:
            missing.append('ros2 bag record (install ros-jazzy-rosbag2)')
    if scenario == 'live':
        from ros.gazebo_waypoint_mission import require_api_configuration
        require_api_configuration('qwen3.8-omni-flash')
    if missing:
        raise StackFailure('Missing prerequisites: ' + ', '.join(missing))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--plan', action='store_true', help='print what will run without side effects')
    g.add_argument('--run', action='store_true', help='actually run ROS/Gazebo on Ubuntu')
    p.add_argument('--scenario', choices=['motion-check', 'live'], default='motion-check')
    p.add_argument('--capture-rosbag', action='store_true', help='optional ROS 2 bag evidence (disk space required)')
    p.add_argument('--instruction', default='避難所Bに飲料水を届けて')
    p.add_argument('--startup-timeout', type=int, default=180)
    p.add_argument('--mission-timeout', type=int, default=440)
    args = p.parse_args(argv)
    if args.startup_timeout < 5 or args.mission_timeout < 10:
        p.error('timeouts too short')
    placeholder=ROOT/'outputs'/'runs'/'<run_id>' if args.capture_rosbag else None
    plan = build_plan(args.scenario, args.instruction, mission_timeout=args.mission_timeout,
                      evidence_dir=placeholder, capture_rosbag=args.capture_rosbag)
    summary = {'scenario': plan['scenario'], 'services': [list(x.argv) for x in plan['services']],
               'readiness': list(plan['readiness']), 'mission': list(plan['mission'].argv),
               'capture_rosbag': args.capture_rosbag,
               'notes': 'plan/dry output is not execution evidence; live requires Jev+Qwen3.8 API.'}
    if args.plan:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    run_id = uuid.uuid4().hex[:16]
    log_dir = ROOT/'outputs'/'runs'/run_id
    log_dir.mkdir(parents=True, exist_ok=False)
    plan = build_plan(args.scenario, args.instruction, mission_timeout=args.mission_timeout, evidence_dir=log_dir,
                      capture_rosbag=args.capture_rosbag)
    summary['mission'] = list(plan['mission'].argv)
    (log_dir/'stack_plan.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    outcome = {'run_id': run_id, 'scenario': args.scenario, 'state': 'FAILED', 'error': None,
               'scope': 'actual external ROS/Gazebo runtime if command executed on Ubuntu'}
    try:
        check_prerequisites(args.scenario, capture_rosbag=args.capture_rosbag)
        with Supervisor(log_dir) as sup:
            for spec in plan['services']:
                sup.start_service(spec)
                time.sleep(1.)
                sup.ensure_alive()
            def probe():
                try:
                    r = subprocess.run(plan['readiness'], capture_output=True, text=True, timeout=52)
                    (log_dir/'readiness_last.txt').write_text(r.stdout + '\nSTDERR\n' + r.stderr)
                    return r.returncode == 0
                except subprocess.TimeoutExpired:
                    return False
            sup.wait_readiness(probe, args.startup_timeout, interval_s=2.)
            sup.run_mission(plan['mission'], plan['mission_timeout'])
            from rescuemind.run_completion import validate, CompletionError
            try:
                outcome['receipt']=validate(log_dir/'mission.json',args.scenario,run_id)
            except CompletionError as e:
                raise StackFailure('mission exit 0 but completion receipt invalid: '+str(e)) from e
            # A successful mission-owned JSON receipt is insufficient for an award
            # claim. Require independently subscribed /odom and /cmd_vel traces.
            from rescuemind.motion_evidence import audit_motion, MotionEvidenceError
            mission_record=json.loads((log_dir/'mission.json').read_text(encoding='utf8'))
            item=mission_record.get('intent',{}).get('item')
            config=json.loads((ROOT/'configs/gazebo_waypoints.json').read_text())
            if item not in ('water','medicine'):
                raise StackFailure('motion evidence: invalid supply item')
            # The observer runs asynchronously: give the final odometry sample
            # up to 1.5 seconds to reach the separate subscriber, never assume
            # process exit means physical movement was observed.
            last_error=None
            for attempt in range(11):
                sup.ensure_alive()
                try:
                    outcome['independent_motion_evidence']=audit_motion(
                        log_dir/'independent_ros_topics.jsonl',run_id=run_id,
                        station=config[item],shelter=config['B'])
                    break
                except (MotionEvidenceError,OSError,ValueError) as e:
                    last_error=e
                    if attempt<10: time.sleep(.15)
            else:
                raise StackFailure('mission receipt passed but independent ROS movement evidence failed: '+str(last_error)) from last_error
            if args.scenario == 'live':
                # Distinguish physical trajectory from authorization chronology.
                from rescuemind.causal_evidence import audit_causal, CausalEvidenceError
                try:
                    outcome['authorization_motion_chronology'] = audit_causal(
                        log_dir/'mission.json', log_dir/'independent_ros_topics.jsonl',
                        station=config[item], shelter=config['B'])
                except (CausalEvidenceError, ValueError, OSError) as exc:
                    raise StackFailure('AI authorization/movement chronology failed: '+str(exc)) from exc
            outcome['state'] = 'COMPLETED'
    except (StackFailure, OSError, RuntimeError) as e:
        outcome['error'] = f'{type(e).__name__}: {e}'
        print(outcome['error'], file=sys.stderr)
        return_code = 2
    else:
        return_code = 0
        if args.capture_rosbag:
            from rescuemind.bag_evidence import audit_bag_metadata, BagEvidenceError
            try:
                outcome['rosbag_evidence'] = audit_bag_metadata(log_dir/'rosbag2', require_clock=True)
            except (BagEvidenceError, OSError, ValueError) as exc:
                outcome['state'] = 'FAILED'
                outcome['error'] = 'rosbag evidence missing/incomplete: ' + str(exc)
                return_code = 2
    finally:
        (log_dir/'stack_result.json').write_text(json.dumps(outcome, ensure_ascii=False, indent=2)+'\n')
        print('Stack execution records:', log_dir)
    return return_code


if __name__ == '__main__':
    raise SystemExit(main())
