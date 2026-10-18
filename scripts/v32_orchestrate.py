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


WORLD_SPEC_KEYS = {'lighting_params', 'prop_offsets', 'hazard_at', 'hazard_geom', 'distractor_at',
                   'distractor_kind', 'distractor_side', 'distractor_layout', 'layout', 'depot'}


def waypoint_config_path(log_dir: Path) -> Path:
    """Study L: a run with a per-trial layout audits against ITS OWN waypoints.json in the run folder;
    every other run keeps the fixed configs/gazebo_waypoints.json."""
    own = Path(log_dir)/'waypoints.json'
    return own if own.is_file() else ROOT/'configs/gazebo_waypoints.json'


def can_raise_priority() -> bool:
    """True if this process may lower niceness (docker --cap-add SYS_NICE, no sudo needed)."""
    try:
        r = subprocess.run(['nice', '-n', '-10', 'true'], capture_output=True, text=True, timeout=5)
        return r.returncode == 0 and not r.stderr.strip()
    except (OSError, subprocess.TimeoutExpired):
        return False


def prioritised(argv: tuple[str, ...], niceness: int) -> tuple[str, ...]:
    """I-09: on a CPU-saturated 4-core host the control loops must not be starved.
    Negative niceness only when permitted; positive (lower priority) always allowed."""
    if niceness < 0 and not PRIORITY_OK:
        return argv
    return ('nice', '-n', str(niceness)) + tuple(argv)


