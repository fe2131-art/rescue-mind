"""Development readout of the hazard-question variants: thresholds, detection and false stops on synthetic rows."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import gv_dev_analysis as da  # noqa: E402


def r(study, tid, view, item, fire, a, b):
    return {'study': study, 'trial_id': tid, 'view': view, 'item': item, 'fire': fire, 'arm': 'cal', 'world': tid, 'scores': {'h36': {'max': a}, 'h37a': {'max': b}, 'h37b': {'max': b}}}


class Analyse(unittest.TestCase):
    def test_threshold_detection_and_false_stops(self):
        rows = [r('GDK', f'K{i}', 'F', 'medicine', False, 0.01 * (i + 1) / 10, 0.005) for i in range(10)]       # clean 0.001 .. 0.01
        rows += [r('GD', 'A', 'F', 'medicine', True, 0.5, 0.5), r('GD', 'A', 'R', 'medicine', True, 0.02, 0.02),   # a fire run, largest view counts
                 r('GD', 'B', 'F', 'medicine', True, 0.002, 0.002),                                              # a missed fire
                 r('GD', 'C', 'F', 'water', False, 0.004, 0.004)]
        out = da.analyse(rows, {'B'}, prompts=('h36',))['h36']
        self.assertEqual(out['clean_0.4m']['m'], 10)
        self.assertIsNone(out['clean_0.4m']['tau_alpha2'])           # m = 10: the rank does not exist at alpha = 2%
        out2 = da.analyse(rows + [r('GDK', 'K11', 'F', 'water', False, 0.0005, 0.0005)] * 0, {'B'}, prompts=('h36',))['h36']
        self.assertEqual(out2['fire_runs_0.4m']['n'], 2)

    def test_rank_rule(self):
        self.assertEqual(da.rank_tau([i / 100 for i in range(1, 101)]), 0.99)


if __name__ == '__main__':
    unittest.main()
