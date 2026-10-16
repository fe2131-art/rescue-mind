"""Nav2 integration test using fake ROS modules; not evidence of real ROS execution."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('rescuemind_nav2_mission', ROOT/'ros/nav2_mission.py')
bridge=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)

class FakeBasicNavigator:
    latest=None
    def __init__(self):
        self.sim_calls=0;self.cancelled=False;self.goal_count=0;self.handlers={};FakeBasicNavigator.latest=self
    def has_parameter(self,k):return True
    def set_parameters(self,v):pass
    def get_clock(self):return NS(now=lambda:NS(to_msg=lambda:0))
    def setInitialPose(self,p):pass
    def waitUntilNav2Active(self):pass
    def create_subscription(self,msg,topic,callback,qos):self.handlers[topic]=callback;return callback
    def getPath(self,start,target):return NS(poses=[NS(pose=NS(position=NS(x=0.0,y=0.0))),NS(pose=NS(position=NS(x=1.0,y=1.0)))])
    def goToPose(self,pose):self.sim_calls=0;self.goal_count+=1
    def isTaskComplete(self):return self.sim_calls>0
    def cancelTask(self):self.cancelled=True
    def getResult(self):return 'SUCCEEDED'
    def destroyNode(self):pass

class FakePose:
    def __init__(self):self.header=NS(frame_id='',stamp=None);self.pose=NS(position=NS(x=None,y=None),orientation=NS(z=0.0,w=1.0))

class TestFakeRosIntegration(unittest.TestCase):
    def execute_fake(self,scan_range=1.0,estop=False):
        rclpy=types.ModuleType('rclpy');rclpy.init=lambda:None;rclpy.shutdown=lambda:None
        def spin_once(nav,timeout_sec):
            nav.sim_calls+=1
            scan=NS(ranges=[scan_range]*31,angle_min=-.3,angle_increment=.02,range_min=.08,range_max=10)
            nav.handlers['/scan'](scan)
            if estop:nav.handlers['/rescuemind/estop'](NS(data=True))
        rclpy.spin_once=spin_once
        rclpy_param=types.ModuleType('rclpy.parameter');rclpy_param.Parameter=lambda *a,**kw:None
        nav_pkg=types.ModuleType('nav2_simple_commander');nav_mod=types.ModuleType('nav2_simple_commander.robot_navigator')
        nav_mod.BasicNavigator=FakeBasicNavigator;nav_mod.TaskResult=NS(SUCCEEDED='SUCCEEDED')
        geom_pkg=types.ModuleType('geometry_msgs');geom_msg=types.ModuleType('geometry_msgs.msg');geom_msg.PoseStamped=FakePose
        sensor_pkg=types.ModuleType('sensor_msgs');sensor_msg=types.ModuleType('sensor_msgs.msg');sensor_msg.LaserScan=object
        std_pkg=types.ModuleType('std_msgs');std_msg=types.ModuleType('std_msgs.msg');std_msg.Bool=object
        modules={'rclpy':rclpy,'rclpy.parameter':rclpy_param,'nav2_simple_commander':nav_pkg,
                 'nav2_simple_commander.robot_navigator':nav_mod,'geometry_msgs':geom_pkg,'geometry_msgs.msg':geom_msg,
                 'sensor_msgs':sensor_pkg,'sensor_msgs.msg':sensor_msg,'std_msgs':std_pkg,'std_msgs.msg':std_msg}
        args=NS(min_front_m=.30,max_scan_age_s=2.0,startup_grace_s=4.0,scan_topic='/scan',
                estop_topic='/rescuemind/estop',dynamic_obstacle=False,obstacle_delay=1000,
                timeout=5,obstacle_width=.7,world='auto')
        record={'events':[],'success':False}
        with patch.dict(sys.modules,modules):
            if scan_range < .3 or estop:
                with self.assertRaisesRegex(RuntimeError,'Watchdog cancelled'):
                    bridge.execute({'initial':[0,0,0]},[('pickup','water',[1,1,0])],args,record)
            else:
                bridge.execute({'initial':[0,0,0]},[('pickup','water',[1,1,0]),('delivery','B',[2,2,0])],args,record)
        return record,FakeBasicNavigator.latest
    def test_fake_ros_goal_sequence(self):
        rec,nav=self.execute_fake()
        self.assertTrue(rec['success'])
        self.assertEqual(nav.goal_count,2)
    def test_fake_ros_lidar_abort(self):
        rec,nav=self.execute_fake(scan_range=.15)
        self.assertTrue(nav.cancelled)
        self.assertIn('watchdog_abort', [e['status'] for e in rec['events']])
    def test_fake_ros_operator_abort(self):
        rec,nav=self.execute_fake(estop=True)
        self.assertTrue(nav.cancelled)
        self.assertEqual(rec['events'][0]['reason'],'operator_emergency_stop')

if __name__=='__main__':unittest.main()
