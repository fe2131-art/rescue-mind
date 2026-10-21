"""Stop hook that refuses to end the turn while the GPU is idle (pure decision function; no process is started)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import stop_hook_gpu_idle as h  # noqa: E402


class Decide(unittest.TestCase):
    def test_busy_allows_and_resets(self):
        self.assertEqual(h.decide(False, {'blocks': 4}), (None, {'blocks': 0}))

    def test_idle_blocks_and_counts(self):
        out, st = h.decide(True, {})
        self.assertEqual(out['decision'], 'block')
        self.assertIn('GPU_QUEUE', out['reason'])
        self.assertEqual(st, {'blocks': 1})

    def test_loop_guard_allows_after_max(self):
        out, st = h.decide(True, {'blocks': h.MAX_BLOCKS})
        self.assertIsNone(out)
        self.assertEqual(st, {'blocks': h.MAX_BLOCKS})


if __name__ == '__main__':
    unittest.main()
