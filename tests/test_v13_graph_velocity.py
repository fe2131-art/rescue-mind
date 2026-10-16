"""v1.3 safety contract regression; no actual Gazebo or DDS claims."""
import unittest
from types import SimpleNamespace as N
from rescuemind.velocity_relay import VelocityRelay, planar_request_components
from rescuemind.ros_graph_contract import publisher_names, assert_guard_topology


def twist(v=0.1,w=0.,**parts):
    linear=N(x=v,y=parts.get('linear_y',0.),z=parts.get('linear_z',0.))
    angular=N(x=parts.get('angular_x',0.),y=parts.get('angular_y',0.),z=w)
    return N(linear=linear,angular=angular)


def graph(*nodes):
    entries=[]
    for name in nodes:
        entries.append(f'Node name: {name}\nNode namespace: /\nTopic type: geometry_msgs/msg/Twist\nEndpoint type: PUBLISHER\nGID: 00:01\n')
    return 'Type: geometry_msgs/msg/Twist\nPublisher count: '+str(len(nodes))+'\n'+'\n'.join(entries)

class V13SafetyContracts(unittest.TestCase):
    def test_reverse_not_allowed_without_rear_scan(self):
        r=VelocityRelay(0.)
        r.request(-0.01,0.,0.1)
        d=r.decide(.2)
        self.assertFalse(d.ready)
        self.assertEqual(d.reason,'reverse_motion_unmonitored')
        self.assertEqual((d.linear,d.angular),(0.,0.))

    def test_forward_turn_and_stop_valid(self):
        self.assertEqual(planar_request_components(twist()),(.1,0.))
        self.assertEqual(planar_request_components(twist(0,.5)),(0.,.5))
        self.assertEqual(planar_request_components(twist(0,0)),(0.,0.))

    def test_nonplanar_and_invalid_twists_rejected(self):
        for kw in ('linear_y','linear_z','angular_x','angular_y'):
            with self.subTest(axis=kw),self.assertRaises(ValueError):
                planar_request_components(twist(**{kw:.3}))
        for v in (float('nan'),float('inf'),True):
            with self.subTest(v=v),self.assertRaises(ValueError):
                planar_request_components(twist(v=v))

    def test_expected_graph(self):
        valid=graph('rescuemind_velocity_guard')
        self.assertEqual(publisher_names(valid),['rescuemind_velocity_guard'])
        assert_guard_topology(valid,valid)

    def test_rogue_and_missing_graph_rejected(self):
        valid=graph('rescuemind_velocity_guard')
        for invalid in (graph('rogue'),graph('rescuemind_velocity_guard','rogue'),graph(),
                        'Publisher count: 1\nNode name: rescuemind_velocity_guard'):
            with self.subTest(invalid=invalid),self.assertRaises((RuntimeError,ValueError)):
                assert_guard_topology(invalid,valid)

    def test_graph_rejects_subscriber_as_publisher(self):
        bad=graph('rescuemind_velocity_guard').replace('Endpoint type: PUBLISHER','Endpoint type: SUBSCRIPTION')
        with self.assertRaises(ValueError):publisher_names(bad)

if __name__=='__main__': unittest.main()
