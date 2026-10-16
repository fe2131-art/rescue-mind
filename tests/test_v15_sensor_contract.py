import importlib.util
import math
import random
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import patch
from rescuemind.sensor_contract import StreamAudit

ROOT = Path(__file__).resolve().parents[1]

def stamp(i): return N(stamp=N(sec=1+i, nanosec=0),frame_id='odom')
def camera(i=0,**kw):
    d=dict(header=stamp(i),encoding='rgb8',width=320,height=240,step=960,
           data=b'\x10' * (320*240*3),is_bigendian=0)
    d.update(kw);return N(**d)
def scan(i=0,**kw):
    d=dict(header=stamp(i),ranges=[float('inf')]*360,
           angle_min=-math.pi,angle_max=math.pi,angle_increment=math.pi/180,
           range_min=.08,range_max=10.0)
    d.update(kw);return N(**d)
def odom(i=0,**kw):
    d=dict(header=stamp(i),child_frame_id='base_link',
           pose=N(pose=N(position=N(x=0.,y=0.,z=0.), orientation=N(x=0.,y=0.,z=0.,w=1.))))
    d.update(kw);return N(**d)

class StreamContractTests(unittest.TestCase):
    def test_positive_sequence(self):
        check=StreamAudit()
        for i in range(3):
            check.add_image(camera(i));check.add_scan(scan(i));check.add_odom(odom(i))
        self.assertTrue(check.report()['ok'])
        self.assertEqual(check.report()['distinct_timestamps']['camera'],3)

    def test_missing_topic_blocks(self):
        check=StreamAudit()
        for i in range(4): check.add_image(camera(i));check.add_scan(scan(i))
        self.assertFalse(check.report()['ok'])
        self.assertEqual(check.report()['missing']['odom'],3)

    def test_duplicate_stamp_does_not_count(self):
        check=StreamAudit();check.add_image(camera(0));check.add_image(camera(0))
        self.assertEqual(check.counts['camera'],1)

    def test_regression_rejected(self):
        check=StreamAudit();check.add_scan(scan(4))
        with self.assertRaisesRegex(ValueError,'regression'):
            check.add_scan(scan(2))

    def test_camera_invalid_payloads(self):
        for item in [dict(encoding='jpeg'),dict(width=319),dict(step=100),
                     dict(data=b'x'*10), dict(is_bigendian=4)]:
            with self.subTest(item=item), self.assertRaises(ValueError):
                StreamAudit().add_image(camera(**item))

    def test_scan_invalid_payloads(self):
        for item in [dict(ranges=[math.nan]*360),dict(ranges=[-math.inf]*360),
                     dict(ranges=[0.3]*50),dict(angle_increment=0),dict(range_max=-1)]:
            with self.subTest(item=str(item)[:50]),self.assertRaises(ValueError):
                StreamAudit().add_scan(scan(**item))

    def test_odom_invalid_payloads(self):
        for item in [odom(child_frame_id='unknown'),odom(header=N(stamp=N(sec=0,nanosec=0),frame_id='odom'))]:
            with self.subTest(item=item),self.assertRaises(ValueError):
                StreamAudit().add_odom(item)
        obj=odom(); obj.pose.pose.position.x=math.nan
        with self.assertRaises(ValueError): StreamAudit().add_odom(obj)

    def test_stress_mutation_fail_closed(self):
        r=random.Random(20261016)
        for i in range(400):
            test=StreamAudit()
            x=r.randrange(4)
            if x==0:
                f=camera(data=b'x'*r.randrange(0,1000))
                with self.assertRaises(ValueError):test.add_image(f)
            elif x==1:
                f=scan(ranges=[math.nan]*360)
                with self.assertRaises(ValueError):test.add_scan(f)
            elif x==2:
                f=odom(child_frame_id='map')
                with self.assertRaises(ValueError):test.add_odom(f)
            else:
                test.add_scan(scan(2))
                with self.assertRaises(ValueError):test.add_scan(scan(1))

    def test_orchestrator_runtime_probe_required(self):
        spec=importlib.util.spec_from_file_location('v15_orch',ROOT/'scripts/v15_orchestrate.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        plan=module.build_plan('live','避難所Bに水',mission_timeout=300)
        self.assertTrue(plan['readiness'][-1].endswith('v15_live_readiness.sh'))
        self.assertEqual([s.name for s in plan['services']],['gazebo','bridge','velocity_guard'])
        self.assertIn('--run-live',plan['mission'].argv[-1])

if __name__=='__main__':unittest.main()