PRIORITY_OK = can_raise_priority()


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
               prompt_set: str = 'v33', model: str | None = None, intent_backend: str = 'tfidf',
               intent_prompt: str = 'i34', describe_prompt: str = 'e0', inject_stall: float = 0.0,
               hazard_threshold: float = 0.5, control_qos: str = 'reliable', hazard_views: str = 'full',
               hazard_prompt: str = 'h35', jev_local: str = 'off', jev_hazard_threshold: float = .35, jev_schema: str = 'jev',
               look_around: float = 0.0, memory_file: str | None = None, memory_mode: str = 'off', adaptive_views: float = 0.0,
               advice_file: str | None = None, advice_mode: str = 'off', advice_from_instruction: bool = False,
               caution_soft: bool = False, advice_scrutiny: bool = False, advice_credit: str | None = None,
               delivery_interlock: bool = False, interlock_key: str | None = None,
               config_path: Path | None = None, centers_path: Path | None = None) -> dict:
    if scenario not in ('motion-check', 'live'):
        raise ValueError('invalid scenario')
    from rescuemind.scene_variants import SCENES
    if scene not in SCENES:
        raise ValueError('unknown experiment scene')
    script = str(ROOT/'ros/gazebo_waypoint_mission.py')
    cmd = ['python3', script, '--motion-check'] if scenario == 'motion-check' else \
          ['python3', script, '--run-live', '--instruction', instruction]
    cmd += ['--stage-timeout', '120', '--control-qos', control_qos]
    if config_path is not None:
        cmd += ['--config', str(config_path)]       # Study L: per-run waypoints
    if centers_path is not None:
        cmd += ['--centers', str(centers_path)]     # Study L: per-run station centres
    cmd += ['--expected-hazard-threshold', str(hazard_threshold)]     # I-19 #27: the mission checks the server's tau_h
    if look_around:
        cmd += ['--look-around', str(look_around)]
    if adaptive_views:
        cmd += ['--adaptive-views', str(adaptive_views)]     # I-20 (tau_sus and near keep their defaults)
    if memory_file:
        cmd += ['--memory-file', str(memory_file), '--memory-mode', memory_mode]
    if advice_file or advice_from_instruction:      # I-19: advice from a file (peer/inventory/memory) and/or the instruction text
        cmd += ['--advice-mode', advice_mode]
        if advice_file:
            cmd += ['--advice-file', str(advice_file)]
        if advice_from_instruction:
            cmd += ['--advice-from-instruction']
    if caution_soft:
        cmd += ['--caution-soft']                            # R5 #5: caution-only refusals continue the search
    if advice_scrutiny:
        cmd += ['--advice-scrutiny']                         # I-19: advice-promoted station gets caution + extra views
    if advice_credit:
        cmd += ['--advice-credit', str(advice_credit)]       # I-24: per-source credit ledger (read here, settled after)
    if delivery_interlock:
        cmd += ['--delivery-interlock']                      # I-22: ask the independent interlock before the delivery leg
    if inject_stall:
        cmd += ['--inject-warmup-stall', str(inject_stall)]
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
        ManagedCommand('velocity_guard', prioritised(('bash', str(ROOT/'scripts/start_velocity_guard.sh')), -10)),
    ]
    if delivery_interlock:
        if scenario != 'live':
            raise ValueError('the delivery interlock needs the live scenario')
        # I-22: separate node, started right after the guard (which is told --delivery-interlock through RESCUEMIND_GUARD_ARGS)
        il = ['python3', str(ROOT/'ros/delivery_interlock.py')]
        if interlock_key:
            il += ['--key-file', interlock_key]
        if evidence_dir is not None:
            il += ['--log', str(evidence_dir/'delivery_interlock.jsonl'), '--image-root', str(evidence_dir)]
        il += ['--hazard-threshold', str(hazard_threshold)]
        if look_around:
            il += ['--require-look-around']
        if adaptive_views:
            il += ['--require-adaptive']
        services.append(ManagedCommand('delivery_interlock', shell_exec(il)))
    if scenario=='live':
        from rescuemind.local_vision import PRIMARY_MODEL, SECONDARY_MODEL
        services.insert(0,ManagedCommand('primary_local_vlm', shell_exec([
            'python3',str(ROOT/'scripts/local_vlm_server.py'),'--model',model or PRIMARY_MODEL,'--port','8765',
            '--prompt-set',prompt_set,'--intent-prompt',intent_prompt,'--describe-prompt',describe_prompt,
            '--hazard-threshold',str(hazard_threshold),'--hazard-views',hazard_views,'--hazard-prompt',hazard_prompt])))
        if jev_local == 'clef':
            # I-13: the original plan's Jev role, answered locally by Clef-Flash (Jev/SystemOne API)
            services.insert(1,ManagedCommand('jev_role_clef', shell_exec([
                'python3',str(ROOT/'scripts/clef_server.py'),'--port','8767'])))
            cmd += ['--jev-url','http://127.0.0.1:8767/v1/systemone','--jev-hazard-threshold',str(jev_hazard_threshold),
                    '--jev-schema',jev_schema]
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
        services.append(ManagedCommand('film_recorder', prioritised(shell_exec([
            'python3', str(ROOT/'ros/film_recorder.py'), '--out', str(evidence_dir/'film')]), 15)))
    if capture_rosbag and evidence_dir is not None:
        # NOTE: `nice` carries a file capability (I-09); a capability exec runs in glibc secure
        # mode and strips LD_LIBRARY_PATH, so it must wrap the shell that sources ROS, never
        # sit between the sourced shell and a ROS binary.
        services.append(ManagedCommand('rosbag_recorder', prioritised(shell_exec([
            'ros2', 'bag', 'record', '-o', str(evidence_dir/'rosbag2'), '--use-sim-time', '--topics',
            '/clock', '/odom', '/cmd_vel', '/rescuemind/cmd_vel_request',
            '/camera', '/scan', '/rescuemind/guard_ready', '/ground_truth/odom']), 10)))
    return {
        'scenario': scenario, 'scene': scene,
        'prerequisites': ['Ubuntu 24.04', 'ROS 2 Jazzy + ros_gz_bridge',
                          'Gazebo Harmonic', 'project .venv from setup_ubuntu_jazzy.sh'],
        'services': services,
        'readiness': ('bash', str(ROOT/'scripts/v21_live_readiness.sh')),
        'mission': ManagedCommand('mission', prioritised(shell_exec(cmd), -10)),
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


def memory_denied(log_dir: Path) -> bool:
    try:
        m = json.loads((log_dir/'mission.json').read_text(encoding='utf8'))
    except (OSError, ValueError):
        return False
    return bool((m.get('memory') or {}).get('deny_without_visit')) and any(
        e.get('stage') == 'memory_denial' for e in m.get('events', []))


def caution_refused(log_dir: Path) -> bool:
    """R5 #5: the run contains a recorded caution-only refusal (soft refusal, --caution-soft): its end is an expected denial."""
    try:
        m = json.loads((log_dir/'mission.json').read_text(encoding='utf8'))
    except (OSError, ValueError):
        return False
    return bool(m.get('caution_soft')) and bool(m.get('caution_refusals'))


def memory_trusted_audit(outcome: dict, log_dir: Path, run_id: str, mission: dict, sup) -> None:
    """I-15 naive-memory baseline: the robot skipped the on-site check because memory said the supply was there.
    Only the physical delivery is audited (guard graph, independent odometry, Gazebo ground truth)."""
    from rescuemind.runtime_guard_graph import audit_watch_jsonl
    from rescuemind.motion_evidence import audit_motion, MotionEvidenceError
    from rescuemind.ground_truth_evidence import audit_ground_truth
    from rescuemind.advice import skip_source
    source = skip_source(mission.get('memory'))
    if source is None or (mission.get('checkpoint') or {}).get('trusted_by', 'memory') != source:
        raise StackFailure('trusted delivery outside the naive memory / naive advice baselines')
    config = json.loads(waypoint_config_path(log_dir).read_text())
    station = mission.get('checkpoint_station')
    outcome['runtime_guard_graph_evidence'] = audit_watch_jsonl(log_dir/'guard_graph_watch.jsonl')
    for attempt in range(11):
        sup.ensure_alive()
        try:
            outcome['independent_motion_evidence'] = audit_motion(log_dir/'independent_ros_topics.jsonl', run_id=run_id,
                                                                  station=config[station], shelter=config['B'])
            break
        except (MotionEvidenceError, OSError, ValueError) as e:
            if attempt == 10:
                raise StackFailure('memory-trusted run: independent ROS movement evidence failed: '+str(e)) from e
            time.sleep(.15)
    outcome['ground_truth_evidence'] = audit_ground_truth(log_dir/'independent_ros_topics.jsonl', station=config[station],
                                                          shelter=config['B'], expect_arrival=True)
    outcome['state'] = 'COMPLETED_ADVICE_TRUSTED' if source == 'advice' else 'COMPLETED_MEMORY_TRUSTED'


def denial_by(log_dir: Path) -> str:
    """'advice' or 'memory': who made the naive robot refuse without visiting (from the logged event and plan)."""
    from rescuemind.advice import denial_source
    m = json.loads((log_dir/'mission.json').read_text(encoding='utf8'))
    by = denial_source(m.get('memory'))
    ev = [e.get('by', 'memory') for e in m.get('events', []) if e.get('stage') == 'memory_denial']
    if by is None or not ev or ev[0] != by:
        raise ValueError('refusal without a visit that no naive plan explains')
    return by


def settle_credit(log_dir: Path, ledger_path: str, run_id: str) -> dict:
    """I-24: charge / refund each advice source after the mission, from mission.json alone (the robot's own checks)."""
    from rescuemind import advice_credit as ac
    m = json.loads((log_dir/'mission.json').read_text(encoding='utf8'))
    led = ac.load(ledger_path)
    rec = ac.settle(led, m.get('memory') or {}, ac.visits_from_mission(m), mission_id=run_id)
    ac.save(led, ledger_path)
    return {'settlement': rec, 'credit': {k: {'loc': v['loc'], 'haz': v['haz']} for k, v in led['sources'].items()}}


def advice_audit(log_dir: Path) -> dict | None:
    """I-19: a monotone run must satisfy advice.assert_monotone(base, plan), recomputed from mission.json, and must
    show no trusted checkpoint and no refusal without a visit.  Raises AdviceError / ValueError.  None if no advice."""
    from rescuemind import advice as adv
    try:
        m = json.loads((log_dir/'mission.json').read_text(encoding='utf8'))
    except (OSError, ValueError):
        return None           # no record (stack failed before the mission wrote it): nothing to audit
    plan = m.get('memory')
    if not (plan or {}).get('advice'):
        return None
    ev = adv.audit_plan(plan)
    ev['scrutiny_run'] = adv.audit_scrutiny(m)
    if 'throttled' in plan['advice']:
        from rescuemind.advice_credit import audit_credit
        ev['credit'] = audit_credit(plan)          # I-24: every item received was acted on or throttled, once
    from rescuemind.caution_soft import audit_caution_refusals
    ev['caution'] = audit_caution_refusals(m)
    if ev.get('mode') == 'monotone':
        if (m.get('checkpoint') or {}).get('trusted_by') == 'advice' or any(
                e.get('stage') in ('memory_denial', 'checkpoint_skipped_by_memory') and e.get('by') == 'advice'
                for e in m.get('events', [])):
            raise adv.AdviceError('monotone run skipped a check or refused without visiting because of advice')
    return ev


def memory_denial_audit(outcome: dict, log_dir: Path) -> None:
    """I-15 naive-memory baseline refused without visiting: prove from Gazebo ground truth that it never left the start."""
    xs = []
    for line in (log_dir/'independent_ros_topics.jsonl').read_text(encoding='utf8').splitlines():
        r = json.loads(line)
        if r.get('kind') == 'ground_truth':
            xs.append((r['x'], r['y']))
    if not xs:
        raise ValueError('no ground-truth samples')
    far = max((x * x + y * y) ** .5 for x, y in xs)
    if far > .5:
        raise ValueError(f'memory denial but the robot moved {far:.2f} m from the start')
    outcome['memory_denial_evidence'] = {'max_distance_from_start_m': round(far, 3), 'n_ground_truth': len(xs)}
    outcome['state'] = 'DENIED_BY_ADVICE' if denial_by(log_dir) == 'advice' else 'DENIED_BY_MEMORY'
    outcome['error'] = None


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
    p.add_argument('--recovery', action=argparse.BooleanOptionalAction, default=True, help='I-02: search the other station if the supply is wrong/missing (v3.6 default on)')
    p.add_argument('--explain', action=argparse.BooleanOptionalAction, default=True, help='I-03: Japanese one-sentence report after each checkpoint (v3.6 default on)')
    p.add_argument('--prompt-set', choices=['v33', 'v34', 'v35'], default='v35', help='VLM checkpoint prompts (v34 = I-05)')
    p.add_argument('--model', default='Qwen/Qwen3.5-9B', help='local VLM model id (I-08)')
    p.add_argument('--intent-backend', choices=['tfidf', 'llm'], default='llm', help='I-04 instruction parser')
    p.add_argument('--intent-prompt', choices=['i34', 'i35', 'i36', 'i37', 'i38'], default='i35')
    p.add_argument('--hazard-threshold', type=float, default=0.05,
                   help='I-10: VLM p(fire/smoke) at or above which the checkpoint refuses (v3.5: 0.05)')
    p.add_argument('--dds-mode', choices=['default', 'async', 'best_effort'], default='async',
                   help='I-12 (v3.5 default: async): default = reliable control topics, synchronous Fast DDS publication; '
                        'async = RMW_FASTRTPS_PUBLICATION_MODE=ASYNCHRONOUS for the whole stack; '
                        'best_effort = best-effort request/heartbeat topics')
    p.add_argument('--adaptive-views', type=float, default=0.0,
                   help='I-20: suspicion-triggered extra views at this side offset (m); 0 = off (v3.6)')
    p.add_argument('--look-around', type=float, default=0.4,
                   help='I-14: after an approval, look again from this far (m) left and right of the station')
    p.add_argument('--memory-file', default=None, help='I-15: cross-mission memory JSONL (read before, appended after)')
    p.add_argument('--memory-mode', choices=['off', 'verified', 'naive'], default='off',
                   help='I-15: verified = memory proposes, perception disposes; naive = trust memory (baseline only)')
    p.add_argument('--advice-file', default=None, help='I-19: JSON list of advice items (peer / inventory / memory claims)')
    p.add_argument('--advice-mode', choices=['off', 'monotone', 'naive', 'filtered'], default='off',
                   help='I-19: monotone = advice may only reorder and tighten; naive = follow advice; '
                        'filtered = follow advice that an LLM injection filter does not flag (baselines only)')
    p.add_argument('--caution-soft', action='store_true',
                   help='R5 #5: a refusal caused ONLY by memory / advice caution (tau_mem <= p(hazard) < tau_h) does not stop the '
                        'mission: no delivery from that station, search the next candidate (default off: v3.6)')
    p.add_argument('--advice-scrutiny', action='store_true',
                   help='I-19: the station that advice moved to the front gets caution (tau_h = caution threshold) and the I-20 '
                        'extra views regardless of suspicion (monotone mode only; can only tighten)')
    p.add_argument('--advice-credit', default=None,
                   help='I-24: per-source advice-credit ledger (JSON, kept across missions): advice whose worst cost the '
                        'source can no longer pay is dropped (monotone mode only; dropping advice never loosens a check); '
                        'settled after the mission from the robot\'s own checks')
    p.add_argument('--delivery-interlock', action='store_true',
                   help='I-22 (default off; v3.6 unchanged): an independent node recomputes the decision from the saved model outputs '
                        'and the velocity guard forwards motion in the delivery leg only with its permit')
    p.add_argument('--interlock-hmac', action=argparse.BooleanOptionalAction, default=True,
                   help='I-22: sign permits with a key generated at stack start (0600, outside the evidence directory)')
    p.add_argument('--advice-from-instruction', action='store_true',
                   help='I-19: extract operator advice from the instruction text (closed-set, fail-closed)')
    p.add_argument('--jev-local', choices=['off', 'clef'], default='off',
                   help='I-13: add the Jev-role model (Clef-Flash, local) - both models must approve')
    p.add_argument('--jev-hazard-threshold', type=float, default=.35)
    p.add_argument('--jev-schema', choices=['jev', 'task'], default='jev',
                   help='I-16: ask the Jev-role model the original Jev request or the task-worded request (T2: task)')
    p.add_argument('--hazard-views', choices=['full', 'tiles'], default='tiles', help='I-11: hazard question on crops too')
    p.add_argument('--hazard-prompt', choices=['h35', 'h36'], default='h36', help='I-11: hazard question wording')
    p.add_argument('--inject-warmup-stall', type=float, default=0.0, help='I-09 fault injection (A/B tests only)')
    p.add_argument('--describe-prompt', choices=['e0', 'e1', 'e2'], default='e0')
    p.add_argument('--lighting', choices=['default', 'dim_evening', 'harsh_noon'], default='default')
    p.add_argument('--hazard-at', choices=['water', 'medicine'], default=None, help='I-05: fire behind this station')
    p.add_argument('--distractor-at', choices=['water', 'medicine'], default=None, help='I-05: cardboard box at this station')
    p.add_argument('--world-spec', default=None,
                   help='JSON object of randomised-world parameters for build_variant (campaign E); '
                        'its hazard_at / distractor_at also drive the audits')
    p.add_argument('--film', action='store_true',
                   help='also record a Gazebo-rendered overview camera for the demo video')
    p.add_argument('--no-operator-report', action='store_true',
                   help='I-18: skip the operator_report.png/pdf normally generated after every run')
    p.add_argument('--startup-timeout', type=int, default=480)
    p.add_argument('--mission-timeout', type=int, default=900)
    args = p.parse_args(argv)
    if args.startup_timeout < 5 or args.mission_timeout < 10:
        p.error('timeouts too short')
    from rescuemind.scene_variants import audit_scenarios
    from rescuemind.gazebo_transport_contract import validate_static
    audit_scenarios(ROOT/'worlds/scenarios')
    validate_static(ROOT/'worlds/scenarios'/('rescuemind_'+args.scene+'.sdf'), ROOT/'configs/ros_gz_bridge_v20.yaml')
    world_spec = json.loads(args.world_spec) if args.world_spec else None
    layout = None
    if world_spec is not None:
        if not isinstance(world_spec, dict) or set(world_spec) - WORLD_SPEC_KEYS:
            p.error(f'--world-spec keys must be within {sorted(WORLD_SPEC_KEYS)}')
        if args.hazard_at or args.distractor_at or args.lighting != 'default':
            p.error('--world-spec replaces --lighting/--hazard-at/--distractor-at')
        args.hazard_at = world_spec.get('hazard_at')
        args.distractor_at = world_spec.get('distractor_at')
        if world_spec.get('layout') is not None:
            from rescuemind.layout import Layout
            try:
                layout = Layout.from_dict(world_spec['layout'])
            except ValueError as e:
                p.error(f'--world-spec layout invalid: {e}')
    depot_k4 = bool(world_spec and (world_spec.get('depot') or {}).get('stations') == 4)
    if depot_k4 and layout is not None:
        p.error('--world-spec: a Study L layout and the four-station depot cannot be combined')
    robust = args.lighting != 'default' or args.hazard_at or args.distractor_at or world_spec is not None
    def make_world(dest_dir):
        if not robust:
            return None
        from rescuemind.robust_scenes import write_variant
        if world_spec is not None:
            kw = dict(world_spec)
            if 'layout' in kw:
                from rescuemind.layout import Layout
                kw['layout'] = Layout.from_dict(kw['layout'])
            if 'hazard_geom' in kw:
                kw['hazard_geom'] = tuple(kw['hazard_geom'])
            w = write_variant(ROOT/'worlds/scenarios', dest_dir, args.scene, **kw)
        else:
            w = write_variant(ROOT/'worlds/scenarios', dest_dir, args.scene, lighting=args.lighting,
                              distractor_at=args.distractor_at, hazard_at=args.hazard_at)
        validate_static(w, ROOT/'configs/ros_gz_bridge_v20.yaml')
        return w
    extra = dict(recovery=args.recovery, explain=args.explain, prompt_set=args.prompt_set, model=args.model,
                 intent_backend=args.intent_backend, intent_prompt=args.intent_prompt,
                 describe_prompt=args.describe_prompt, inject_stall=args.inject_warmup_stall,
                 hazard_threshold=args.hazard_threshold, hazard_views=args.hazard_views,
                 hazard_prompt=args.hazard_prompt, jev_local=args.jev_local, look_around=args.look_around, adaptive_views=args.adaptive_views,
                 jev_hazard_threshold=args.jev_hazard_threshold, jev_schema=args.jev_schema,
                 memory_file=args.memory_file, memory_mode=args.memory_mode,
                 advice_file=args.advice_file, advice_mode=args.advice_mode,
                 advice_from_instruction=args.advice_from_instruction,
                 caution_soft=args.caution_soft, advice_scrutiny=args.advice_scrutiny,
                 advice_credit=args.advice_credit,
                 control_qos='best_effort' if args.dds_mode == 'best_effort' else 'reliable')
    if args.dds_mode == 'async':
        os.environ['RMW_FASTRTPS_PUBLICATION_MODE'] = 'ASYNCHRONOUS'
    if args.dds_mode == 'best_effort':
        os.environ['RESCUEMIND_GUARD_ARGS'] = (os.environ.get('RESCUEMIND_GUARD_ARGS', '') + ' --control-qos best_effort').strip()
    placeholder=ROOT/'outputs'/'runs'/'<run_id>'
    plan = build_plan(args.scenario, args.instruction, mission_timeout=args.mission_timeout, scene=args.scene,
                      evidence_dir=placeholder, capture_rosbag=args.capture_rosbag,local_mode=args.local_mode,
                      gz_mode=args.gz_mode, film=args.film, **extra,
                      delivery_interlock=args.delivery_interlock,
                      interlock_key='<interlock_key>' if (args.delivery_interlock and args.interlock_hmac) else None,
                      **(dict(config_path=placeholder/'waypoints.json', centers_path=placeholder/'station_centers.json')
                         if (layout is not None or depot_k4) else {}))
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
    interlock_key = None
    interlock_keydir = None
    if args.delivery_interlock:
        # I-22: fresh key per stack start, in a private directory (not in the evidence bundle); the guard and the interlock
        # read it, the mission node is not given the path
        import tempfile
        from rescuemind import delivery_permit as _dp
        if args.interlock_hmac:
            interlock_keydir = tempfile.mkdtemp(prefix='rm_interlock_')
            interlock_key = str(Path(interlock_keydir)/'permit.key')
            _dp.generate_key(interlock_key)
        os.environ['RESCUEMIND_GUARD_ARGS'] = (os.environ.get('RESCUEMIND_GUARD_ARGS', '') + ' --delivery-interlock'
                                               + (f' --permit-key-file {interlock_key}' if interlock_key else '')).strip()
    run_world = make_world(log_dir)
    layout_files = layout.write_configs(log_dir) if layout is not None else (None, None)
    if depot_k4:        # I-21 phase 2: the four-station depot audits against ITS OWN waypoints (station ids + inventory)
        from rescuemind.depot import write_k4_configs
        layout_files = write_k4_configs(log_dir)
    if args.delivery_interlock:
        # I-22: the guard derives the shelter geofence from the same per-run waypoints file the run audits against
        os.environ['RESCUEMIND_GUARD_ARGS'] += ' --geofence-config ' + str(waypoint_config_path(log_dir))
    plan = build_plan(args.scenario, args.instruction, mission_timeout=args.mission_timeout, scene=args.scene, evidence_dir=log_dir,
                      world=run_world, config_path=layout_files[0], centers_path=layout_files[1], **extra,
                      delivery_interlock=args.delivery_interlock, interlock_key=interlock_key,
                      capture_rosbag=args.capture_rosbag,local_mode=args.local_mode,gz_mode=args.gz_mode,
                      film=args.film)
    summary['world_variant'] = {'lighting': args.lighting, 'hazard_at': args.hazard_at,
                                'distractor_at': args.distractor_at, 'sdf': run_world.name if run_world else None,
                                'world_spec': world_spec}
    summary['recovery'] = args.recovery
    summary['explain'] = args.explain
    summary['prompt_set'] = args.prompt_set
    summary['model'] = args.model or 'Qwen/Qwen2.5-VL-3B-Instruct'
    summary['intent_backend'] = args.intent_backend
    summary['intent_prompt'] = args.intent_prompt
    summary['hazard_threshold'] = args.hazard_threshold
    summary['dds_mode'] = args.dds_mode
    summary['jev_local'] = args.jev_local
    summary['look_around'] = args.look_around
    summary['adaptive_views'] = args.adaptive_views
    summary['memory_file'] = args.memory_file
    summary['memory_mode'] = args.memory_mode
    summary['advice_file'] = args.advice_file
    summary['advice_mode'] = args.advice_mode
    summary['caution_soft'] = args.caution_soft
    summary['advice_scrutiny'] = args.advice_scrutiny
    summary['delivery_interlock'] = {'enabled': args.delivery_interlock, 'hmac': bool(interlock_key)}
    summary['advice_from_instruction'] = args.advice_from_instruction
    summary['jev_hazard_threshold'] = args.jev_hazard_threshold
    summary['jev_schema'] = args.jev_schema
    summary['hazard_views'] = args.hazard_views
    summary['hazard_prompt'] = args.hazard_prompt
    summary['describe_prompt'] = args.describe_prompt
    summary['control_priority_raised'] = PRIORITY_OK
    summary['guard_args'] = os.environ.get('RESCUEMIND_GUARD_ARGS', '')
    summary['inject_warmup_stall'] = args.inject_warmup_stall
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
    return_code = 2        # overwritten on every normal path; keeps the finally block (advice audit) well-defined
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
                    for port,model in ([(8765,args.model or PRIMARY_MODEL)] + ([(8766,SECONDARY_MODEL)] if args.local_mode=='dual' else [])
                                       + ([(8767,'Cloudflare/clef-flash')] if args.jev_local=='clef' else [])):
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
                if (args.scenario == 'live' and (args.scene in ('swapped', 'empty') or args.hazard_at or memory_denied(log_dir) or caution_refused(log_dir))
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
            mrec=json.loads((log_dir/'mission.json').read_text(encoding='utf8'))
            if (mrec.get('checkpoint') or {}).get('memory_trusted'):
                # I-15 NAIVE-MEMORY BASELINE: no checkpoint to audit (it was skipped); prove only the motion
                memory_trusted_audit(outcome, log_dir, run_id, mrec, sup)
            else:
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
                config=json.loads(waypoint_config_path(log_dir).read_text())
                if item not in ('water','medicine'):
                    raise StackFailure('motion evidence: invalid supply item')
                # I-02: after a recovery search the authorising checkpoint is at the OTHER station.
                station_name=mission_record.get('checkpoint_station') or item
                from rescuemind.stations import StationSet
                if station_name not in StationSet.from_config(config).ids:     # I-21: k stations (the arena: water / medicine)
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
        if (args.scenario=='live' and memory_denied(log_dir) and isinstance(e,StackFailure)
                and str(e).startswith('mission failed (exit=')):
            try:
                memory_denial_audit(outcome, log_dir)
                return_code=0
            except (ValueError,OSError,KeyError,TypeError,RuntimeError) as denial_error:
                outcome['negative_evidence_failure']=str(denial_error)
        elif (args.scenario=='live' and (args.scene in ('swapped','empty') or args.hazard_at or caution_refused(log_dir))
                and isinstance(e,StackFailure)
                and str(e).startswith('mission failed (exit=')):
            try:
                from rescuemind.runtime_guard_graph import audit_watch_jsonl
                outcome['runtime_guard_graph_evidence']=audit_watch_jsonl(log_dir/'guard_graph_watch.jsonl')
                from rescuemind.v24_trial_outcome import classify_negative_run
                config=json.loads(waypoint_config_path(log_dir).read_text())
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
                negative=classify_negative_run(log_dir,scene='hazard' if args.hazard_at else ('caution' if args.scene=='nominal' else args.scene),
                                               run_id=run_id,waypoints=waypoints)
                outcome['expected_denial']=negative
                if denied.get('recovery'):
                    from rescuemind.recovery_evidence import audit_recovery
                    outcome['recovery_evidence']=audit_recovery(denied,log_dir,completed=False)
                from rescuemind.ground_truth_evidence import audit_ground_truth
                outcome['ground_truth_evidence']=audit_ground_truth(
                    log_dir/'independent_ros_topics.jsonl',station=config[final_station],shelter=config['B'],
                    expect_arrival=False, look_around_m=max(float((denied.get('look_around') or {}).get('offset_m', 0.0)),
                                     float(((denied.get('look_around') or {}).get('adaptive') or {}).get('offset_m', 0.0)) if ((denied.get('look_around') or {}).get('adaptive') or {}).get('triggered') else 0.0))
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
        if args.delivery_interlock:
            # I-22: what the interlock decided; a delivered mission without a logged permit fails the run
            from rescuemind.delivery_interlock import summarise_log
            outcome['delivery_interlock'] = summarise_log(log_dir/'delivery_interlock.jsonl')
            if (str(outcome.get('state', '')).startswith('COMPLETED') and outcome['state'] != 'COMPLETED_EXPECTED_DENIAL'
                    and outcome['delivery_interlock']['permits'] == 0):
                outcome['state'] = 'FAILED'
                outcome['error'] = 'delivery completed without a logged interlock permit'
                if return_code in (0, None):
                    return_code = 2
            if interlock_keydir:
                shutil.rmtree(interlock_keydir, ignore_errors=True)
        if args.advice_file or args.advice_from_instruction:
            # I-19: recompute advice monotonicity from the logged plan; a violation fails the run
            try:
                outcome['advice_audit'] = advice_audit(log_dir)
            except Exception as exc:          # AdviceError, ValueError, KeyError ...
                outcome['advice_audit_failure'] = f'{type(exc).__name__}: {exc}'
                outcome['state'] = 'FAILED'
                outcome['error'] = 'advice monotonicity audit failed: ' + str(exc)
                if return_code in (0, None):
                    return_code = 2
            if args.advice_credit and outcome.get('advice_audit') is not None and not outcome.get('advice_audit_failure'):
                # I-24: settle the credit of every source from what the robot itself saw at each station
                try:
                    outcome['advice_credit'] = settle_credit(log_dir, args.advice_credit, run_id)
                except Exception as exc:
                    outcome['advice_credit_failure'] = f'{type(exc).__name__}: {exc}'
                    outcome['state'] = 'FAILED'
                    outcome['error'] = 'advice credit settlement failed: ' + str(exc)
                    if return_code in (0, None):
                        return_code = 2
        if args.memory_file:
            # I-15: remember what the robot itself saw (never ground truth), whatever the outcome
            try:
                from rescuemind.mission_memory import MissionMemory
                m=json.loads((log_dir/'mission.json').read_text(encoding='utf8'))
                outcome['memory_update']=MissionMemory(args.memory_file).append_mission(m, run_id)
                outcome['memory_plan']=m.get('memory')
            except (OSError,ValueError,KeyError,TypeError) as exc:
                outcome['memory_update_error']=f'{type(exc).__name__}: {exc}'
        if not args.no_operator_report:
            # I-18: non-fatal; rendered from the final in-memory outcome (state + memory_update), before it is written
            try:
                from rescuemind.operator_report_render import generate_for_run
                generate_for_run(log_dir, outcome)
            except Exception as exc:      # e.g. Pillow not installed
                outcome['operator_report_error'] = f'{type(exc).__name__}: {exc}'
        (log_dir/'stack_result.json').write_text(json.dumps(outcome, ensure_ascii=False, indent=2)+'\n')
        print('Stack execution records:', log_dir)
    return return_code


if __name__ == '__main__':
    raise SystemExit(main())
