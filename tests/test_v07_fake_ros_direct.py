"""Simulated ros2 messages and ideal kinematics; NOT actual Gazebo testing."""
import importlib.util
import math
import sys
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from rescuemind.waypoint import Pose2, MotionCommand, integrate

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rm_direct07',ROOT/'ros/gazebo_waypoint_mission.py')
drive=importlib.util.module_from_spec(spec);spec.loader.exec_module(drive)

# A textured synthetic RGB frame: previous all-white fixture correctly fails v2.7.
TEXTURED_FRAME = bytes((v,v,v) for v in []) if False else b''.join(
    bytes(((x*3+y*2)%240+8,)*3) for y in range(320) for x in range(320))

class Twist:
    def __init__(self):self.linear=NS(x=0.);self.angular=NS(z=0.)

class FakeNode:
    def __init__(self):
        self.handlers={};self.cmd=MotionCommand(0,0);self.pose=Pose2(0,0,0);self.stopped_calls=0
    def create_subscription(self,cls,topic,fn,qos):
        self.handlers[topic]=fn
        return fn
    def create_publisher(self,cls,topic,qos):
        owner=self
        class Publisher:
            def publish(self,msg):
                owner.cmd=MotionCommand(msg.linear.x,msg.angular.z)
                if msg.linear.x == 0 and msg.angular.z == 0: owner.stopped_calls+=1
        return Publisher()
    def destroy_node(self):pass

