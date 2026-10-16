#!/usr/bin/env python3
"""v3.2 LOCAL-FIRST controlled-scene Gazebo -> bridge -> guard -> live sensor quality gate -> mission.

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


def venv_dir() -> Path:
    """Project venv; the Docker image exports RESCUEMIND_VENV=/opt/rescuemind-venv."""
    return Path(os.environ.get('RESCUEMIND_VENV') or ROOT/'.venv')


def shell_exec(args: list[str]) -> tuple[str, ...]:
    """Source ROS environment for commands using apt-installed ROS modules."""
    command = 'source /opt/ros/jazzy/setup.bash && '
    command += 'source ' + shlex.quote(str(venv_dir()/'bin/activate')) + ' && '
    command += 'exec ' + shlex.join(args)
    return ('bash', '-c', command)


def gazebo_command(world: Path, gz_mode: str = 'auto') -> tuple[str, ...]:
    """Server+GUI on a desktop; server-only EGL rendering on a headless GPU box."""
    if gz_mode not in ('auto', 'headless', 'gui'):
        raise ValueError('invalid gz mode')
    if gz_mode == 'auto':
        gz_mode = 'gui' if os.environ.get('DISPLAY') else 'headless'
    if gz_mode == 'headless':
        return ('gz', 'sim', '-s', '-r', '--headless-rendering', '-v', '3', str(world))
    return ('gz', 'sim', '-r', '-v', '3', str(world))


def build_plan(scenario: str, instruction: str, *, mission_timeout: int, scene: str = "nominal",
               evidence_dir: Path | None = None, capture_rosbag: bool = False,
               local_mode: str = "single", gz_mode: str = 'auto', film: bool = False,
               recovery: bool = False, explain: bool = False, world: Path | None = None,
               prompt_set: str = 'v33', model: str | None = None, intent_backend: str = 'tfidf') -> dict:
    if scenario not in ('motion-check', 'live'):
        raise ValueError('invalid scenario')
    from rescuemind.scene_variants import SCENES
    if scene not in SCENES:
        raise ValueError('unknown experiment scene')
    script = str(ROOT/'ros/gazebo_waypoint_mission.py')
    cmd = ['python3', script, '--motion-check'] if scenario == 'motion-check' else \
          ['python3', script, '--run-live', '--instruction', instruction]
    cmd += ['--stage-timeout', '120']
    if scenario=='live':
        cmd += ['--inference-backend','local','--local-mode',local_mode,
                '--checkpoint-timeout','300']
        if recovery:
            cmd += ['--recovery']
        if explain:
            cmd += ['--explain']
        if intent_backend != 'tfidf':
            cmd += ['--intent-backend', intent_backend]
        if model:
            cmd += ['--vlm-model', model]
    if evidence_dir is not None:
        cmd += ['--run-id', evidence_dir.name, '--out', str(evidence_dir/'mission.json'),
                '--checkpoint-image', str(evidence_dir/'checkpoint.jpg')]
    services = [
        ManagedCommand('gazebo', gazebo_command(world or ROOT/'worlds/scenarios'/('rescuemind_'+scene+'.sdf'), gz_mode)),
        ManagedCommand('bridge', ('bash', str(ROOT/'scripts/bridge_direct_gazebo.sh'))),
        ManagedCommand('velocity_guard', ('bash', str(ROOT/'scripts/start_velocity_guard.sh'))),
    ]
    if scenario=='live':
        from rescuemind.local_vision import PRIMARY_MODEL, SECONDARY_MODEL
        services.insert(0,ManagedCommand('primary_local_vlm', shell_exec([
            'python3',str(ROOT/'scripts/local_vlm_server.py'),'--model',model or PRIMARY_MODEL,'--port','8765',
            '--prompt-set',prompt_set])))
        if local_mode=='dual':
            services.insert(1,ManagedCommand('secondary_local_vlm', shell_exec([
                'python3',str(ROOT/'scripts/local_vlm_server.py'),'--model',SECONDARY_MODEL,'--port','8766'])))
    if evidence_dir is not None:
        services.append(ManagedCommand('guard_graph_watch', shell_exec([
            'python3',str(ROOT/'ros/runtime_guard_graph_watch.py'),
            '--out',str(evidence_dir/'guard_graph_watch.jsonl')])))
    if evidence_dir is not None:
        services.append(ManagedCommand('independent_odom_recorder', shell_exec([
            'python3', str(ROOT/'ros/odom_evidence_recorder.py'),
            '--out', str(evidence_dir/'independent_ros_topics.jsonl'),
            '--run-id', evidence_dir.name])))
    if film and evidence_dir is not None:
        # Demo footage only: Gazebo-rendered overview camera + robot camera frames.
        services.append(ManagedCommand('film_camera_bridge', ('bash', str(ROOT/'scripts/film_camera_bridge.sh'))))
        # Lower CPU priority than the guard/mission so demo footage never starves safety nodes.
        services.append(ManagedCommand('film_recorder', shell_exec([
            'nice', '-n', '15', 'python3', str(ROOT/'ros/film_recorder.py'), '--out', str(evidence_dir/'film')])))
    if capture_rosbag and evidence_dir is not None:
        services.append(ManagedCommand('rosbag_recorder', shell_exec([
            'ros2', 'bag', 'record', '-o', str(evidence_dir/'rosbag2'), '--use-sim-time', '--topics',
            '/clock', '/odom', '/cmd_vel', '/rescuemind/cmd_vel_request',
            '/camera', '/scan', '/rescuemind/guard_ready', '/ground_truth/odom'])))
    return {
        'scenario': scenario, 'scene': scene,
        'prerequisites': ['Ubuntu 24.04', 'ROS 2 Jazzy + ros_gz_bridge',
                          'Gazebo Harmonic', 'project .venv from setup_ubuntu_jazzy.sh'],
        'services': services,
        'readiness': ('bash', str(ROOT/'scripts/v21_live_readiness.sh')),
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
    if not (venv_dir()/'bin/activate').is_file():
        missing.append(str(venv_dir()/'bin/activate')+' (run bash scripts/setup_ubuntu_jazzy.sh or use docker/)')
    if capture_rosbag and Path('/opt/ros/jazzy/setup.bash').is_file():
        check_bag=subprocess.run(('bash','-c','source /opt/ros/jazzy/setup.bash && ros2 bag record --help >/dev/null'),
                                 capture_output=True,text=True,timeout=20)
        if check_bag.returncode!=0:
            missing.append('ros2 bag record (install ros-jazzy-rosbag2)')
    if scenario == 'live':
        try:
            import importlib.util
            if any(importlib.util.find_spec(m) is None for m in ('torch','transformers','accelerate')):
                missing.append('torch/transformers/accelerate for local VLM')
        except (ImportError,ValueError):
            missing.append('local VLM Python packages')
        if shutil.which('nvidia-smi') is None:
            missing.append('nvidia-smi (CUDA GPU driver)')
    if missing:
        raise StackFailure('Missing prerequisites: ' + ', '.join(missing))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--plan', action='store_true', help='print what will run without side effects')
    g.add_argument('--run', action='store_true', help='actually run ROS/Gazebo on Ubuntu')
    p.add_argument('--scenario', choices=['motion-check', 'live'], default='motion-check')
    p.add_argument('--scene', choices=['nominal', 'swapped', 'empty'], default='nominal',
                   help='controlled camera scene: neutral shelves, correct/swapped/empty physical-looking props')
    p.add_argument('--capture-rosbag', action='store_true', help='optional ROS 2 bag evidence (disk space required)')
    p.add_argument('--instruction', default='避難所Bに飲料水を届けて')
    p.add_argument('--local-mode',choices=['single','dual'],default='single',
                   help='single=Qwen2.5-VL-3B twice; dual=Qwen2.5-VL-3B + SmolVLM2-2.2B')
    p.add_argument('--gz-mode', choices=['auto', 'headless', 'gui'], default='auto',
                   help='auto=GUI when DISPLAY is set, otherwise server-only headless EGL rendering')
    p.add_argument('--recovery', action='store_true', help='I-02: search the other station if the supply is wrong/missing')
    p.add_argument('--explain', action='store_true', help='I-03: Japanese one-sentence report after each checkpoint')
    p.add_argument('--prompt-set', choices=['v33', 'v34', 'v35'], default='v33', help='VLM checkpoint prompts (v34 = I-05)')
    p.add_argument('--model', default=None, help='local VLM model id (I-08); default Qwen2.5-VL-3B')
    p.add_argument('--intent-backend', choices=['tfidf', 'llm'], default='tfidf', help='I-04 instruction parser')
    p.add_argument('--lighting', choices=['default', 'dim_evening', 'harsh_noon'], default='default')
    p.add_argument('--hazard-at', choices=['water', 'medicine'], default=None, help='I-05: fire behind this station')
    p.add_argument('--distractor-at', choices=['water', 'medicine'], default=None, help='I-05: cardboard box at this station')
    p.add_argument('--film', action='store_true',
                   help='also record a Gazebo-rendered overview camera for the demo video')
    p.add_argument('--startup-timeout', type=int, default=480)
    p.add_argument('--mission-timeout', type=int, default=900)
    args = p.parse_args(argv)
    if args.startup_timeout < 5 or args.mission_timeout < 10:
        p.error('timeouts too short')
    from rescuemind.scene_variants import audit_scenarios
    from rescuemind.gazebo_transport_contract import validate_static
    audit_scenarios(ROOT/'worlds/scenarios')
    validate_static(ROOT/'worlds/scenarios'/('rescuemind_'+args.scene+'.sdf'), ROOT/'configs/ros_gz_bridge_v20.yaml')
    robust = args.lighting != 'default' or args.hazard_at or args.distractor_at
    def make_world(dest_dir):
        if not robust:
            return None
        from rescuemind.robust_scenes import write_variant
        w = write_variant(ROOT/'worlds/scenarios', dest_dir, args.scene, lighting=args.lighting,
                          distractor_at=args.distractor_at, hazard_at=args.hazard_at)
        validate_static(w, ROOT/'configs/ros_gz_bridge_v20.yaml')
        return w
    extra = dict(recovery=args.recovery, explain=args.explain, prompt_set=args.prompt_set, model=args.model,
                 intent_backend=args.intent_backend)
    placeholder=ROOT/'outputs'/'runs'/'<run_id>'
    plan = build_plan(args.scenario, args.instruction, mission_timeout=args.mission_timeout, scene=args.scene,
                      evidence_dir=placeholder, capture_rosbag=args.capture_rosbag,local_mode=args.local_mode,
                      gz_mode=args.gz_mode, film=args.film, **extra)
    import hashlib
    scene_path = ROOT/'worlds/scenarios'/('rescuemind_'+args.scene+'.sdf')
    scene_sha256=hashlib.sha256(scene_path.read_bytes()).hexdigest()
    summary = {'scenario': plan['scenario'], 'scene': plan['scene'], 'scene_sha256': scene_sha256, 'services': [list(x.argv) for x in plan['services']],
               'readiness': list(plan['readiness']), 'mission': list(plan['mission'].argv),
               'capture_rosbag': args.capture_rosbag,'local_mode':args.local_mode,'cloud_api_used':False,
               'notes':'Plan is not execution proof. Vision is ON-DEVICE Qwen2.5-VL-3B (optional second SmolVLM2). Old cloud/Jev code stays in scripts/v31_orchestrate.py; no cloud API is used here.'}
    if args.plan:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    run_id = uuid.uuid4().hex[:16]
    log_dir = ROOT/'outputs'/'runs'/run_id
    log_dir.mkdir(parents=True, exist_ok=False)
    run_world = make_world(log_dir)
    plan = build_plan(args.scenario, args.instruction, mission_timeout=args.mission_timeout, scene=args.scene, evidence_dir=log_dir,
                      world=run_world, **extra,
                      capture_rosbag=args.capture_rosbag,local_mode=args.local_mode,gz_mode=args.gz_mode,
                      film=args.film)
    summary['world_variant'] = {'lighting': args.lighting, 'hazard_at': args.hazard_at,
                                'distractor_at': args.distractor_at, 'sdf': run_world.name if run_world else None}
    summary['recovery'] = args.recovery
    summary['explain'] = args.explain
    summary['prompt_set'] = args.prompt_set
    summary['model'] = args.model or 'Qwen/Qwen2.5-VL-3B-Instruct'
    summary['intent_backend'] = args.intent_backend
    # Replace every planning placeholder with the actual run ID, including
    # independent recorder / bag paths, not just mission output paths.
    summary['run_id'] = run_id
    summary['services'] = [list(x.argv) for x in plan['services']]
    summary['readiness'] = list(plan['readiness'])
    summary['mission'] = list(plan['mission'].argv)
    (log_dir/'stack_plan.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    outcome = {'run_id': run_id, 'scenario': args.scenario, 'scene': args.scene, 'state': 'FAILED', 'error': None,
               'scope': 'unverified live LOCAL CUDA model + ROS/Gazebo runtime if executed on Ubuntu'}
    import signal as _signal
    def _graceful(signum, _frame):
        # Turn SIGTERM into an exception so `with Supervisor` tears the stack down.
        raise StackFailure(f'orchestrator received signal {signum}; stack torn down')
    _signal.signal(_signal.SIGTERM, _graceful)
    try:
        check_prerequisites(args.scenario, capture_rosbag=args.capture_rosbag)
        quiet = subprocess.run(shell_exec(['python3', str(ROOT/'scripts/stack_quiescence.py'), '--wait', '45']),
                               capture_output=True, text=True, timeout=120)
        (log_dir/'preflight_quiescence.json').write_text(quiet.stdout)
        if quiet.returncode != 0:
            raise StackFailure('stale ROS/Gazebo stack already running (another /cmd_vel publisher or world); refuse to start')
        with Supervisor(log_dir) as sup:
            for spec in plan['services']:
                sup.start_service(spec)
                time.sleep(1.)
                sup.ensure_alive()
            def probe():
                if args.scenario=='live':
                    import urllib.request
                    from rescuemind.local_vision import PRIMARY_MODEL,SECONDARY_MODEL
                    for port,model in ([(8765,args.model or PRIMARY_MODEL)] + ([(8766,SECONDARY_MODEL)] if args.local_mode=='dual' else [])):
                        try:
                            with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/health',timeout=3) as f:
                                h=json.load(f)
                            if h.get('status')!='ready' or h.get('model')!=model:
                                return False
                        except (OSError,ValueError,KeyError):
                            return False
                try:
                    r = subprocess.run(plan['readiness'], capture_output=True, text=True, timeout=52)
                    (log_dir/'readiness_last.txt').write_text(r.stdout + '\nSTDERR\n' + r.stderr)
                    return r.returncode == 0
                except subprocess.TimeoutExpired:
                    return False
            sup.wait_readiness(probe, args.startup_timeout, interval_s=2.)
            # Intentional AI denial exits nonzero. Do NOT let that exit skip
            # rosbag2 SIGINT finalization: both successful arrival and a
            # completed 2.5s denial dwell require a closed evidence recording.
            deferred_denial = None
            try:
                sup.run_mission(plan['mission'], plan['mission_timeout'])
            except StackFailure as mission_error:
                if (args.scenario == 'live' and (args.scene in ('swapped', 'empty') or args.hazard_at)
                        and str(mission_error).startswith('mission failed (exit=')):
                    deferred_denial = mission_error
                else:
                    raise
            # Finalize recorder while Gazebo, guard, and odom evidence recorder
            # are still supervised. Never classify a denial successful if
            # recorder termination itself failed or was force-killed.
            if args.capture_rosbag:
                outcome['rosbag_finalization'] = sup.stop_service('rosbag_recorder')
            if deferred_denial is not None:
                raise deferred_denial
            from rescuemind.run_completion import validate, CompletionError
            try:
                outcome['receipt']=validate(log_dir/'mission.json',args.scenario,run_id)
            except CompletionError as e:
                raise StackFailure('mission exit 0 but completion receipt invalid: '+str(e)) from e
            from rescuemind.runtime_guard_graph import audit_watch_jsonl
            outcome['runtime_guard_graph_evidence']=audit_watch_jsonl(log_dir/'guard_graph_watch.jsonl')
            if args.scenario == 'live':
                from rescuemind.v26_stationary_evidence import audit_stationarity
                outcome['stationary_camera_evidence']=audit_stationarity(log_dir/'mission.json')
                from rescuemind.v27_image_evidence import audit_capture
                outcome['image_acquisition_evidence']=audit_capture(log_dir/'mission.json',log_dir/'checkpoint.jpg')
                from rescuemind.v28_clock_evidence import audit_clock_capture
                outcome['gazebo_camera_clock_evidence']=audit_clock_capture(log_dir/'mission.json')
            # A successful mission-owned JSON receipt is insufficient for an award
            # claim. Require independently subscribed /odom and /cmd_vel traces.
            from rescuemind.motion_evidence import audit_motion, MotionEvidenceError
            mission_record=json.loads((log_dir/'mission.json').read_text(encoding='utf8'))
            item=mission_record.get('intent',{}).get('item')
            config=json.loads((ROOT/'configs/gazebo_waypoints.json').read_text())
            if item not in ('water','medicine'):
                raise StackFailure('motion evidence: invalid supply item')
            # I-02: after a recovery search the authorising checkpoint is at the OTHER station.
            station_name=mission_record.get('checkpoint_station') or item
            if station_name not in ('water','medicine'):
                raise StackFailure('motion evidence: invalid checkpoint station')
            if mission_record.get('recovery'):
                from rescuemind.recovery_evidence import audit_recovery
                outcome['recovery_evidence']=audit_recovery(mission_record,log_dir,completed=True)
            # The observer runs asynchronously: give the final odometry sample
            # up to 1.5 seconds to reach the separate subscriber, never assume
            # process exit means physical movement was observed.
            last_error=None
            for attempt in range(11):
                sup.ensure_alive()
                try:
                    outcome['independent_motion_evidence']=audit_motion(
                        log_dir/'independent_ros_topics.jsonl',run_id=run_id,
                        station=config[station_name],shelter=config['B'])
                    break
                except (MotionEvidenceError,OSError,ValueError) as e:
                    last_error=e
                    if attempt<10: time.sleep(.15)
            else:
                raise StackFailure('mission receipt passed but independent ROS movement evidence failed: '+str(last_error)) from last_error
            from rescuemind.ground_truth_evidence import audit_ground_truth, GroundTruthError
            try:
                outcome['ground_truth_evidence']=audit_ground_truth(
                    log_dir/'independent_ros_topics.jsonl',station=config[station_name],shelter=config['B'],
                    expect_arrival=True)
            except (GroundTruthError,OSError,ValueError,KeyError) as exc:
                raise StackFailure('Gazebo ground-truth audit failed: '+str(exc)) from exc
            if args.scenario == 'live':
                # Distinguish physical trajectory from authorization chronology.
                from rescuemind.causal_evidence import audit_causal, CausalEvidenceError
                try:
                    outcome['authorization_motion_chronology'] = audit_causal(
                        log_dir/'mission.json', log_dir/'independent_ros_topics.jsonl',
                        station=config[station_name], shelter=config['B'])
                except (CausalEvidenceError, ValueError, OSError) as exc:
                    raise StackFailure('AI authorization/movement chronology failed: '+str(exc)) from exc
            outcome['state'] = 'COMPLETED'
    except KeyboardInterrupt:
        outcome['error'] = 'KeyboardInterrupt: aborted by operator; stack torn down'
        print(outcome['error'], file=sys.stderr)
        return_code = 130
    except (StackFailure, OSError, RuntimeError) as e:
        outcome['error'] = f'{type(e).__name__}: {e}'
        print(outcome['error'], file=sys.stderr)
        return_code = 2
        # Expected AI rejection in swapped/empty is a valid experimental
        # outcome ONLY when the independent ROS evidence proves the robot
        # stayed at the station after the explicitly logged denial.
        if (args.scenario=='live' and (args.scene in ('swapped','empty') or args.hazard_at)
                and isinstance(e,StackFailure)
                and str(e).startswith('mission failed (exit=')):
            try:
                from rescuemind.runtime_guard_graph import audit_watch_jsonl
                outcome['runtime_guard_graph_evidence']=audit_watch_jsonl(log_dir/'guard_graph_watch.jsonl')
                from rescuemind.v24_trial_outcome import classify_negative_run
                config=json.loads((ROOT/'configs/gazebo_waypoints.json').read_text())
                from rescuemind.v26_stationary_evidence import audit_stationarity
                outcome['stationary_camera_evidence']=audit_stationarity(log_dir/'mission.json')
                from rescuemind.v27_image_evidence import audit_capture
                outcome['image_acquisition_evidence']=audit_capture(log_dir/'mission.json',log_dir/'checkpoint.jpg')
                from rescuemind.v28_clock_evidence import audit_clock_capture
                outcome['gazebo_camera_clock_evidence']=audit_clock_capture(log_dir/'mission.json')
                denied=json.loads((log_dir/'mission.json').read_text(encoding='utf8'))
                denied_item=denied['intent']['item']
                final_station=denied.get('checkpoint_station') or denied_item
                waypoints=dict(config); waypoints[denied_item]=config[final_station]
                negative=classify_negative_run(log_dir,scene='hazard' if args.hazard_at else args.scene,
                                               run_id=run_id,waypoints=waypoints)
                outcome['expected_denial']=negative
                if denied.get('recovery'):
                    from rescuemind.recovery_evidence import audit_recovery
                    outcome['recovery_evidence']=audit_recovery(denied,log_dir,completed=False)
                from rescuemind.ground_truth_evidence import audit_ground_truth
                outcome['ground_truth_evidence']=audit_ground_truth(
                    log_dir/'independent_ros_topics.jsonl',station=config[final_station],shelter=config['B'],
                    expect_arrival=False)
                # If a rosbag was specifically requested, it is evidence
                # required even for a deliberately denied mission.
                if args.capture_rosbag:
                    from rescuemind.bag_evidence import audit_bag_metadata
                    receipt=outcome.get('rosbag_finalization')
                    if (not isinstance(receipt, dict) or
                            receipt.get('process_finished_before_metadata_audit') is not True):
                        raise ValueError('denial rosbag not gracefully finalized')
                    outcome['rosbag_evidence']=audit_bag_metadata(log_dir/'rosbag2',require_clock=True)
                outcome['state']='COMPLETED_EXPECTED_DENIAL'
                outcome['error']=None
                return_code=0
            except (ValueError,OSError,KeyError,TypeError,RuntimeError) as denial_error:
                outcome['negative_evidence_failure']=str(denial_error)
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
