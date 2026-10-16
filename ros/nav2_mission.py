"""ROS 2 Jazzy Nav2 bridge for RescueMind (NOT tested against actual ROS here).

- Default is a dry-run requiring NO ROS environment.
- --run controls the real simulated TurtleBot3 via Nav2 Simple Commander.
- Goals are user-calibrated map coordinates (configs/poses.example.json).
- --dynamic-obstacle experimentally inserts a Gazebo box on the delivery route.
- A research-only LiDAR / operator E-stop watchdog cancels the Nav2 action.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
from math import cos, sin
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.intent import IntentClassifier  # noqa: E402
from rescuemind.watchdog import Watchdog  # noqa: E402


def mission(instruction: str, classifier: str, config: str):
    data=json.loads(Path(config).read_text(encoding='utf-8'))
    for key in ('initial','water','medicine','A','B'):
        if key not in data or len(data[key])!=3 or not all(isinstance(x,(int,float)) for x in data[key]):
            raise ValueError(f'Expected [x,y,yaw_radians] in config at {key}')
    intent=IntentClassifier(classifier).classify(instruction)
    steps=[('pickup',intent.item,data[intent.item]),('delivery',intent.shelter,data[intent.shelter])]
    return data,intent,steps


def pose(navigator, xyz):
    from geometry_msgs.msg import PoseStamped
    x,y,yaw=xyz
    p=PoseStamped()
    p.header.frame_id='map'
    p.header.stamp=navigator.get_clock().now().to_msg()
    p.pose.position.x=float(x)
    p.pose.position.y=float(y)
    p.pose.orientation.z=sin(float(yaw)/2)
    p.pose.orientation.w=cos(float(yaw)/2)
    return p


def execute(data, steps, args, record):
    try:
        import rclpy
        from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
        from rclpy.parameter import Parameter
        from sensor_msgs.msg import LaserScan
        from std_msgs.msg import Bool
    except ImportError as e:
        raise SystemExit('ROS 2 Jazzy / nav2_simple_commander not available. Source /opt/ros/jazzy/setup.bash: '+str(e))
    rclpy.init()
    navigator=BasicNavigator()
    try:
        # Match Gazebo /clock when producing PoseStamped timestamps.
        if navigator.has_parameter('use_sim_time'):
            navigator.set_parameters([Parameter('use_sim_time', value=True)])
        else:
            navigator.declare_parameter('use_sim_time', True)
        # Navigation gets a localization seed matching the configured Gazebo spawn pose.
        navigator.setInitialPose(pose(navigator,data['initial']))
        print('Waiting for Nav2 lifecycle and AMCL...')
        navigator.waitUntilNav2Active()
        # Watchdog runs on raw LiDAR front sector and a latched operator E-stop.
        # It is NOT a certified safety system; Nav2 costmap still performs obstacle avoidance.
        watchdog=Watchdog(min_front_m=args.min_front_m,
                          max_scan_age_s=args.max_scan_age_s,
                          startup_grace_s=args.startup_grace_s,
                          started_at=time.monotonic())
        def scan_cb(msg):
            watchdog.update_scan(msg.ranges, msg.angle_min, msg.angle_increment,
                                 msg.range_min, msg.range_max, time.monotonic())
        def estop_cb(msg):
            watchdog.emergency_stop(bool(msg.data))
        # Keep subscriptions alive until mission finishes.
        scan_sub=navigator.create_subscription(LaserScan,args.scan_topic,scan_cb,10)
        estop_sub=navigator.create_subscription(Bool,args.estop_topic,estop_cb,10)
        previous=data['initial']
        for stage,name,xyz in steps:
            beginning=pose(navigator,previous)
            target=pose(navigator,xyz)
            path=navigator.getPath(beginning,target)
            if path is None or len(path.poses)<2:
                record['events'].append({'stage':stage,'status':'no_path','goal':xyz})
                raise RuntimeError(f'Nav2 cannot plan to {name} at {xyz}; inspect RViz and edit config')
            # getPath and goToPose rely on Nav2 for global/local planning (not our grid A*).
            navigator.goToPose(target)
            start=time.monotonic()
            inserted=False
            while not navigator.isTaskComplete():
                # Poll subscription callbacks while the Nav2 action is in flight.
                # If ROS receives no scan or an operator sends E-stop, cancel.
                rclpy.spin_once(navigator, timeout_sec=0.02)
                abort_reason=watchdog.check(time.monotonic())
                if abort_reason:
                    navigator.cancelTask()
                    record['events'].append({'stage':stage,'status':'watchdog_abort',
                                             'reason':abort_reason})
                    raise RuntimeError('Watchdog cancelled navigation: '+abort_reason)
                elapsed=time.monotonic()-start
                if args.dynamic_obstacle and stage=='delivery' and not inserted and elapsed>args.obstacle_delay:
                    inserted=True
                    sample=path.poses[min(len(path.poses)-2,max(1,int(len(path.poses)*0.55)))].pose.position
                    # Caveat: Nav2 map and Gazebo world frames must be aligned.
                    from spawn_box import spawn
                    try:
                        report=spawn(float(sample.x),float(sample.y),args.world,args.obstacle_width)
                        record['events'].append({'stage':stage,'status':'gazebo_obstacle_spawned','details':report})
                        print('Dynamic blockage inserted:', report)
                    except Exception as e:
                        record['events'].append({'stage':stage,'status':'obstacle_error','message':str(e)})
                        print('Obstacle not inserted:',e)
                if elapsed>args.timeout:
                    navigator.cancelTask()
                    record['events'].append({'stage':stage,'status':'timeout','elapsed':round(elapsed,2)})
                    raise TimeoutError(f'Navigation timeout at {stage}')
                time.sleep(0.1)
            status=navigator.getResult()
            record['events'].append({'stage':stage,'name':name,'status':str(status),
                                     'elapsed_wall_sec':round(time.monotonic()-start,2),'goal':xyz})
            if status!=TaskResult.SUCCEEDED:
                raise RuntimeError(f'Nav2 task failed at {stage}: {status}')
            previous=xyz
        record['success']=True
        print('All navigation tasks reached their goals (no physical item grasping).')
    finally:
        navigator.destroyNode()
        rclpy.shutdown()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--instruction', default='避難所Bの飲料水が不足しています。水を届けて')
    p.add_argument('--classifier',choices=['tfidf','keyword','minilm'],default='tfidf')
    p.add_argument('--config',default=str(ROOT/'configs/poses.example.json'))
    p.add_argument('--run',action='store_true',help='actually send goals to ROS 2 Nav2; otherwise dry-run')
    p.add_argument('--preflight-image',help='Actual camera snapshot REQUIRED with --run; Jev + Qwen3.5 fail-closed gate')
    p.add_argument('--corridor-image',help='Required independent corridor frame')
    p.add_argument('--qwen-model',default='Qwen/Qwen3.5-4B')
    p.add_argument('--qwen-endpoint',default='http://127.0.0.1:8000/v1/chat/completions')
    p.add_argument('--min-confidence',type=float,default=0.55,help='heuristic threshold for tfidf probability; not calibrated')
    p.add_argument('--dynamic-obstacle',action='store_true',help='experimental Gazebo spawn during delivery')
    p.add_argument('--obstacle-delay',type=float,default=1.0)
    p.add_argument('--obstacle-width',type=float,default=0.7)
    p.add_argument('--world',default='auto')
    p.add_argument('--timeout',type=float,default=180.0)
    p.add_argument('--scan-topic',default='/scan')
    p.add_argument('--estop-topic',default='/rescuemind/estop')
    p.add_argument('--min-front-m',type=float,default=0.30)
    p.add_argument('--max-scan-age-s',type=float,default=2.0)
    p.add_argument('--startup-grace-s',type=float,default=4.0)
    p.add_argument('--preflight-max-age-s',type=float,default=120.0)
    p.add_argument('--output',default='outputs/ros_mission.json')
    a=p.parse_args()
    data,intent,steps=mission(a.instruction,a.classifier,a.config)
    record={'instruction':a.instruction,'intent':asdict(intent),
            'steps':[{'stage':s,'target':name,'pose_map':xyz} for s,name,xyz in steps],
            'is_ros_executed':bool(a.run),'success':False,'events':[]}
    print(json.dumps(record,indent=2,ensure_ascii=False))
    if a.run:
        try:
            if not a.preflight_image or not a.corridor_image:
                raise RuntimeError('v0.3 requires --preflight-image and --corridor-image: Jev is mandatory for Nav2 operation')
            if not 0 < a.min_front_m < 2 or a.max_scan_age_s <= 0 or a.startup_grace_s <= 0:
                raise ValueError('Invalid watchdog limits')
            # Avoid granting motion from an old, unrelated camera capture.
            # File mtime is not a signed timestamp: operational safeguard only.
            for source in (a.preflight_image, a.corridor_image):
                age=time.time()-Path(source).stat().st_mtime
                if age< -5 or age > a.preflight_max_age_s:
                    raise RuntimeError(f'Camera snapshot stale/future ({age:.1f}s): {source}')
            from rescuemind.multimodal_demo import run as multimodal_run
            perception = multimodal_run(a.preflight_image, intent.item, qwen_model=a.qwen_model, endpoint=a.qwen_endpoint, corridor_image=a.corridor_image)
            record['preflight'] = perception
            if not perception['gate']['allow']:
                raise RuntimeError('Jev/Qwen preflight DENIED: '+perception['gate']['reason'])
            if a.classifier=='tfidf' and intent.confidence<a.min_confidence:
                raise ValueError(f'Ambiguous instruction (prob={intent.confidence:.3f} < {a.min_confidence:.3f}); request clarification')
            execute(data,steps,a,record)
        except Exception as e:
            record['events'].append({'status':'exception','message':str(e)})
            raise
        finally:
            o=Path(a.output);o.parent.mkdir(parents=True,exist_ok=True)
            o.write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8')
            print('ROS execution log:',o)
    else:
        print('DRY RUN: no ROS goals sent. Add --run after checking coordinates in RViz.')

if __name__=='__main__':
    main()
