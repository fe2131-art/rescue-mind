"""I-77 (Jev): the judge in the VLM server may only veto: on the gate's own scale the effective hazard score is max(p_qwen, p_judge * tau_h / tau_judge) (no GPU: stubs)."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import local_vlm_server as srv  # noqa: E402


class Pic:
    size = (640, 480)

    def crop(self, box):
        return self

    def resize(self, size):
        return self


def worker(p_qwen, p_judge, judge=True, tau_h=0.05, tau_j=0.2):
    w = srv.ModelWorker.__new__(srv.ModelWorker)
    w.hazard_views, w.hazard_prompt, w.prompt_set, w.hazard_threshold = 'full', 'h36', 'v35', tau_h
    w._answer_probs = lambda pic, q, labels: {'Yes': p_qwen, 'No': 1 - p_qwen}
    if judge:
        w.judge = SimpleNamespace(hazard=lambda pic: {'max': p_judge})
        w.judge_name, w.judge_threshold = 'smolvlm2', tau_j
    return w


class Veto(unittest.TestCase):
    def haz(self, *a, **k):
        return worker(*a, **k)._hazard(Pic(), 'digest', '')[0]

    def test_judge_flag_alone_raises_the_score_to_the_gate_threshold(self):
        p = self.haz(0.001, 0.3)                    # judge 0.3 >= 0.2 -> scaled 0.3 * 0.05 / 0.2 = 0.075 >= tau_h
        self.assertAlmostEqual(p, 0.075)
        self.assertGreaterEqual(p, 0.05)

    def test_judge_below_its_threshold_does_not_flag(self):
        self.assertLess(self.haz(0.001, 0.1), 0.05)  # 0.1 * 0.25 = 0.025

    def test_judge_can_never_lower_the_gate(self):
        self.assertEqual(self.haz(0.4, 0.0), 0.4)

    def test_without_a_judge_nothing_changes(self):
        self.assertEqual(self.haz(0.03, 0.9, judge=False), 0.03)


if __name__ == '__main__':
    unittest.main()
