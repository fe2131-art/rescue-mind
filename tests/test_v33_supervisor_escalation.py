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
POLITE = ("import signal,sys,time\nsignal.signal(signal.SIGINT, signal.default_int_handler)\ntry:\n    open(sys.argv[1], 'w').write('ready')\n    time.sleep(60)\nexcept KeyboardInterrupt:\n    pass\n")


def wait_for(cond, limit=60.0):
    """Readiness, not a fixed sleep: under heavy host load the children start late and SIGINT would hit them before their handlers exist."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit:
        if cond():
            return True
        time.sleep(0.1)
    return False


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
            ready = Path(d) / 'polite.ready'
            polite = sup.start_service(ManagedCommand('polite', (sys.executable, '-c', POLITE, str(ready))))
            stubborn = sup.start_service(ManagedCommand('stubborn', (sys.executable, '-c', STUBBORN)))
            log = Path(d) / 'stubborn.log'
            self.assertTrue(wait_for(lambda: ready.is_file() and log.is_file() and log.read_text().split()), 'children did not start')
            grandchild = int(log.read_text().split()[0])
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
