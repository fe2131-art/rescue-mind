"""Independent Gazebo-Harmonic ROS/GZ bridge *direct drive* experimental lane.

Works independently of Nav2; useful for proving that a Gazebo robot actually
moves, but does not demonstrate Nav2 path planning or true object transport.
--run only after a fresh Jev+Qwen preflight that ALLOWS the mission.
--motion-check runs the motors without models and is explicitly NOT an AI task.

Start worlds/rescuemind_test_arena.sdf; bridge /cmd_vel /odom /scan;
source ROS 2 Jazzy; check odometry-frame calibration and obstacle geometry.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import hashlib
import uuid
import os
from urllib.parse import urlsplit
from threading import Thread
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
SCRUTINY_OFFSET_M=0.8      # side offset of the extra views at a scrutinised station (I-20 default offset)
sys.path.insert(0,str(ROOT))
from rescuemind.mission_policy import decide_intent
from rescuemind.ros_qos import image_qos
from rescuemind.waypoint import Pose2, WaypointController, yaw_from_quaternion
from rescuemind.watchdog import Watchdog
from rescuemind.progress_watch import ProgressWatch
from rescuemind.frame_freshness import FrameSequence
from rescuemind.camera_watch import CameraWatch
from rescuemind.camera_aim import aim_at_station, station_centers
from rescuemind.stationary_gate import StationaryGate, odom_planar_twist, MotionUnstable
from rescuemind.image_acquisition import CheckpointAcquisitionGate
from rescuemind.camera_clock_gate import CameraClockGate, CameraClockRejected
from rescuemind import real_profile as rp      # I-26: opt-in real-robot profile (all off by default)
from rescuemind.stations import StationSet, next_candidate, plan_order


def route_from_config(config_path, item, station=None):
    """Supply station then shelter approach.  `station` (memory / advice / the recovery search) may be any station of
    the config's station set (I-21: k stations; the arena's default is water / medicine)."""
    from rescuemind.stations import StationSet, SUPPLIES
    d=json.loads(Path(config_path).read_text(encoding='utf-8'))
    ss=StationSet.from_config(d)
    if item not in SUPPLIES or (station or ss.catalog(item)) not in ss.ids:
        raise ValueError('unknown supply')
    if d.get('physical_pickup') is not False:
        raise ValueError('expected physical_pickup=false for this prototype')
    station=station or ss.catalog(item)     # I-15: memory may propose visiting another station first (still verified there)
    result=[('supply_station',station,d[station]),('shelter_approach','B',d['B'])]
    for _,_,xy in result:
        if len(xy)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in xy):
            raise ValueError('invalid Gazebo waypoints')
        if any(abs(x)>6 for x in xy):
            raise ValueError('waypoint out of test-arena bounds')
    return result



def load_centers(args):
    """Station centres: the locked default file, or (Study L) the per-run --centers file, shape-checked only."""
    custom=getattr(args,'centers',None)
    path=Path(custom) if custom else ROOT/'configs/gazebo_station_centers.json'
    return station_centers(json.loads(path.read_text(encoding='utf-8')),locked=not custom)


def require_api_configuration(qwen_model: str) -> None:
    """Fail BEFORE first wheel command if the mandatory vision stack cannot run.

    This only checks credentials/configuration, not their validity or API uptime.
    Runtime or inference errors at checkpoint still force a stop.
    """
    if not os.environ.get('TYPESAFE_API_KEY','').strip():
        raise RuntimeError('Jev mandatory: TYPESAFE_API_KEY missing; refuse departure')
    if qwen_model == 'qwen3.8-omni-flash':
        if not os.environ.get('DASHSCOPE_API_KEY','').strip():
            raise RuntimeError('Qwen3.8 mandatory: DASHSCOPE_API_KEY missing; refuse departure')
        url=os.environ.get('DASHSCOPE_BASE_URL','').rstrip('/')
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not (parsed.hostname or '').endswith('.aliyuncs.com') or parsed.username or parsed.password:
            raise RuntimeError('Qwen3.8 needs valid HTTPS Alibaba Cloud workspace base URL before departure')
    elif qwen_model not in ('Qwen/Qwen3.5-4B','Qwen3.5-4B'):
        raise ValueError('unsupported Qwen model for a required Jev+Qwen mission')


def fresh_image(path, max_age=120):
    f=Path(path)
    if not f.is_file() or f.stat().st_size < 300:
        raise RuntimeError(f'camera image absent or empty: {f}')
    age=time.time()-f.stat().st_mtime
    if age < -5 or age > max_age:
        raise RuntimeError(f'camera image stale/future: {f}, age={age:.1f}s')


def SystemClockGateNow():
    # looked up through this module's `time` at call time (the unit tests replace time.time_ns)
    return rp.SystemClockGate(now_ns=lambda: time.time_ns())


def run_ros(route, args, record):
    try:
        import rclpy
        from rclpy.qos import qos_profile_sensor_data
        from geometry_msgs.msg import Twist
        from nav_msgs.msg import Odometry
        from sensor_msgs.msg import LaserScan, Image
        from std_msgs.msg import Bool
        from rosgraph_msgs.msg import Clock
    except ImportError as ex:
        raise RuntimeError('ROS2 not loaded; source /opt/ros/jazzy/setup.bash') from ex
    rclpy.init()
    node=rclpy.create_node('rescuemind_gazebo_waypoint_mission')
    from rescuemind.ros_qos import control_qos
    pub=node.create_publisher(Twist,args.cmd_topic,control_qos(getattr(args,'control_qos','reliable')))
    ctx={'pose':None,'pose_time':None,'odom_twist':None,'frame_msg':None,'frame_time':None, 'guard_ready':False, 'guard_time':None}
    frames=FrameSequence()
    # I-26 (default off): --clock-source system compares the camera stamps with the host's system clock instead of /clock
    clock_source=getattr(args,'clock_source','sim')
    camera_qos=getattr(args,'camera_qos','reliable')
    odom_frame=getattr(args,'odom_frame',None); base_frame=getattr(args,'base_frame',None)
    clock_gate=SystemClockGateNow() if clock_source=='system' else CameraClockGate()
    clock_failure={"reason":None}
    live = record.get('run_type') in ('jev_qwen_live_mission','local_vlm_live_mission')
    soft=bool(getattr(args,'caution_soft',False))      # R5 #5: a caution-only refusal continues the search (default off)
    record['caution_soft']=soft
    hcont=bool(getattr(args,'hazard_continue',False))  # I-42: a REAL hazard refusal continues the search too (default off)
    record['hazard_continue']=hcont
    record['advice_scrutiny']=bool(getattr(args,'advice_scrutiny',False))
    sensor_grace=max(5.,float(getattr(args,'sensor_wait',5.)))
    camera_watch=CameraWatch(started_at=time.monotonic(), max_age_s=getattr(args,'camera_max_age',3.0),
                             startup_grace_s=sensor_grace) if live else None
    watch=Watchdog(started_at=time.monotonic(),min_front_m=args.min_front_m,
                   max_scan_age_s=args.scan_max_age,startup_grace_s=sensor_grace)
    def on_odom(msg):
        if (odom_frame is not None or base_frame is not None) and not rp.odom_frames_ok(msg,odom_frame,base_frame):
            ctx['pose']=None; ctx['odom_twist']=None      # I-26: unexpected odometry frame names -> no pose, latched stop
            watch.latched_reason='invalid_odometry_frames'
            return
        p=msg.pose.pose.position; q=msg.pose.pose.orientation
        try:
            ctx['pose']=Pose2(float(p.x),float(p.y),yaw_from_quaternion(float(q.x),float(q.y),float(q.z),float(q.w)))
            ctx['pose_time']=time.monotonic()
            ctx['odom_twist']=odom_planar_twist(msg)
        except (ValueError, MotionUnstable):
            ctx['pose']=None
            ctx['odom_twist']=None
            watch.latched_reason='invalid_odometry'
    def on_scan(msg):
        watch.update_scan(msg.ranges,msg.angle_min,msg.angle_increment,
                          msg.range_min,msg.range_max,time.monotonic())
    def on_estop(msg):
        watch.emergency_stop(bool(msg.data))
    def on_clock(msg):
        if clock_failure['reason'] is not None:
            return
        try:
            clock_gate.clock(int(msg.clock.sec), int(msg.clock.nanosec), time.monotonic())
        except CameraClockRejected as exc:
            clock_failure['reason']=str(exc)
    def on_camera(msg):
        now=time.monotonic()
        frames.observe(msg)
        if camera_watch is not None:
            camera_watch.observe(msg, now)
        ctx['frame_msg']=msg
        ctx['frame_time']=now
        if clock_source=='system':
            ctx['frame_sys_ns']=time.time_ns()         # I-26: system time at reception (not at the later inspection)
    guard_required=bool(getattr(args,'relay_required',False))
    def on_guard(msg):
        ctx['guard_ready']=bool(msg.data)
        ctx['guard_time']=time.monotonic()
    subs=[node.create_subscription(Odometry,args.odom_topic,on_odom,qos_profile_sensor_data),
          node.create_subscription(LaserScan,args.scan_topic,on_scan,qos_profile_sensor_data),
          node.create_subscription(Bool,args.estop_topic,on_estop,10),
          node.create_subscription(Image,args.camera_topic,on_camera,
                                   image_qos() if camera_qos=='reliable' else image_qos(reliability=camera_qos))]
    if clock_source=='sim':
        subs.append(node.create_subscription(Clock,'/clock',on_clock,qos_profile_sensor_data))
    if guard_required:
        subs.append(node.create_subscription(Bool,'/rescuemind/guard_ready',on_guard,
                                             control_qos(getattr(args,'control_qos','reliable'))))
    # I-22 (default off): publish the mission phase and, before the delivery leg, the approval record; the independent
    # interlock node decides and the velocity guard enforces.  Nothing below is trusted for safety: it only asks.
    interlock=bool(getattr(args,'delivery_interlock',False))
    record['delivery_interlock']={'enabled':interlock}
    il={'phase':'search','raw':None,'last_rec':0.,'permit':None,'phase_pub':None,'record_pub':None,'String':None}
    if interlock:
        from std_msgs.msg import String
        from rescuemind import delivery_permit as dp
        q_il=control_qos('reliable')
        il['String']=String
        il['phase_pub']=node.create_publisher(String,dp.TOPIC_PHASE,q_il)
        il['record_pub']=node.create_publisher(String,dp.TOPIC_RECORD,q_il)
        def on_permit(msg):
            il['permit']=msg.data
        subs.append(node.create_subscription(String,dp.TOPIC_PERMIT,on_permit,q_il))
    def interlock_heartbeat():
        # phase every call (the guard treats a missing / stale phase as 'deliver'); the record once a second while pending
        m=il['String'](); m.data=il['phase']; il['phase_pub'].publish(m)
        if il['raw'] is not None and time.monotonic()-il['last_rec']>=1.0:
            r=il['String'](); r.data=il['raw']; il['record_pub'].publish(r); il['last_rec']=time.monotonic()
    ctl=WaypointController()
    peek_ctl=WaypointController(tolerance=.08)   # I-14: side views must really be beside the station
    progress=ProgressWatch()
    # I-09: instrument gaps between velocity requests (the guard latches after 0.45 s)
    gap_state={'last':None,'phase':'startup','max':0.0}
    import gc
    gc_t={'t0':None}
    def gc_probe(phase, info):
        if phase=='start':
            gc_t['t0']=time.monotonic()
        elif gc_t['t0'] is not None:
            dur=time.monotonic()-gc_t['t0']
            if dur>0.03:
                record['events'].append({'stage':'gc_pause','generation':info.get('generation'),'pause_s':round(dur,3),
                                         'phase':gap_state['phase'],'t_wall_s':round(time.monotonic()-start,3)})
    gc.callbacks.append(gc_probe)
    def spin(timeout):
        t0=time.monotonic()
        rclpy.spin_once(node,timeout_sec=timeout)
        dur=time.monotonic()-t0
        if dur>timeout+0.12:
            record['events'].append({'stage':'slow_spin','dur_s':round(dur,3),'timeout_s':timeout,
                                     'phase':gap_state['phase'],'t_wall_s':round(time.monotonic()-start,3)})
    if getattr(args,'gc_freeze',False):
        # move every object created during start-up (sklearn, LLM client, ...) out of the
        # collector's reach so later full collections stay short
        gc.collect(); gc.freeze()
        record['gc_frozen_objects']=gc.get_freeze_count()
    def set_phase(name):
        gap_state['phase']=name
    def publish(linear=0.,angular=0.):
        now_p=time.monotonic()
        if gap_state['last'] is not None:
            gap=now_p-gap_state['last']
            gap_state['max']=max(gap_state['max'],gap)
            if gap>0.25:
                record['events'].append({'stage':'request_gap','gap_s':round(gap,3),'phase':gap_state['phase'],
                                         't_wall_s':round(now_p-start,3)})
        gap_state['last']=now_p
        if interlock:
            interlock_heartbeat()
        t=Twist();t.linear.x=float(linear);t.angular.z=float(angular);pub.publish(t)
        pub_dur=time.monotonic()-now_p
        if pub_dur>0.1:
            record['events'].append({'stage':'slow_publish','dur_s':round(pub_dur,3),'phase':gap_state['phase'],
                                     't_wall_s':round(now_p-start,3)})
    start=time.monotonic()
    record['mission_start_unix_ns']=time.time_ns()
    record['wall_clock_time_basis']='host_unix_ns_plus_monotonic_event_offsets'
    def check_clock_health():
        if clock_failure['reason'] is not None:
            raise RuntimeError('simulation clock invalid: '+clock_failure['reason'])
    def check_camera(now):
        check_clock_health()
        if camera_watch is not None:
            reason=camera_watch.check(now)
            if reason:
                record['events'].append({'stage':'camera_watchdog_abort','reason':reason,
                                         't_wall_s':round(now-start,3)})
                raise RuntimeError('camera watchdog stopped mission: '+reason)

    def check_guard(now):
        if guard_required and (not ctx['guard_ready'] or ctx['guard_time'] is None or
                               now < ctx['guard_time'] or now-ctx['guard_time']>0.6):
            raise RuntimeError('independent velocity guard missing / not ready; refuse motion')

    def hold_stationary_while(thread, timeout_s, label):
        """Keep commanding zero velocity and enforce every watchdog while `thread` runs."""
        started=time.monotonic()
        while thread.is_alive():
            publish()
            spin(.09)
            now=time.monotonic()
            if watch.check(now):
                raise RuntimeError(label+' watchdog: '+watch.latched_reason)
            check_camera(now)
            check_guard(now)
            if ctx['pose_time'] is None or now-ctx['pose_time']>1.3:
                raise RuntimeError(label+' odometry stale')
            enforce_stationary_ref[0]()
            if now-started>timeout_s:
                raise TimeoutError(label+' timeout; remain STOPPED')
        thread.join(timeout=.01)

    enforce_stationary_ref=[lambda: None]

    def onsite_check(station, expected=None, peek=False):
        """Align camera to `station`, capture NEW frame, then keep zero velocity during AI.

        `expected` is the requested supply (defaults to the station name); in a
        recovery search the robot checks the next candidate station (the arena: the other one) for the same supply.
        Returns the checkpoint outcome; a denial has already held 2.5 s at zero.
        """
        expected=expected or station
        if getattr(args,'inference_backend','cloud') == 'local':
            from rescuemind.local_vision import verify_station_local
        else:
            from rescuemind.checkpoint import verify_station
        # The robot can finish a waypoint within 23 cm at an arbitrary yaw.
        # Before VLM inference, actively point its camera at the expected
        # supply station. Scene truth labels are NOT supplied to the models.
        centers=load_centers(args)
        if station not in centers:
            raise RuntimeError('Unknown camera aiming station; do not infer')
        set_phase('aim:'+station)
        aim_started=time.monotonic()
        aligned_since=None
        while True:
            spin(.06)
            now=time.monotonic()
            why=watch.check(now)
            if why:
                raise RuntimeError('camera aiming watchdog: '+why)
            check_camera(now)
            check_guard(now)
            if ctx['pose'] is None or ctx['pose_time'] is None or now-ctx['pose_time']>1.3:
                raise RuntimeError('camera aiming odometry stale')
            if now-aim_started>args.aim_timeout:
                raise TimeoutError('camera aiming timed out; VLM inference withheld')
            aim=aim_at_station(ctx['pose'],centers[station])
            publish(0.,aim.angular)
            if aim.aligned:
                if aligned_since is None:
                    aligned_since=now
                if now-aligned_since>=0.5:
                    publish()
                    record['events'].append({'stage':'camera_aim_aligned',
                        'target_station':station,'error_rad':round(aim.bearing_error_rad,4),
                        'duration_wall_s':round(now-aim_started,3),
                        't_wall_s':round(now-start,3)})
                    break
            else:
                aligned_since=None
        # v2.6: zero commanded speed is NOT evidence that wheels have stopped.
        # Require a continuous period of fresh low-velocity odometry and small
        # pose/yaw drift before the camera exposure, then monitor the same
        # locked pose throughout on-site inference and any denial dwell.
        stationary=StationaryGate()
        set_phase('settle:'+station)
        settle_started=time.monotonic()
        # v3.3 (campaign C, R001): the first stationarity sample must not be the odometry
        # message received *before* alignment finished, otherwise the reported stable
        # window can start a few ms before the alignment event and the audit rejects it.
        last_odom_processed=ctx['pose_time']
        def enforce_stationary():
            nonlocal last_odom_processed
            if ctx['pose'] is None or ctx['pose_time'] is None or ctx['odom_twist'] is None:
                raise MotionUnstable('missing_stationary_odometry')
            stamp=ctx['pose_time']
            if stamp != last_odom_processed:
                last_odom_processed=stamp
                stationary.observe(ctx['pose'], *ctx['odom_twist'], stamp)
            return stationary.locked
        enforce_stationary_ref[0]=enforce_stationary
        while not stationary.locked:
            publish()
            spin(.08)
            now=time.monotonic()
            why=watch.check(now)
            if why: raise RuntimeError('stationary settle watchdog: '+why)
            check_camera(now)
            check_guard(now)
            if ctx['pose_time'] is None or now-ctx['pose_time']>1.3:
                raise RuntimeError('stationary settle odometry stale')
            if now-settle_started>args.settle_timeout:
                raise TimeoutError('physical stationarity not verified; VLM inference withheld')
            enforce_stationary()
        record['events'].append({'stage':'checkpoint_stationary_verified',
            't_wall_s':round(time.monotonic()-start,3),**stationary.report()})
        # Fresh camera acquisition starts AFTER physical stationarity is proven.
        arrived_at=time.monotonic()
        stamp_at_arrival=frames.last_stamp_ns
        if frames.invalid_or_regressed or stamp_at_arrival is None:
            raise RuntimeError('ROS camera lacks valid, monotonic acquisition timestamp')
        # A short stationary dwell avoids reusing a camera frame queued while moving.
        first_frame_after=arrived_at+0.5
        image_gate=CheckpointAcquisitionGate(stamp_at_arrival,first_frame_after)
        last_examined_camera_time=ctx['frame_time']
        last_clock_proof=None
        record['events'].append({'stage':'checkpoint_wait','t_wall_s':round(arrived_at-start,3)})
        set_phase('frames:'+station)
        while time.monotonic()-arrived_at < args.camera_wait:
            publish()
            spin(.1)
            now=time.monotonic()
            if watch.check(now):
                raise RuntimeError('checkpoint sensor watchdog: '+watch.latched_reason)
            check_camera(now)
            check_guard(now)
            if ctx['pose_time'] is None or now-ctx['pose_time']>1.3:
                raise RuntimeError('checkpoint odometry stale')
            enforce_stationary()
            if frames.invalid_or_regressed:
                raise RuntimeError('ROS camera acquisition timestamp missing or regressed')
            # Only new callback instances are inspected; two distinct valid
            # acquisition stamps and gross exposure integrity are mandatory.
            if ctx['frame_msg'] is not None and ctx['frame_time']!=last_examined_camera_time:
                last_examined_camera_time=ctx['frame_time']
                # The camera stamp must be near the *current* simulated time,
                # not merely newer than the previous stamp. Delayed queued
                # frames are not a proof of new on-site observation.
                if clock_source=='system':
                    last_clock_proof=clock_gate.check_frame(ctx['frame_msg'],ctx['frame_time'],
                                                            received_ns=ctx.get('frame_sys_ns'))
                else:
                    last_clock_proof=clock_gate.check_frame(ctx['frame_msg'],ctx['frame_time'])
                if image_gate.observe(ctx['frame_msg'],ctx['frame_time']):
                    break
        else:
            raise TimeoutError('Two quality-checked NEW ROS camera frames not received after stationarity')
        f=Path(args.checkpoint_image)
        f.parent.mkdir(parents=True,exist_ok=True)
        image_gate.frame.save(f,'JPEG',quality=90)
        record['events'].append({'stage':'checkpoint_image_quality_verified',
                                 't_wall_s':round(time.monotonic()-start,3),
                                 **image_gate.report()})
        record['events'].append({'stage':rp.SYSTEM_CLOCK_STAGE if clock_source=='system' else 'checkpoint_camera_sim_clock_verified',
                                 't_wall_s':round(time.monotonic()-start,3),
                                 **last_clock_proof})
        record['checkpoint_image_path']=(str(f.relative_to(ROOT)) if f.is_relative_to(ROOT) else f.name)
        record['events'].append({'stage':'checkpoint_frame','t_wall_s':round(time.monotonic()-start,3),
                                  'image_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),
                                  'captured_from_ros_topic':args.camera_topic,
                                  'ros_acquisition_stamp_ns':frames.last_stamp_ns})
        finished={'result':None,'error':None}
        def inference():
            try:
                if getattr(args,'inference_backend','cloud') == 'local':
                    finished['result']=verify_station_local(f,expected,mode=args.local_mode,
                        primary_url=args.local_primary_url,secondary_url=args.local_secondary_url,
                        primary_model=getattr(args,'vlm_model','Qwen/Qwen2.5-VL-3B-Instruct'),
                        hazard_threshold=getattr(args,'expected_hazard_threshold',0.05),
                        **({'jev_url':args.jev_url,'jev_hazard_threshold':args.jev_hazard_threshold,'jev_schema':args.jev_schema}
                           if getattr(args,'jev_url',None) else {}))
                else:
                    finished['result']=verify_station(f,expected,qwen_model=args.qwen_model,endpoint=args.qwen_endpoint)
            except Exception as e:
                finished['error']=e
        t=Thread(target=inference,daemon=True)
        set_phase('inference:'+station)
        t.start()
        hold_stationary_while(t,args.checkpoint_timeout,'checkpoint inference')
        if finished['error'] is not None:
            raise RuntimeError('on-site checkpoint inference failed') from finished['error']
        outcome=finished['result']
        caution=((record.get('memory') or {}).get('caution') or {}).get(station)
        if caution:
            # I-15: a hazard was seen here on a recent mission -> stricter hazard threshold (approval -> refusal only)
            from rescuemind.mission_memory import apply_memory_caution
            outcome['memory_caution_tau_h']=float(caution['tau_h'])
            if not peek:
                calls=outcome['model_calls']
                outcome['decision']=apply_memory_caution(outcome['decision'],calls['first'],calls['second'],float(caution['tau_h']))
        record['checkpoint']=outcome
        record['checkpoint_station']=station
        record['events'].append({'stage':'checkpoint_decision','t_wall_s':round(time.monotonic()-start,3),
                                  'station':station,'expected':expected,
                                  'allow':outcome['decision']['allow'],'reason':outcome['decision']['reason']})
        if peek:
            return outcome      # I-14 side view: no explanation, no denial dwell (the caller decides)
        if getattr(args,'explain',False) and getattr(args,'inference_backend','cloud')=='local':
            # I-03: one-sentence Japanese report of what the camera saw (explanation only;
            # the decision above is already final and never reads this text).
            from rescuemind.local_vision import describe_station_local
            said={'result':None,'error':None}
            def explain():
                try:
                    said['result']=describe_station_local(f,url=args.local_primary_url.replace('/v1/classify','/v1/describe'),
                                                          model=getattr(args,'vlm_model','Qwen/Qwen2.5-VL-3B-Instruct'))
                except Exception as e:
                    said['error']=e
            set_phase('explanation:'+station)
            te=Thread(target=explain,daemon=True); te.start(); t0=time.monotonic()
            hold_stationary_while(te,60.,'explanation')
            entry={'stage':'checkpoint_explanation','t_wall_s':round(time.monotonic()-start,3),
                   'latency_s':round(time.monotonic()-t0,3)}
            if said['result'] is not None:
                outcome['explanation']=said['result']
                entry['text_ja']=said['result']['text_ja']
            else:
                entry['error']=type(said['error']).__name__  # explanation failure never changes the decision
            record['events'].append(entry)
        if not outcome['decision']['allow']:
            # An expected negative scene must not be confused with a crash.
            # Keep the velocity guard alive, command ZERO, and retain new ROS
            # odometry samples after the AI denial for independent audit.
            # Any sensor/guard error during this dwell is a real FAILURE.
            set_phase('denial_dwell:'+station)
            denied_at=time.monotonic()
            while time.monotonic()-denied_at < 2.5:
                publish()
                spin(.1)
                now=time.monotonic()
                why=watch.check(now)
                if why:
                    raise RuntimeError('denial dwell watchdog: '+why)
                check_camera(now)
                check_guard(now)
                if ctx['pose_time'] is None or now-ctx['pose_time']>1.3:
                    raise RuntimeError('denial dwell odometry stale')
                enforce_stationary()
            record['events'].append({'stage':'checkpoint_denial_dwell_finished',
                                     't_wall_s':round(time.monotonic()-start,3),
                                     'commanded_linear':0.,'commanded_angular':0.})
        return outcome

    def schedule_look_around(station, waypoint):
        centers=load_centers(args)
        cx,cy=centers[station][:2] if isinstance(centers[station],(list,tuple)) else (centers[station].x,centers[station].y)
        wx,wy=waypoint[:2]
        n=math.hypot(cx-wx,cy-wy) or 1.
        vx,vy=-(cy-wy)/n,(cx-wx)/n
        d=float(args.look_around)
        pts=[('L',(round(wx-d*vx,3),round(wy-d*vy,3))),('R',(round(wx+d*vx,3),round(wy+d*vy,3)))]
        pts=[q for q in pts if q[0] in getattr(args,'look_around_sides','LR')]      # I-74: one-sided look-around (default both sides)
        caution=((record.get('memory') or {}).get('caution') or {}).get(station) or {}
        if caution.get('first_side')=='R':
            pts.reverse()     # I-15: look first from the side that revealed the remembered hazard
        la=record.setdefault('look_around',{'offset_m':d,'station':station,'points':[],'peeks':[]})
        la['points']=[{'side':sd,'xy':list(xy)} for sd,xy in pts]
        la['waypoint']=[round(wx,3),round(wy,3)]; la['center']=[round(cx,3),round(cy,3)]
        record['events'].append({'stage':'look_around_scheduled','station':station,'points':la['points'],
                                 't_wall_s':round(time.monotonic()-start,3)})
        return [('peek',f'{station}:{sd}',xy) for sd,xy in pts]

    def schedule_adaptive_views(station, cp, la):
        """I-20: after the standard views all passed, if any of them was suspicious (p(hazard) >= tau_sus), look again
        from wider side poses and closer to the station.  Can only add refusals (an extra view with a hazard revokes)."""
        # I-19 scrutiny (--advice-scrutiny): the station that advice moved to the front of the order gets the extra views
        # whether or not a view was suspicious (it can only add views)
        scr=bool(getattr(args,'advice_scrutiny',False)) and station in ((record.get('memory') or {}).get('scrutiny') or [])
        off=float(getattr(args,'adaptive_views',0) or 0) or (SCRUTINY_OFFSET_M if scr else 0.)
        if off <= 0 or la.get('adaptive') is not None or len(la['peeks']) < len(la['points']):
            return None
        from rescuemind.adaptive_views import suspicion, extra_points
        p_max=suspicion(cp, la['peeks'])
        tau=float(getattr(args,'adaptive_tau_sus',0.005))
        la['adaptive']={'p_max':p_max,'tau_sus':tau,'triggered':p_max>=tau or scr,'offset_m':off,
                        'near_m':float(getattr(args,'adaptive_near',0.3))}
        if scr:
            la['adaptive']['scrutiny']=True
        if p_max < tau and not scr:
            return None
        pts=extra_points(la['waypoint'],la['center'],off,float(getattr(args,'adaptive_near',0.3)))
        if float(getattr(args,'adaptive_near',0.3))<=0:
            pts=[q for q in pts if q[0]!='N']       # study JK Amendment 2: --adaptive-near 0 drops the near pose N (default 0.3 unchanged)
        la['points']+= [{'side':sd,'xy':list(xy)} for sd,xy in pts]
        record['events'].append({'stage':'adaptive_views_scheduled','station':station,'p_max':p_max,'points':[sd for sd,_ in pts],
                                 't_wall_s':round(time.monotonic()-start,3)})
        return [('peek',f'{station}:{sd}',xy) for sd,xy in pts]

    SOFT_PEEK=object()
    HAZ_PEEK=object()

    def search_context(target):
        """(prior recovery block, stations denied before this one, candidate order, next candidate or None)."""
        prior=record.get('recovery')
        denied_before=([prior['first_station']]+[h['station'] for h in prior.get('hops',[])]) if prior else []
        head=denied_before[0] if denied_before else target
        order=record.get('station_order') or [head,'medicine' if head=='water' else 'water']   # the arena: the other one
        return prior,denied_before,order,next_candidate(order,denied_before+[target])

    def note_caution_refusal(station, where, source, tau_mem, base_reason, nxt):
        """Record a caution-only refusal (R5 #5).  `source`: the checkpoint outcome (front) or the side-view entry."""
        from rescuemind.caution_soft import refusal_record
        from rescuemind.mission_memory import hazard_prob
        calls=source.get('model_calls') or {}
        p_max=max(hazard_prob(calls.get('first')),hazard_prob(calls.get('second')))
        rec=refusal_record(station,where,p_max,float(tau_mem),base_reason or '',nxt is not None,nxt)
        record.setdefault('caution_refusals',[]).append(rec)
        record['events'].append({'stage':'caution_refusal','t_wall_s':round(time.monotonic()-start,3),**rec})

    def note_hazard_refusal(station, where, source, nxt):
        """Record a real-hazard refusal that the search continues past (I-42, --hazard-continue)."""
        from rescuemind.hazard_continue import refusal_record as hz_record
        from rescuemind.mission_memory import hazard_prob
        calls=source.get('model_calls') or {}
        p_max=max(hazard_prob(calls.get('first')),hazard_prob(calls.get('second')))
        rec=hz_record(station,where,p_max,nxt is not None,nxt)
        record.setdefault('hazard_refusals',[]).append(rec)
        record['events'].append({'stage':'hazard_refusal','t_wall_s':round(time.monotonic()-start,3),**rec})

    def begin_search(target, outcome, reason, ctx, index, kind=None):
        """Keep the refused station's evidence under a 'recovery_' prefix and send the robot to the next candidate."""
        prior,denied_before,order,nxt=ctx
        first=len(record['events'])-1
        while first>=0 and record['events'][first].get('stage')!='supply_station':
            first-=1
        for e in record['events'][first:]:
            e['stage']='recovery_'+e['stage']
        first_image=Path(args.checkpoint_image)
        n_hop=len(denied_before)       # 0: first denial, 1: second, ...
        pre='recovery_' if n_hop==0 else f'recovery{n_hop+1}_'
        kept=first_image.with_name(pre+first_image.name)
        first_image.replace(kept)
        la_=outcome.get('look_around')
        if la_:        # side views of the refused station keep their own file names (the next station takes the old ones)
            for pk in la_.get('peeks',[]):
                old_img=first_image.with_name(pk['image'])
                if old_img.is_file():
                    old_img.replace(first_image.with_name(pre+pk['image']))
                    pk['image']=pre+pk['image']
            record.pop('look_around',None)
        if prior is None:
            record['recovery']={'first_station':target,'first_checkpoint':outcome,
                                'first_checkpoint_image':kept.name,'searched_station':nxt,
                                'reason':reason,'candidates':list(order)}
            if kind:
                record['recovery']['first_kind']=kind
        else:
            hop={'station':target,'checkpoint':outcome,'checkpoint_image':kept.name,'reason':reason}
            if kind:
                hop['kind']=kind
            prior.setdefault('hops',[]).append(hop)
            prior['searched_station']=nxt
        record['checkpoint']=None
        record['events'].append({'stage':'recovery_search_started','from':target,'to':nxt,
                                 't_wall_s':round(time.monotonic()-start,3)})
        waypoints=json.loads(Path(getattr(args,'config',ROOT/'configs/gazebo_waypoints.json')).read_text(encoding='utf-8'))
        route.insert(index,('supply_station',nxt,tuple(waypoints[nxt])))

    def look_around_peek(target, goal):
        station,side=target.split(':')
        requested=(record.get('intent') or {}).get('item') or station
        n0=len(record['events'])
        saved=(record.get('checkpoint'),record.get('checkpoint_station'),args.checkpoint_image)
        img=Path(saved[2]).with_name(f'peek_{side}_'+Path(saved[2]).name)
        args.checkpoint_image=str(img)
        try:
            po=onsite_check(station,requested,peek=True)
        finally:
            args.checkpoint_image=saved[2]
            record['checkpoint'],record['checkpoint_station']=saved[0],saved[1]
        for e in record['events'][n0:]:
            e['stage']=f'peek_{side}_'+e['stage']
        from rescuemind.mission_memory import peek_hazard
        hazard=peek_hazard(po['decision']['reason'],po['model_calls']['first'],po['model_calls']['second'],
                           po.get('memory_caution_tau_h'))
        entry={'side':side,'xy':list(goal[:2]),'image':img.name,'image_sha256':po['image_sha256'],
               'model_calls':po['model_calls'],'hazard':hazard,'reason':po['decision']['reason']}
        if 'jev_call' in po:
            entry['jev_call']=po['jev_call']
        la=record['look_around']; la['peeks'].append(entry)
        cp=record['checkpoint']; cp['look_around']=la
        if not hazard:
            return schedule_adaptive_views(station, cp, la)
        from rescuemind.caution_soft import classify_view
        # R5 #5: a side view the standard (v3.6) rule would have passed, refused only by the tightened threshold
        soft_peek=soft and classify_view(po['decision']['reason'],po['model_calls']['first'],po['model_calls']['second'],
                                         po.get('memory_caution_tau_h'))=='caution_only'
        from rescuemind.hazard_continue import real_side_hazard
        haz_peek=hcont and real_side_hazard(po['decision']['reason'],po['model_calls']['first'],po['model_calls']['second'],
                                            po.get('memory_caution_tau_h'))     # I-42: a real hazard seen from the side
        # a hazard seen from the side: the approval becomes a hazard refusal, exactly as at the front
        from rescuemind.local_vision import combine_with_look_around
        cp['decision']=combine_with_look_around(cp['decision'],[{'side':q['side'],'hazard':q['hazard']} for q in la['peeks']])
        for e in record['events']:
            if e.get('stage')=='checkpoint_decision':
                e['stage']='front_checkpoint_decision'
        record['events'].append({'stage':'checkpoint_decision','t_wall_s':round(time.monotonic()-start,3),
                                 'station':station,'expected':requested,'allow':False,
                                 'reason':'visible_hazard_at_checkpoint','source':'look_around_'+side})
        set_phase('denial_dwell:look_around')
        denied_at=time.monotonic()
        while time.monotonic()-denied_at < 2.5:
            publish(); spin(.1)
            now=time.monotonic()
            why=watch.check(now)
            if why:
                raise RuntimeError('denial dwell watchdog: '+why)
            check_camera(now); check_guard(now)
            if ctx['pose_time'] is None or now-ctx['pose_time']>1.3:
                raise RuntimeError('denial dwell odometry stale')
            enforce_stationary_ref[0]()
        record['events'].append({'stage':'checkpoint_denial_dwell_finished','t_wall_s':round(time.monotonic()-start,3),
                                 'commanded_linear':0.,'commanded_angular':0.})
        if soft_peek:
            ctx_=search_context(station)
            note_caution_refusal(station,'side_'+side,entry,po.get('memory_caution_tau_h'),
                                 cp['decision'].get('front_reason'),ctx_[3])
            if ctx_[3] is not None and (ctx_[0] is None or station==ctx_[0].get('searched_station')):
                return SOFT_PEEK
        if haz_peek:
            ctx_=search_context(station)
            note_hazard_refusal(station,'side_'+side,entry,ctx_[3])
            if ctx_[3] is not None and (ctx_[0] is None or station==ctx_[0].get('searched_station')):
                return HAZ_PEEK
        raise RuntimeError('on-site checkpoint DENIED: visible_hazard_at_checkpoint (look-around '+side+')')

    def request_delivery_permit():
        """I-22: stand still, publish the approval record, wait for the interlock's permit for exactly this record."""
        il['phase']=dp.PHASE_DELIVER
        img=Path(args.checkpoint_image)
        il['raw']=dp.build_record(record,image_dir=img.parent,front_name=img.name,
                                  look_around=getattr(args,'look_around',0.),adaptive_views=getattr(args,'adaptive_views',0.),
                                  look_around_sides=getattr(args,'look_around_sides','LR'))
        h=dp.record_hash(il['raw'])
        record['delivery_interlock'].update({'record_hash':h,'station':record.get('checkpoint_station'),
                                             'requested_t_wall_s':round(time.monotonic()-start,3)})
        set_phase('permit_wait')
        t0=time.monotonic()
        wait=float(getattr(args,'interlock_wait',10.))
        while True:
            spin(.08)
            publish()
            if watch.check(time.monotonic()):
                raise RuntimeError('watchdog during permit wait: '+watch.latched_reason)
            check_camera(time.monotonic())
            check_guard(time.monotonic())
            try:
                p=json.loads(il['permit']) if il['permit'] else {}
            except ValueError:
                p={}
            if p.get('record_hash')==h and isinstance(p.get('not_after'),(int,float)) and p['not_after']>=time.time():
                record['delivery_interlock'].update({'permit_t_wall_s':round(time.monotonic()-start,3),'permit_received':True})
                record['events'].append({'stage':'delivery_permit','record_hash':h,'t_wall_s':round(time.monotonic()-start,3)})
                return
            if time.monotonic()-t0>wait:
                record['delivery_interlock']['permit_received']=False
                record['events'].append({'stage':'delivery_permit_timeout','record_hash':h,'t_wall_s':round(time.monotonic()-start,3)})
                raise RuntimeError('delivery interlock: no permit for the approval record (denied or interlock down)')

    try:
        set_phase('warmup')
        # Sensor warmup, no motion allowed during startup.  v3.3: a fixed 3 s
        # window lost DDS discovery races on a loaded host (campaign A: 4 of 12
        # attempts saw no /odom or /scan).  Keep the minimum warmup, then keep
        # waiting (zero velocity) until every required stream has delivered a
        # first message, up to --sensor-wait seconds; the checks below still fail closed.
        live_run = record.get('run_type') in ('jev_qwen_live_mission','local_vlm_live_mission')
        def streams_ready():
            return (ctx['pose'] is not None and watch.last_scan_at is not None
                    and (not live_run or ctx['frame_msg'] is not None)
                    and (not guard_required or ctx['guard_ready']))
        injected=False
        while (time.monotonic()-start < args.warmup
               or (not streams_ready() and time.monotonic()-start < args.sensor_wait)):
            if getattr(args,'inject_warmup_stall',0) and not injected and time.monotonic()-start>1.0:
                injected=True   # I-09 fault injection: reproduce a planner stall while stationary
                record['events'].append({'stage':'injected_stall','stall_s':args.inject_warmup_stall,
                                         't_wall_s':round(time.monotonic()-start,3)})
                time.sleep(args.inject_warmup_stall)
            spin(.08)
            publish()
            if watch.check(time.monotonic()):
                raise RuntimeError('watchdog during startup: '+watch.latched_reason)
            check_camera(time.monotonic())
        if ctx['pose'] is None or ctx['pose_time'] is None:
            raise RuntimeError('No odometry received. Check bridge /odom and gz topic -l')
        if watch.last_scan_at is None:
            raise RuntimeError('No scan received. Check bridge /scan and Gazebo play state')
        if record.get('run_type') in ('jev_qwen_live_mission','local_vlm_live_mission'):
            if ctx['frame_msg'] is None:
                raise RuntimeError('No ROS camera frame during warmup: refuse to start live AI mission')
            if frames.invalid_or_regressed or frames.last_stamp_ns is None:
                raise RuntimeError('ROS camera has no valid monotonic header timestamp')
        check_guard(time.monotonic())
        if math.hypot(ctx['pose'].x,ctx['pose'].y)>1.0:
            raise RuntimeError('Unexpected start odometry: restart test world at origin and calibrate')
        from rescuemind.advice import skip_source, denial_source
        deny_by=denial_source(record.get('memory'))
        if deny_by:
            # NAIVE BASELINES ONLY: refuse because of a remembered hazard (I-15) or an advised one (I-19: peer,
            # inventory or the operator's text) without going to look.  Never in verified / monotone mode.
            record['events'].append({'stage':'memory_denial','station':record['memory']['first_station'],'by':deny_by,
                                     't_wall_s':round(time.monotonic()-start,3)})
            for _ in range(10):
                publish(); spin(.1)
            raise RuntimeError('on-site checkpoint DENIED: '+('advice_hazard (naive advice baseline)' if deny_by=='advice'
                                                              else 'memory_hazard (naive memory baseline)'))
        route=list(route)
        index=0
        while index < len(route):
            stage,target,goal=route[index]
            index+=1
            progress.anchor_at=None; progress.anchor_xy=None
            if interlock:
                il['phase']=dp.PHASE_DELIVER if stage=='shelter_approach' else dp.PHASE_SEARCH
                if stage=='shelter_approach':
                    request_delivery_permit()
            set_phase('drive:'+stage+':'+str(target))
            begun=time.monotonic();samples=[]
            while True:
                spin(.06)
                now=time.monotonic()
                why=watch.check(now)
                if why:
                    raise RuntimeError('watchdog stopped mission: '+why)
                check_camera(now)
                check_guard(now)
                if ctx['pose'] is None or ctx['pose_time'] is None or now-ctx['pose_time']>1.3:
                    raise RuntimeError('odometry stale')
                if record.get('run_type') in ('jev_qwen_live_mission','local_vlm_live_mission') and frames.invalid_or_regressed:
                    raise RuntimeError('camera timestamp regression or invalid header')
                if now-begun>args.stage_timeout:
                    raise TimeoutError(f'waypoint timeout: {stage}/{target}')
                cmd=(peek_ctl if stage=='peek' else ctl).command(ctx['pose'],goal)
                stall=progress.update(ctx['pose'],cmd.linear,now)
                if stall:
                    raise RuntimeError('drive progress watchdog: '+stall)
                if cmd.arrived:
                    publish()
                    if stage == 'peek':
                        # I-14: a side-view pose is not a mission waypoint; keep the supply->shelter receipt intact
                        record['events'].append({'stage':'look_around_arrival','target':target,'reached':True,
                                                 'duration_wall_s':round(now-begun,3),'t_wall_s':round(now-start,3),
                                                 'last_pose':list(ctx['pose'].__dict__.values())})
                        record['trace'].extend(samples)
                        extra=look_around_peek(target, goal)
                        if extra is SOFT_PEEK or extra is HAZ_PEEK:
                            # R5 #5: caution-only side view -> no delivery from this station, drop its remaining
                            # views and continue with the next candidate (full check there)
                            st_=target.split(':')[0]
                            route[index:]=[r for r in route[index:] if not (r[0]=='peek' and str(r[1]).startswith(st_+':'))]
                            begin_search(st_,record['checkpoint'],'visible_hazard_at_checkpoint',search_context(st_),index,
                                         kind='caution_only' if extra is SOFT_PEEK else 'hazard')
                        elif extra:
                            route[index:index]=extra      # I-20: suspicion-triggered extra views, before leaving
                        break
                    record['events'].append({'stage':stage,'target':target,'arrived':True,
                                              'duration_wall_s':round(now-begun,3),'t_wall_s':round(now-start,3),'samples':len(samples),
                                              'last_pose':list(ctx['pose'].__dict__.values())})
                    record['trace'].extend(samples)
                    mem=record.get('memory') or {}
                    trust=skip_source(mem)
                    if (stage == 'supply_station' and trust
                            and record.get('recovery') is None and target==mem.get('first_station')):
                        # NAIVE BASELINES ONLY: trust the previous mission (I-15) or the advice (I-19) instead of
                        # looking (never in v3.6 / verified / monotone)
                        record['checkpoint']={'memory_trusted':True,'trusted_by':trust,
                                              'decision':{'allow':True,'reason':'memory_trusted' if trust=='memory' else 'advice_trusted'}}
                        record['checkpoint_station']=target
                        record['events'].append({'stage':'checkpoint_skipped_by_memory','station':target,'by':trust,
                                                 't_wall_s':round(time.monotonic()-start,3)})
                        break
                    if stage == 'supply_station' and record.get('run_type') in ('jev_qwen_mission', 'jev_qwen_live_mission','local_vlm_live_mission'):
                        requested=(record.get('intent') or {}).get('item') or target
                        outcome=onsite_check(target,requested)
                        if outcome['decision']['allow'] and getattr(args,'look_around',0) > 0:
                            # I-14: before leaving, look again from beside the station (a fire hidden behind the
                            # supply from the front is often plainly visible from the side)
                            route[index:index]=schedule_look_around(target, goal)
                        if not outcome['decision']['allow']:
                            reason=outcome['decision']['reason']
                            # I-02 / I-21: the requested supply is not here and no hazard was seen -> check the next
                            # candidate station (the arena: the other one, once; the depot: up to k-1 more, in the
                            # inventory / memory order, never skipping one).  Hazards and low-confidence matches stop
                            # immediately (no search into a possible danger), as does an exhausted candidate list.
                            sctx=search_context(target)
                            prior,denied_before,order,nxt=sctx
                            from rescuemind.caution_soft import front_caution_only
                            soft_front=soft and front_caution_only(outcome['decision'])
                            if soft_front:      # R5 #5: record it whether or not a next candidate is left
                                note_caution_refusal(target,'front',outcome,outcome['decision']['memory_caution_tau_h'],
                                                     outcome['decision'].get('pre_caution_reason'),nxt)
                            from rescuemind.hazard_continue import real_front_hazard
                            cm_=outcome.get('model_calls') or {}
                            hz_front=hcont and real_front_hazard(outcome['decision'],cm_.get('first'),cm_.get('second'))
                            if hz_front:        # I-42: record it whether or not a next candidate is left
                                note_hazard_refusal(target,'front',outcome,nxt)
                            if (nxt is not None and (prior is None or target==prior.get('searched_station'))
                                    and ((getattr(args,'recovery',False) and reason=='local_vlm_disagree_or_wrong_supply')
                                         or soft_front or hz_front)):
                                begin_search(target,outcome,reason,sctx,index,
                                             kind='caution_only' if soft_front else ('hazard' if hz_front else None))
                            else:
                                raise RuntimeError('on-site checkpoint DENIED: '+reason)
                    break
                publish(cmd.linear,cmd.angular)
                if len(samples)==0 or now-samples[-1]['t']>.24:
                    samples.append({'t':round(now-start,3),'x':round(ctx['pose'].x,3),
                                    'y':round(ctx['pose'].y,3),'yaw':round(ctx['pose'].yaw,3),
                                    'v':round(cmd.linear,3),'w':round(cmd.angular,3),'stage':stage})
                time.sleep(.06)
        record['success']=True
    finally:
        if gc_probe in gc.callbacks:       # I-42: a run leaves no callback behind (tests run the node hundreds of times in one process)
            gc.callbacks.remove(gc_probe)
        record['max_request_gap_s']=round(gap_state['max'],3)
        # Publish redundant zeros as this is not safety-certified hardware.
        for _ in range(5):
            publish();spin(.05)
        _=subs
        node.destroy_node();rclpy.shutdown()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',action='store_true',help='legacy: static-image dual preflight then on-site Jev+Qwen')
    ap.add_argument('--run-live',action='store_true',help='v0.9: no static images; intent guard then ROS camera on-site Jev+Qwen')
    ap.add_argument('--intent-min-score',type=float,default=.60,help='heuristic TF-IDF score threshold; not calibrated')
    ap.add_argument('--motion-check',action='store_true',help='just move in Gazebo; no AI claim')
    ap.add_argument('--instruction',default='避難所Bに飲料水を届けて')
    ap.add_argument('--config',default=str(ROOT/'configs/gazebo_waypoints.json'))
    ap.add_argument('--centers',default=None,
        help='Study L: per-run station centres JSON (default: locked configs/gazebo_station_centers.json)')
    ap.add_argument('--preflight-image')
    ap.add_argument('--corridor-image')
    ap.add_argument('--inference-backend',choices=['local','cloud'],default='cloud',
                    help='local=on-device Transformers vision; cloud=legacy Jev/Qwen APIs')
    ap.add_argument('--local-mode',choices=['single','dual'],default='single')
    ap.add_argument('--expected-hazard-threshold',type=float,default=None,
                    help='the VLM server tau_h (--hazard-threshold) this run must have been started with; every model call is '
                         'checked against it and the mission aborts otherwise (default 0.05 = v3.6; the server default 0.5 is '
                         'refused; with --site-config the site value, and a conflicting flag is an error)')
    ap.add_argument('--local-primary-url',default='http://127.0.0.1:8765/v1/classify')
    ap.add_argument('--local-secondary-url',default='http://127.0.0.1:8766/v1/classify')
    ap.add_argument('--qwen-model',default='qwen3.8-omni-flash')
    ap.add_argument('--qwen-endpoint',default='http://127.0.0.1:8000/v1/chat/completions')
    ap.add_argument('--cmd-topic',default='/rescuemind/cmd_vel_request',help='guarded input; do not point live tasks at /cmd_vel')
    ap.add_argument('--legacy-direct-motion-check',action='store_true',help='UNGUARDED diagnostic only for --motion-check; never for live AI tasks')
    ap.add_argument('--odom-topic',default='/odom')
    ap.add_argument('--scan-topic',default='/scan')
    ap.add_argument('--camera-topic',default='/camera')
    ap.add_argument('--run-id',default=None,help='Supervisor-provided unique 16-digit hex run ID')
    ap.add_argument('--checkpoint-image',default=None,help='Optional checkpoint JPEG path; omitted => unique per-run output')
    ap.add_argument('--camera-max-age',type=float,default=3.0,help='Stop a live mission if ROS camera acquisition stamps stop advancing')
    ap.add_argument('--camera-wait',type=float,default=10.0)
    ap.add_argument('--aim-timeout',type=float,default=14.0)
    ap.add_argument('--settle-timeout',type=float,default=7.0)
    ap.add_argument('--checkpoint-timeout',type=float,default=155.0)
    ap.add_argument('--intent-backend',choices=['tfidf','llm'],default='tfidf',help='I-04: llm = local model closed-set parse + shelter guard')
    ap.add_argument('--intent-conflict-check',action='store_true',
                    help='I-27 (default off): a request naming both supplies, or whose other supply keeps p >= 0.05, is not acted on (ask back)')
    ap.add_argument('--vlm-model',default='Qwen/Qwen2.5-VL-3B-Instruct',help='model id served on the local endpoint')
    ap.add_argument('--recovery',action='store_true',help='I-02: if the supply is missing/wrong, check the other station once')
    ap.add_argument('--explain',action='store_true',help='I-03: one-sentence Japanese report after each checkpoint (not used for decisions)')
    ap.add_argument('--look-around-sides',choices=['LR','L','R'],default='LR',
                    help='I-74: which side views the look-around takes (default both)')
    ap.add_argument('--look-around',type=float,default=0.0,
                    help='I-14: after an approval, look again from this far (m) left and right of the station waypoint')
    ap.add_argument('--jev-url',default=None,help='I-13: local Jev-role model (Clef-Flash) URL; both models must approve')
    ap.add_argument('--jev-schema',choices=['jev','task'],default='jev',help='I-16: original Jev request or task-worded request')
    ap.add_argument('--jev-hazard-threshold',type=float,default=.35)
    ap.add_argument('--memory-file',default=None,help='I-15: cross-mission memory (JSONL of what the robot saw before)')
    ap.add_argument('--memory-mode',choices=['off','verified','naive'],default='off',
                    help='I-15: verified = memory proposes, perception disposes; naive = trust memory (baseline only)')
    ap.add_argument('--adaptive-views',type=float,default=0.0,
                    help='I-20: if a standard view is suspicious (p(hazard) >= --adaptive-tau-sus) look again from this '
                         'side offset (m) and from --adaptive-near closer; 0 = off')
    ap.add_argument('--adaptive-tau-sus',type=float,default=0.005)
    ap.add_argument('--adaptive-near',type=float,default=0.3)
    ap.add_argument('--caution-soft',action='store_true',
                    help='R5 #5: a refusal caused only by memory / advice caution (tau_mem <= p(hazard) < tau_h) does not stop the '
                         'mission: no delivery from that station, continue with the next candidate station (default off: v3.6)')
    ap.add_argument('--hazard-continue',action='store_true',
                    help='I-42: a REAL hazard refusal (standard rule, valid scores) does not stop the mission either: no delivery from that '
                         'station, continue with the next candidate station (default off: v3.6 stops at the first hazard)')
    ap.add_argument('--advice-scrutiny',action='store_true',
                    help='I-19: the station that advice moved to the front gets caution and the I-20 extra views regardless of suspicion')
    ap.add_argument('--advice-file',default=None,
                    help='I-19: JSON list of advice items (peer robot / inventory / memory claims), see rescuemind.advice.validate')
    ap.add_argument('--advice-mode',choices=['off','monotone','naive','filtered'],default='off',
                    help='I-19: monotone = advice may only reorder stations and tighten thresholds; naive = follow advice; filtered = follow advice that an LLM injection filter does not flag (baselines only)')
    ap.add_argument('--advice-credit',default=None,
                    help='I-24: per-source advice-credit ledger (read only here; the orchestrator settles it after the mission)')
    ap.add_argument('--advice-from-instruction',action='store_true',
                    help='I-19: extract operator advice (location / hazard / skip claims) from the instruction text with the local model')
    ap.add_argument('--delivery-interlock',action='store_true',
                    help='I-22 (default off): publish the phase and the approval record; do not start the delivery leg without the '
                         'independent interlock node\'s permit (the velocity guard enforces it)')
    ap.add_argument('--interlock-wait',type=float,default=10.0,help='I-22: seconds to wait for the permit before the delivery leg')
    ap.add_argument('--control-qos',choices=['reliable','best_effort'],default='reliable',
                    help='I-12: QoS of /rescuemind/cmd_vel_request and /rescuemind/guard_ready')
    ap.add_argument('--inject-warmup-stall',type=float,default=0.0,help='I-09 fault injection (seconds); tests only')
    ap.add_argument('--gc-freeze',action='store_true',help='I-09: freeze start-up objects out of the cyclic GC before the control loop')
    ap.add_argument('--estop-topic',default='/rescuemind/estop')
    ap.add_argument('--min-front-m',type=float,default=.26)
    ap.add_argument('--scan-max-age',type=float,default=1.5)
    ap.add_argument('--warmup',type=float,default=3.0)
    ap.add_argument('--sensor-wait',type=float,default=20.0,
                    help='max seconds (from start) to wait for first odom/scan/camera/guard messages')
    ap.add_argument('--stage-timeout',type=float,default=130.)
    ap.add_argument('--out',default=None,help='Mission JSON path; defaults to per-run outputs/runs/<ID>/mission.json')
    # I-26: opt-in real-robot profile.  Every default below reproduces the simulation behaviour exactly.
    ap.add_argument('--clock-source',choices=list(rp.CLOCK_SOURCES),default='sim',
                    help='I-26: sim (default) = camera stamps vs Gazebo /clock; system = vs this host\'s system clock (a real robot has '
                         'no /clock; same 1.2 s lag / 0.25 s lead limits, fail closed on absent or non-monotonic stamps; the camera '
                         'computer\'s clock must be synchronised)')
    ap.add_argument('--camera-qos',choices=list(rp.CAMERA_QOS),default='reliable',
                    help='I-26: camera subscription QoS; best_effort (for drivers that publish best effort) only with --clock-source system')
    ap.add_argument('--odom-frame',default=None,help='I-26: header.frame_id of /odom must end with this (default: not checked here; the guard checks odom)')
    ap.add_argument('--base-frame',default=None,help='I-26: child_frame_id of /odom must end with this (default: not checked here; the guard checks base_link)')
    ap.add_argument('--site-config',default=None,
                    help='I-26: site.json (schema rescuemind-site-1) with the site tau_h, the caution threshold derived from it and '
                         'optionally the odometry frame names; recorded in mission.json; the same file goes to the server, the interlock and the guard')
    a=ap.parse_args()
    site=None
    try:
        rp.check_profile(a.clock_source,a.camera_qos)
        if a.site_config:
            site=rp.load_site_config(a.site_config)
        a.expected_hazard_threshold=rp.resolve('expected-hazard-threshold',a.expected_hazard_threshold,
                                                site.hazard_threshold if site else None,0.05)
        a.odom_frame=rp.resolve('odom-frame',a.odom_frame,site.odom_frame if site else None,None)
        a.base_frame=rp.resolve('base-frame',a.base_frame,site.base_frame if site else None,None)
        for nm,fr in (('--odom-frame',a.odom_frame),('--base-frame',a.base_frame)):
            if fr is not None: rp.check_frame_name(fr,nm)
    except rp.SiteConfigError as e:
        ap.error(str(e))
    if site is not None and site.caution_tau_h!=rp.CAUTION_TAU_H and (a.advice_file or a.advice_from_instruction):
        ap.error('advice with a site tau_h whose derived caution threshold is not 0.01 is not supported '
                 '(the advice audits assume 0.01); use tau_h >= 0.05 or no advice')
    if a.inference_backend == 'local':
        from rescuemind.local_vision import localhost_only
        localhost_only(a.local_primary_url)
        localhost_only(a.local_secondary_url)
    if not (math.isfinite(a.aim_timeout) and 2.0 <= a.aim_timeout <= 60.):
        ap.error('--aim-timeout must be between 2 and 60 seconds')
    if not (math.isfinite(a.settle_timeout) and 2.0 <= a.settle_timeout <= 30.0):
        ap.error('--settle-timeout must be 2 to 30 seconds')
    if not (math.isfinite(a.camera_max_age) and 0.5 <= a.camera_max_age <= 30.):
        ap.error('--camera-max-age must be between 0.5 and 30 s')
    if a.run_id is not None and (len(a.run_id)!=16 or any(x not in '0123456789abcdef' for x in a.run_id)):
        ap.error('--run-id must be 16 lowercase hex characters')
    run_id=a.run_id or uuid.uuid4().hex[:16]
    if a.checkpoint_image is None:
        a.checkpoint_image=str(ROOT/'outputs'/'runs'/run_id/'on_site_supply.jpg')
    if a.out is None:
        a.out=str(ROOT/'outputs'/'runs'/run_id/'mission.json')
    if sum(bool(x) for x in (a.run,a.run_live,a.motion_check))>1:
        ap.error('--run, --run-live and --motion-check are mutually exclusive')
    if a.legacy_direct_motion_check and not a.motion_check:
        ap.error('--legacy-direct-motion-check is allowed only for --motion-check')
    if a.legacy_direct_motion_check:
        a.cmd_topic='/cmd_vel'
    elif a.cmd_topic!='/rescuemind/cmd_vel_request':
        ap.error('all guarded missions must publish only to /rescuemind/cmd_vel_request')
    a.relay_required=not a.legacy_direct_motion_check
    selection=decide_intent(a.instruction,min_confidence=a.intent_min_score)
    intent=selection.intent
    llm_intent=None
    if a.intent_backend=='llm':
        # I-04: on-board LLM parse (+ explicit shelter-name guard).  If the local model is
        # unreachable the mission refuses to start rather than silently using TF-IDF.
        from rescuemind.intent_llm import decide_intent_hybrid
        from rescuemind.intent import Intent
        from rescuemind.mission_policy import IntentGate
        llm_intent=decide_intent_hybrid(a.instruction,model=a.vlm_model,
                                        url=a.local_primary_url.replace('/v1/classify','/v1/intent'),
                                        **({'conflict_check':True} if getattr(a,'intent_conflict_check',False) else {}))
        item=llm_intent['item'] or 'water'
        conf=(llm_intent.get('probs') or {}).get('item',{}).get(item,0.0)
        selection=IntentGate(bool(llm_intent['accept']),llm_intent['reason'],
                             Intent(item,'B',float(conf),'local_llm_closed_set'))
        intent=selection.intent
    mem_plan=None
    stations=StationSet.from_config(json.loads(Path(a.config).read_text(encoding='utf-8')))     # I-21: k stations (arena: 2)
    if not stations.is_legacy():
        if not a.centers:
            ap.error('a config with a station set (k != 2 arena stations) needs the matching per-run --centers file')
        from rescuemind.stations import check_centers
        try:
            check_centers(load_centers(a),stations)
        except ValueError as e:
            ap.error(str(e))
    if a.memory_mode!='off' and a.memory_file:
        from rescuemind.mission_memory import MissionMemory
        mem_plan=MissionMemory(a.memory_file).plan(intent.item,a.memory_mode,stations=stations,
                                                   **({'caution_tau_h':site.caution_tau_h} if site is not None else {}))
    if a.advice_file or a.advice_from_instruction:
        # I-19: everything that is not the robot's own perception at the station is advice (memory, peer, inventory,
        # operator text).  The combined plan has the memory plan's schema, so the paths below handle both.
        from rescuemind.advice_llm import plan_for_mission
        mem_plan=plan_for_mission(intent.item,mem_plan,mode=a.advice_mode,advice_file=a.advice_file,
                                  from_instruction=a.advice_from_instruction,instruction=a.instruction,
                                  model=a.vlm_model,url=a.local_primary_url.replace('/v1/classify','/v1/advice'),stations=stations,
                                  scrutiny=a.advice_scrutiny,credit_path=a.advice_credit,
                                  filter_url=a.local_primary_url.replace('/v1/classify','/v1/advice_filter'))
    route=route_from_config(a.config,intent.item,station=(mem_plan or {}).get('first_station'))
    order=plan_order(mem_plan,stations,intent.item) if intent.item in ('water','medicine') else None
    record={'version':'3.1','run_id':run_id,'camera_max_age_s':a.camera_max_age,'lane':'Gazebo direct-drive through independent velocity relay, NOT Nav2',
            'run_type':(('local_vlm_live_mission' if a.inference_backend=='local' else 'jev_qwen_live_mission') if a.run_live else ('jev_qwen_mission' if a.run else ('motion_check_non_ai' if a.motion_check else 'dry_run'))),
            'instruction':a.instruction,'intent':intent.__dict__,
            'intent_gate':{'allow':selection.allow,'reason':selection.reason,'threshold':a.intent_min_score,
                           'backend':a.intent_backend,'llm':llm_intent},'route':route,
            'preflight':None,'checkpoint':None,'success':False,'events':[],'trace':[],
            'physical_pickup':False,'memory':mem_plan,'advice':(mem_plan or {}).get('advice'),
            'robot_runtime_verified_in_author_environment':False}
    if site is not None:
        record['site_config']=site.block()       # I-26: the audits take tau_h from here and compare it with every model call
    if a.clock_source!='sim' or a.camera_qos!='reliable' or a.odom_frame is not None or a.base_frame is not None:
        record['real_profile']={'clock_source':a.clock_source,'camera_qos':a.camera_qos,
                                'odom_frame':a.odom_frame,'base_frame':a.base_frame}
    if not stations.is_legacy():
        # I-21: k > 2 stations: the inventory, and the candidate order the recovery search follows (memory / advice may
        # have reordered it; the audit checks that no candidate was skipped)
        record['stations']=stations.to_block(); record['station_order']=order
    if a.inference_backend=='local':
        record['version']='3.2-local'
    print(json.dumps({k:v for k,v in record.items() if k not in ('trace','events')},ensure_ascii=False,indent=2))
    if not (a.run or a.run_live or a.motion_check):
        print('DRY RUN ONLY: no ROS publish or Jev request')
        return
    try:
        if not selection.allow:
            raise RuntimeError('mission intent rejected: '+selection.reason)
        if a.run:
            if not a.preflight_image or not a.corridor_image:
                raise RuntimeError('Jev mandatory: two fresh distinct images required to move')
            fresh_image(a.preflight_image);fresh_image(a.corridor_image)
            from rescuemind.multimodal_demo import run as preflight
            result=preflight(a.preflight_image,intent.item,qwen_model=a.qwen_model,
                             endpoint=a.qwen_endpoint,corridor_image=a.corridor_image)
            record['preflight']=result
            if not result['gate']['allow']:
                raise RuntimeError('Jev+Qwen DENIED: '+result['gate']['reason'])
        if a.run_live:
            if a.inference_backend == 'cloud':
                require_api_configuration(a.qwen_model)
            else:
                from rescuemind.local_vision import localhost_only
                localhost_only(a.local_primary_url)
                localhost_only(a.local_secondary_url)
                record['events'].append({'stage':'local_vision_selected','mode':a.local_mode,
                    't_wall_s':0.0,'cloud_api_required':False})
            record['events'].append({'stage':'intent_gate','allow':True,'reason':selection.reason, 't_wall_s':0.0})
        run_ros(route,a,record)
    except Exception as ex:
        record['events'].append({'stage':'error','type':type(ex).__name__,'message':str(ex)})
        raise
    finally:
        p=Path(a.out);p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Saved experiment record to',p)

if __name__=='__main__':main()
