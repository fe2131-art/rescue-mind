import signal, tempfile, unittest
from unittest.mock import Mock,patch
from pathlib import Path
from rescuemind.stack_supervisor import Supervisor

class TestBagShutdownSignal(unittest.TestCase):
    def test_all_services_receive_sigint_first(self):
        with tempfile.TemporaryDirectory() as d:
            a=Supervisor(Path(d))
            p1=Mock(pid=123);p1.poll.return_value=0
            p2=Mock(pid=456);p2.poll.return_value=0
            f1=Mock();f2=Mock()
            a.services=[('velocity_guard',p1,f1),('rosbag_recorder',p2,f2)]
            with patch('rescuemind.stack_supervisor.os.killpg') as kill:
                a.shutdown()
            calls=[c.args for c in kill.call_args_list]
            # rosbag (last started) is stopped first; v3.3: every service gets SIGINT
            # first (graceful DDS teardown) before any escalation.
            self.assertEqual(calls[0],(456,signal.SIGINT))
            first={}
            for pid,sig in calls: first.setdefault(pid,sig)
            self.assertEqual(first,{456:signal.SIGINT,123:signal.SIGINT})
            f1.close.assert_called_once();f2.close.assert_called_once()
