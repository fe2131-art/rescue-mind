"""v3.3: real child processes — teardown must escalate and leave no process-group stragglers."""
import os
import signal
import sys
import tempfile
import time
import unittest
from pathlib import Path
from rescuemind.stack_supervisor import ManagedCommand, Supervisor

STUBBORN = ("import signal,time,subprocess,sys\n"
            "signal.signal(signal.SIGINT, signal.SIG_IGN); signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "child=subprocess.Popen([sys.executable,'-c','import signal,time;signal.signal(signal.SIGINT,signal.SIG_IGN);time.sleep(60)'])\n"
            "print(child.pid, flush=True); time.sleep(60)\n")
POLITE = "import time\ntry:\n    time.sleep(60)\nexcept KeyboardInterrupt:\n    pass\n"


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:  # zombies count as dead
        with open(f'/proc/{pid}/stat') as f:
            return f.read().split()[2] != 'Z'
    except OSError:
        return False


class TestEscalation(unittest.TestCase):
    def test_sigint_first_then_kill_whole_group(self):
        with tempfile.TemporaryDirectory() as d:
            sup = Supervisor(Path(d))
            polite = sup.start_service(ManagedCommand('polite', (sys.executable, '-c', POLITE)))
            stubborn = sup.start_service(ManagedCommand('stubborn', (sys.executable, '-c', STUBBORN)))
            time.sleep(1.0)
            grandchild = int((Path(d) / 'stubborn.log').read_text().split()[0])
            t0 = time.monotonic()
            sup.shutdown()
            self.assertLess(time.monotonic() - t0, 20)
            self.assertIsNotNone(polite.poll())
            self.assertIsNotNone(stubborn.poll())
            time.sleep(0.5)
            self.assertFalse(alive(grandchild), 'process-group straggler survived teardown')
            self.assertEqual(polite.returncode, 0)  # exited cleanly on SIGINT


if __name__ == '__main__':
    unittest.main()