class TestROSBridgeEndToEndStub(unittest.TestCase):
    def run_stub(self,permit,run_type="jev_qwen_mission", stop_camera_after=None, camera_max_age=3.,
                 disturb_stationary=False, camera_style="textured", sim_clock_bias_s=0.0, local=False):
        fake=FakeNode();clock=[0.];real_sleep=time.sleep
        rclpy=types.ModuleType('rclpy')
        rclpy.init=lambda:None;rclpy.shutdown=lambda:None
        rclpy.create_node=lambda name:fake
        def spin_once(node,timeout_sec=.1):
            clock[0]+=.08
            node.pose=integrate(node.pose,node.cmd,.08)
            # Inject a persistent post-alignment external push. The robot is
            # commanded to STOP, but actual odometry continues to change.
            if disturb_stationary and any(e.get('stage')=='camera_aim_aligned' for e in record['events']):
                node.pose=Pose2(node.pose.x+.037,node.pose.y,node.pose.yaw)
            x,y,yaw=node.pose.x,node.pose.y,node.pose.yaw
            odom=NS(pose=NS(pose=NS(position=NS(x=x,y=y),orientation=NS(x=0.,y=0.,z=math.sin(yaw/2),w=math.cos(yaw/2)))), twist=NS(twist=NS(linear=NS(x=node.cmd.linear,y=0.,z=0.),angular=NS(x=0.,y=0.,z=node.cmd.angular))))
            node.handlers['/odom'](odom)
            node.handlers['/scan'](NS(ranges=[3.]*360,angle_min=-math.pi,angle_increment=2*math.pi/360,range_min=.08,range_max=10.))
            ct=clock[0]+1+sim_clock_bias_s
            node.handlers['/clock'](NS(clock=NS(sec=int(ct),nanosec=int((ct%1)*1e9))))
            if stop_camera_after is None or clock[0] < stop_camera_after:
                test_frame = (TEXTURED_FRAME if camera_style=='textured' else
                              bytes([{'black':0,'white':255,'flat':128}[camera_style]])*320*320*3)
                node.handlers['/camera'](NS(encoding='rgb8',width=320,height=320,step=960,data=test_frame, header=NS(stamp=NS(sec=int(clock[0])+1,nanosec=int((clock[0]%1)*1e9)))))
            real_sleep(.0002) # allow the async checkpoint thread to run
        rclpy.spin_once=spin_once
        qos=types.ModuleType('rclpy.qos');qos.qos_profile_sensor_data=object()
        qos.QoSProfile=lambda **kw:kw
        qos.ReliabilityPolicy=qos.HistoryPolicy=qos.DurabilityPolicy=types.SimpleNamespace(RELIABLE=1,KEEP_LAST=1,VOLATILE=1)
        rclpy.qos=qos
        typesmap={'rclpy':rclpy,'rclpy.qos':qos,
                  'geometry_msgs.msg':NS(Twist=Twist),
                  'nav_msgs.msg':NS(Odometry=object),
                  'sensor_msgs.msg':NS(LaserScan=object,Image=object),
                  'std_msgs.msg':NS(Bool=object),
                  'rosgraph_msgs.msg':NS(Clock=object)}
        args=NS(cmd_topic='/cmd_vel',odom_topic='/odom',scan_topic='/scan',estop_topic='/estop',
                camera_topic='/camera',min_front_m=.27,scan_max_age=2.0,warmup=.1,
                stage_timeout=50.,camera_wait=5.,aim_timeout=14.,settle_timeout=7.,checkpoint_timeout=40.,
                checkpoint_image='/tmp/rescuemind_v07_fake_ros_camera.jpg',camera_max_age=camera_max_age,qwen_model='qwen3.8-omni-flash',qwen_endpoint='unused',inference_backend='local' if local else 'cloud',local_mode='single',local_primary_url='http://127.0.0.1:8765/v1/classify',local_secondary_url='http://127.0.0.1:8766/v1/classify')
        record={'run_type':run_type,'success':False,'events':[],'trace':[],'checkpoint':None}
        def fake_verify(f,expected,*,qwen_model,endpoint):
            return {'decision':{'allow':permit,'reason':'on_site_supply_confirmed' if permit else 'models_disagree_or_wrong_supply'},
                    'image_sha256':__import__('hashlib').sha256(Path(f).read_bytes()).hexdigest(),
                    'model_calls':{'jev':{'model':'jev-1.14.0'},'qwen':{'model':'qwen3.8-omni-flash'}}}
        def fake_verify_local(f,expected,*,mode,primary_url,secondary_url):
            return {'decision':{'allow':permit,'reason':'on_site_supply_confirmed' if permit else 'local_vlm_disagree_or_wrong_supply'},
                    'backend':'OFFLINE_MOCK_ONLY','image_sha256':__import__('hashlib').sha256(Path(f).read_bytes()).hexdigest()}
        def fake_sleep(seconds):
            clock[0]+=seconds
            real_sleep(.0001)
        with patch.dict(sys.modules,typesmap),\
             patch.object(drive.time,'monotonic',side_effect=lambda:clock[0]),\
             patch.object(drive.time,'sleep',side_effect=fake_sleep),\
             patch('rescuemind.checkpoint.verify_station',side_effect=fake_verify),\
             patch('rescuemind.local_vision.verify_station_local',side_effect=fake_verify_local):
            if camera_style!='textured':
                from rescuemind.image_acquisition import AcquisitionRejected
                with self.assertRaisesRegex(AcquisitionRejected,'poor_checkpoint_image_quality'):
                    drive.run_ros([('supply_station','water',(0.50,0)),('shelter_approach','B',(1.0,0))],args,record)
            elif disturb_stationary:
                with self.assertRaisesRegex(TimeoutError,'physical stationarity not verified'):
                    drive.run_ros([('supply_station','water',(0.50,0)),('shelter_approach','B',(1.0,0))],args,record)
            elif stop_camera_after is not None:
                with self.assertRaisesRegex(RuntimeError,'camera watchdog stopped mission'):
                    drive.run_ros([('supply_station','water',(0.50,0)),('shelter_approach','B',(1.0,0))],args,record)
            elif sim_clock_bias_s:
                from rescuemind.camera_clock_gate import CameraClockRejected
                with self.assertRaisesRegex(CameraClockRejected,'camera_acquisition_too_old'):
                    drive.run_ros([('supply_station','water',(0.50,0)),('shelter_approach','B',(1.0,0))],args,record)
            elif permit:drive.run_ros([('supply_station','water',(0.50,0)),('shelter_approach','B',(1.0,0))],args,record)
            else:
                with self.assertRaisesRegex(RuntimeError,'checkpoint DENIED'):
                    drive.run_ros([('supply_station','water',(0.50,0)),('shelter_approach','B',(1.0,0))],args,record)
        return fake,record
    def test_v32_mock_local_on_site_approval(self):
        _,record=self.run_stub(True,run_type='local_vlm_live_mission',local=True)
        self.assertTrue(record['success'])
        self.assertEqual([e['stage'] for e in record['events'] if e.get('arrived')],['supply_station','shelter_approach'])
        self.assertEqual(record['checkpoint']['backend'],'OFFLINE_MOCK_ONLY')
    def test_v32_mock_local_on_site_denial(self):
        _,record=self.run_stub(False,run_type='local_vlm_live_mission',local=True)
        self.assertFalse(record['success'])
        self.assertEqual([e['stage'] for e in record['events'] if e.get('arrived')],['supply_station'])
    def test_v28_stale_ros_camera_stamps_rejected_despite_advance(self):
        fake,rec=self.run_stub(True,run_type='jev_qwen_live_mission',sim_clock_bias_s=3.0)
        self.assertFalse(rec['success'])
        self.assertIsNone(rec['checkpoint'])
        self.assertNotIn('checkpoint_frame',[e['stage'] for e in rec['events']])
        self.assertGreater(fake.stopped_calls,5)

    def test_approval_allows_second_leg(self):
        fake,record=self.run_stub(True)
        self.assertTrue(record['success'])
        self.assertTrue(record['checkpoint']['decision']['allow'])
        self.assertEqual([e['stage'] for e in record['events'] if e.get('arrived')],['supply_station','shelter_approach'])
        self.assertGreater(fake.stopped_calls,5)
    def test_v08_live_mode_approval_allows_second_leg(self):
        fake,record=self.run_stub(True,run_type='jev_qwen_live_mission')
        self.assertTrue(record['success'])
        self.assertTrue(record['checkpoint']['decision']['allow'])
        self.assertEqual([e['stage'] for e in record['events'] if e.get('arrived')],['supply_station','shelter_approach'])
    def test_v08_live_mode_denial_blocks_second_leg(self):
        fake,record=self.run_stub(False,run_type='jev_qwen_live_mission')
        self.assertFalse(record['success'])
        self.assertEqual([e['stage'] for e in record['events'] if e.get('arrived')],['supply_station'])
    def test_v11_camera_freeze_stops_robot_even_with_clear_lidar(self):
        fake,record=self.run_stub(True,run_type='jev_qwen_live_mission',stop_camera_after=1.5,camera_max_age=1.0)
        self.assertFalse(record['success'])
        self.assertGreater(fake.stopped_calls,5)
        self.assertIn('camera_watchdog_abort',[e['stage'] for e in record['events']])

    def test_v26_external_push_blocks_vlm_and_second_leg(self):
        fake, record=self.run_stub(True,run_type='jev_qwen_live_mission',disturb_stationary=True)
        self.assertFalse(record['success'])
        self.assertIsNone(record['checkpoint'])
        self.assertEqual([e['stage'] for e in record['events'] if e.get('arrived')], ['supply_station'])
        self.assertNotIn('checkpoint_frame',[e['stage'] for e in record['events']])
        self.assertGreater(fake.stopped_calls,5)

    def test_v26_stationarity_proof_precedes_live_inference(self):
        _,record=self.run_stub(True,run_type='jev_qwen_live_mission')
        events=[e['stage'] for e in record['events']]
        self.assertLess(events.index('camera_aim_aligned'), events.index('checkpoint_stationary_verified'))
        self.assertLess(events.index('checkpoint_stationary_verified'), events.index('checkpoint_frame'))
        self.assertLess(events.index('checkpoint_frame'), events.index('checkpoint_decision'))

    def test_v27_black_frame_blocks_real_mission_core(self):
        _,rec=self.run_stub(True,run_type='jev_qwen_live_mission',camera_style='black')
        self.assertIsNone(rec['checkpoint'])
        self.assertNotIn('checkpoint_frame',[r['stage'] for r in rec['events']])
    def test_v27_white_frame_blocks_real_mission_core(self):
        _,rec=self.run_stub(True,run_type='jev_qwen_live_mission',camera_style='white')
        self.assertIsNone(rec['checkpoint'])
    def test_v27_gray_frame_blocks_real_mission_core(self):
        _,rec=self.run_stub(True,run_type='jev_qwen_live_mission',camera_style='flat')
        self.assertIsNone(rec['checkpoint'])
    def test_jev_qwen_disagreement_prevents_second_leg(self):
        fake,record=self.run_stub(False)
        self.assertFalse(record['success'])
        self.assertEqual([e['stage'] for e in record['events'] if e.get('arrived')],['supply_station'])
        self.assertFalse(record['checkpoint']['decision']['allow'])
        self.assertGreater(fake.stopped_calls,5)
if __name__=='__main__':unittest.main()
