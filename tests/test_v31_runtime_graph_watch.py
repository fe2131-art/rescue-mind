"""ROS-free tests of the real runtime publisher guard's pure policy."""
import unittest
import math
from pathlib import Path
from unittest.mock import patch
from rescuemind.runtime_guard_graph import (check_graph, endpoints, RuntimeGuardGraph,
                                             GraphMonitorFault)

GOOD_CMD=[dict(node_name='rescuemind_velocity_guard',node_namespace='/',topic_type='geometry_msgs/msg/Twist')]
GOOD_READY=[dict(node_name='rescuemind_velocity_guard',node_namespace='/',topic_type='std_msgs/msg/Bool')]

class TestV31RuntimeGraph(unittest.TestCase):
    def test_exact_guard_passes(self):
        self.assertTrue(check_graph(GOOD_CMD,GOOD_READY))
    def test_missing_velocity_guard_fails(self):
        with self.assertRaises(GraphMonitorFault):check_graph([],GOOD_READY)
    def test_missing_ready_publisher_fails(self):
        with self.assertRaises(GraphMonitorFault):check_graph(GOOD_CMD,[])
    def test_duplicate_velocity_publisher_fails(self):
        with self.assertRaises(GraphMonitorFault):check_graph(GOOD_CMD*2,GOOD_READY)
    def test_rogue_publisher_fails(self):
        with self.assertRaises(GraphMonitorFault):check_graph(GOOD_CMD+[dict(node_name='intruder',node_namespace='/',topic_type='geometry_msgs/msg/Twist')],GOOD_READY)
    def test_duplicate_guard_ready_fails(self):
        with self.assertRaises(GraphMonitorFault):check_graph(GOOD_CMD,GOOD_READY*2)
    def test_wrong_namespace_fails(self):
        with self.assertRaises(GraphMonitorFault):check_graph([{**GOOD_CMD[0],'node_namespace':'/evil'}],GOOD_READY)
    def test_wrong_ros_type_fails(self):
        with self.assertRaises(GraphMonitorFault):check_graph([{**GOOD_CMD[0],'topic_type':'geometry_msgs/msg/TwistStamped'}],GOOD_READY)
    def test_rogue_ready_fails(self):
        with self.assertRaises(GraphMonitorFault):check_graph(GOOD_CMD,[{**GOOD_READY[0],'node_name':'another'}])
    def test_invalid_row_fails(self):
        with self.assertRaises(GraphMonitorFault):check_graph([dict(node_name='x')],GOOD_READY)
    def test_unsupported_topic_fails(self):
        with self.assertRaises(GraphMonitorFault):endpoints('/camera',GOOD_CMD)
    def test_partial_discovery_initially_allowed(self):
        m=RuntimeGuardGraph(10,startup_grace_s=6)
        self.assertEqual(m.observe(10,[],[]),'waiting_for_guard_graph')
        self.assertEqual(m.observe(11,GOOD_CMD,[]),'waiting_for_guard_graph')
        self.assertFalse(m.armed)
        self.assertEqual(m.observe(12,GOOD_CMD,GOOD_READY),'sole_guard_confirmed')
        self.assertTrue(m.armed)
    def test_missing_graph_after_grace_latches(self):
        m=RuntimeGuardGraph(10,startup_grace_s=3)
        m.observe(11,[],[])
        with self.assertRaises(GraphMonitorFault):m.observe(14,[],[])
        with self.assertRaises(GraphMonitorFault):m.observe(15,GOOD_CMD,GOOD_READY)
    def test_new_rogue_during_startup_immediate_abort(self):
        m=RuntimeGuardGraph(10)
        with self.assertRaises(GraphMonitorFault):m.observe(10,GOOD_CMD*2,GOOD_READY)
    def test_new_rogue_after_arm_latches(self):
        m=RuntimeGuardGraph(10)
        m.observe(11,GOOD_CMD,GOOD_READY)
        with self.assertRaises(GraphMonitorFault):m.observe(12,GOOD_CMD*2,GOOD_READY)
        with self.assertRaises(GraphMonitorFault):m.observe(13,GOOD_CMD,GOOD_READY)
    def test_guard_disappears_after_arm_latches(self):
        m=RuntimeGuardGraph(10)
        m.observe(11,GOOD_CMD,GOOD_READY)
        with self.assertRaises(GraphMonitorFault):m.observe(12,[],GOOD_READY)
    def test_graph_time_regression_latches(self):
        m=RuntimeGuardGraph(10)
        m.observe(11,GOOD_CMD,GOOD_READY)
        with self.assertRaises(GraphMonitorFault):m.observe(10.5,GOOD_CMD,GOOD_READY)
    def test_nan_graph_time_rejected(self):
        m=RuntimeGuardGraph(10)
        with self.assertRaises(GraphMonitorFault):m.observe(float('nan'),GOOD_CMD,GOOD_READY)
    def test_invalid_init_rejected(self):
        for val in (0,float('nan'),float('inf'),61):
            with self.assertRaises(ValueError):RuntimeGuardGraph(10,startup_grace_s=val)
    def test_audit_valid_watch(self):
        import tempfile,json
        from rescuemind.runtime_guard_graph import audit_watch_jsonl
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'watch.jsonl'
            rows=[{'elapsed_s':.1,'state':'waiting_for_guard_graph','cmd_publishers':0,'guard_ready_publishers':0},
                  {'elapsed_s':.8,'state':'sole_guard_confirmed','cmd_publishers':1,'guard_ready_publishers':1},
                  {'elapsed_s':1.4,'state':'sole_guard_confirmed','cmd_publishers':1,'guard_ready_publishers':1}]
            p.write_text(''.join(json.dumps(x)+'\n' for x in rows))
            self.assertTrue(audit_watch_jsonl(p)['pass'])
    def test_audit_missing_log_fails(self):
        from rescuemind.runtime_guard_graph import audit_watch_jsonl
        with self.assertRaises(GraphMonitorFault):audit_watch_jsonl('/no/such/ros/watch.jsonl')
    def test_audit_rogue_log_fails(self):
        import tempfile,json
        from rescuemind.runtime_guard_graph import audit_watch_jsonl
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'watch.jsonl'
            p.write_text(''.join(json.dumps(x)+'\n' for x in [
                {'elapsed_s':.8,'state':'sole_guard_confirmed','cmd_publishers':1,'guard_ready_publishers':1},
                {'elapsed_s':1.8,'state':'FAILED_LATCHED','cmd_publishers':2,'guard_ready_publishers':1}]))
            with self.assertRaises(GraphMonitorFault):audit_watch_jsonl(p)
    def test_audit_not_enough_observations_fails(self):
        import tempfile,json
        from rescuemind.runtime_guard_graph import audit_watch_jsonl
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'watch.jsonl'
            p.write_text(json.dumps({'elapsed_s':1.,'state':'sole_guard_confirmed','cmd_publishers':1,'guard_ready_publishers':1})+'\n')
            with self.assertRaises(GraphMonitorFault):audit_watch_jsonl(p)
    def test_audit_non_monotonic_time_fails(self):
        import tempfile,json
        from rescuemind.runtime_guard_graph import audit_watch_jsonl
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'watch.jsonl'
            p.write_text(''.join(json.dumps(x)+'\n' for x in [
                {'elapsed_s':1.,'state':'sole_guard_confirmed','cmd_publishers':1,'guard_ready_publishers':1},
                {'elapsed_s':.9,'state':'sole_guard_confirmed','cmd_publishers':1,'guard_ready_publishers':1}]))
            with self.assertRaises(GraphMonitorFault):audit_watch_jsonl(p)
    def test_plan_watches_exact_guard(self):
        from scripts.v22_orchestrate import build_plan
        p=build_plan('live','避難所Bに飲料水を届けて',mission_timeout=300,scene='nominal',evidence_dir=Path('/tmp/1234567890abcdef'),capture_rosbag=True)
        names=[s.name for s in p['services']]
        self.assertIn('guard_graph_watch',names)
        self.assertLess(names.index('velocity_guard'),names.index('guard_graph_watch'))
        cmd=next(s.argv for s in p['services'] if s.name=='guard_graph_watch')
        self.assertIn('runtime_guard_graph_watch.py',' '.join(cmd))
        self.assertIn('guard_graph_watch.jsonl',' '.join(cmd))
        self.assertIn('rosbag_recorder',names)
    def test_motion_plan_also_watched(self):
        from scripts.v22_orchestrate import build_plan
        p=build_plan('motion-check','x',mission_timeout=300,evidence_dir=Path('/tmp/1234567890abcdef'))
        self.assertIn('guard_graph_watch',[x.name for x in p['services']])
        self.assertNotIn('rosbag_recorder',[x.name for x in p['services']])

