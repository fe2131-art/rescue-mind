import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from rescuemind.sim_clock_contract import SimClockContract,ClockContractError,stamp_ns
from rescuemind.bridge_contract import audit
from rescuemind.bag_evidence import audit_bag_metadata,BagEvidenceError
ROOT=Path(__file__).resolve().parents[1]

def valid_contract():
    c=SimClockContract()
    for sec in range(1,11):c.clock(sec,0)
    for sec in (3,4,5):
        for name in ('camera','scan','odom'):c.sensor(name,sec,0)
    return c

class ClockTests(unittest.TestCase):
    def test_healthy_sim_clock(self): self.assertTrue(valid_contract().report()['ok'])
    def test_wall_time_in_sensor_rejected(self):
        c=valid_contract();c.sensor('camera',1_792_000_000,0)
        self.assertIn('camera_not_in_simulation_time_domain',c.report()['issues'])
    def test_ros_clock_rewind_rejected(self):
        c=valid_contract();c.clock(2,0)
        self.assertIn('simulation_clock_rewound',c.report()['issues'])
    def test_paused_clock_does_not_count_as_advance(self):
        c=SimClockContract()
        for _ in range(30):c.clock(1,0)
        self.assertFalse(c.report()['ok'])
    def test_sensor_stamp_regression_rejected(self):
        c=valid_contract();c.sensor('scan',2,0)
        self.assertIn('scan_stamp_not_advancing',c.report()['issues'])
    def test_missing_clock_rejected(self):
        c=SimClockContract();c.sensor('camera',1,0)
        self.assertIn('clock_did_not_advance',c.report()['issues'])
    def test_missing_sensor_rejected(self):
        c=SimClockContract()
        for sec in range(1,8):c.clock(sec,0)
        self.assertIn('odom_insufficient_samples',c.report()['issues'])
    def test_invalid_nanosec(self):
        with self.assertRaises(ClockContractError):stamp_ns(5,1_000_000_000)
    def test_bool_stamp_not_valid_int(self):
        with self.assertRaises(ClockContractError):stamp_ns(True,0)
    def test_small_clock_skew_permitted(self):
        c=SimClockContract(max_skew_s=.3)
        for v in range(1,5):c.clock(v,0)
        for name in c.sensors:
            for s in (1,2):c.sensor(name,s,100_000_000)
        self.assertTrue(c.report()['ok'])

class BridgeTests(unittest.TestCase):
    def test_bridge_source_matches_world(self):
        self.assertTrue(audit(ROOT/'worlds/rescuemind_test_arena.sdf',ROOT/'configs/ros_gz_bridge_v20.yaml')['ok'])
    def test_clock_cannot_be_bidirectional(self):
        content=(ROOT/'configs/ros_gz_bridge_v20.yaml').read_text().replace('direction: GZ_TO_ROS','direction: BIDIRECTIONAL',1)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.yaml';p.write_text(content)
            with self.assertRaises(ValueError):audit(ROOT/'worlds/rescuemind_test_arena.sdf',p)
    def test_world_name_cannot_differ(self):
        content=(ROOT/'worlds/rescuemind_test_arena.sdf').read_text().replace('name="rescuemind_arena"','name="wrong"',1)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.sdf';p.write_text(content)
            with self.assertRaises(ValueError):audit(p,ROOT/'configs/ros_gz_bridge_v20.yaml')

class BagTests(unittest.TestCase):
    def make_bag(self,d,clock):
        import yaml
        p=Path(d)
        req=('/odom','/cmd_vel','/camera','/scan','/rescuemind/cmd_vel_request')
        rows=[{'topic_metadata':{'name':t},'message_count':4} for t in req]
        if clock:rows.append({'topic_metadata':{'name':'/clock'},'message_count':7})
        obj={'rosbag2_bagfile_information':{'topics_with_message_count':rows,'relative_file_paths':['recording.db3']}}
        (p/'metadata.yaml').write_text(yaml.safe_dump(obj));(p/'recording.db3').write_bytes(b'x'*1024)
    def test_sim_bag_clock_required(self):
        with tempfile.TemporaryDirectory() as d:
            self.make_bag(d,False)
            with self.assertRaises(BagEvidenceError):audit_bag_metadata(d,require_clock=True)
    def test_sim_bag_clock_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            self.make_bag(d,True)
            self.assertTrue(audit_bag_metadata(d,require_clock=True)['pass'])
    def test_legacy_bag_still_supported(self):
        with tempfile.TemporaryDirectory() as d:
            self.make_bag(d,False)
            self.assertTrue(audit_bag_metadata(d)['pass'])

class OrchestratorTests(unittest.TestCase):
    def test_plan_clock_and_bag_consistent(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('v20_orchestrate',ROOT/'scripts/v20_orchestrate.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        plan=mod.build_plan('live','避難所Bに飲料水を届けて',mission_timeout=440,evidence_dir=ROOT/'outputs/runs'/'0123456789abcdef',capture_rosbag=True)
        bag=[x for x in plan['services'] if x.name=='rosbag_recorder'][0]
        flat=' '.join(bag.argv)
        self.assertIn('--use-sim-time',flat)
        self.assertIn('/clock',flat)
        self.assertTrue(str(plan['readiness'][1]).endswith('v20_live_readiness.sh'))

if __name__=='__main__':unittest.main()