if __name__=='__main__':unittest.main()


PENDING_CMD=[dict(node_name='_NODE_NAME_UNKNOWN_',node_namespace='_NODE_NAMESPACE_UNKNOWN_',
                  topic_type='geometry_msgs/msg/Twist')]


class TestPendingDiscoveryIdentity(unittest.TestCase):
    """Live Jazzy finding: rmw briefly reports the guard with a placeholder identity."""
    def test_pending_identity_tolerated_only_before_arming(self):
        g=RuntimeGuardGraph(0.,startup_grace_s=8.)
        self.assertEqual(g.observe(1.,PENDING_CMD,GOOD_READY),'waiting_for_guard_graph')
        self.assertEqual(g.observe(1.2,GOOD_CMD,GOOD_READY),'sole_guard_confirmed')
        with self.assertRaises(GraphMonitorFault):
            g.observe(1.4,PENDING_CMD,GOOD_READY)
    def test_pending_identity_latches_after_grace(self):
        g=RuntimeGuardGraph(0.,startup_grace_s=3.)
        with self.assertRaises(GraphMonitorFault):
            g.observe(3.5,PENDING_CMD,GOOD_READY)
    def test_pending_plus_guard_is_duplicate(self):
        g=RuntimeGuardGraph(0.,startup_grace_s=8.)
        with self.assertRaises(GraphMonitorFault):
            g.observe(1.,GOOD_CMD+PENDING_CMD,GOOD_READY)
