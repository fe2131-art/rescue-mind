"""Study JC: the cascade policy and its registered claims on synthetic scores."""
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import ji_cascade as jc  # noqa: E402

THR = {'tau': {'v36_FLR': {'qwen35': 0.088}, 'all_six': {'qwen35': 0.088}}}
CTHR = {'primary_alpha': 0.2, 'gate_own_trigger': 0.01, 'sentinel_alpha': {j: {'0.2': 0.05} for j in jc.SENTINELS}}


def scores():
    random.seed(0)
    sc = {s: {} for s in ('qwen35',) + jc.SENTINELS}
    kind = {}
    for i in range(20):
        for tag, k in ((f'f{i}', 'fire'), (f'c{i}', 'clean')):
            kind[tag] = k
            for v in jc.STD + jc.EXTRA:
                for s in sc:
                    sc[s][(tag, v)] = 0.001
    for i in range(2, 20):
        sc['qwen35'][(f'f{i}', 'F')] = 0.5            # plainly visible fires
    # fire f0: only an extra view shows it to the gate; the sentinel sees something on the standard views -> the cascade catches it, always3 does not
    sc['qwen35'][('f0', 'L2')] = 0.5
    sc['smolvlm2'][('f0', 'F')] = 0.2
    # fire f1: the sentinel is blind -> the cascade misses it as always3 does
    sc['qwen35'][('f1', 'R2')] = 0.5
    # clean c0: the sentinel false-alarms; the gate stays quiet -> extra views spent, no false stop
    sc['smolvlm2'][('c0', 'L')] = 0.3
    return sc, kind


class Cascade(unittest.TestCase):
    def test_policies_and_claims(self):
        sc, kind = scores()
        out = jc.analyse(sc, kind, THR, CTHR, {'internvl3': 6.0, 'idefics3': 7.0, 'smolvlm2': 1.0}, 2.0)
        P = out['policies']
        self.assertEqual((P['always3']['miss'], P['always6']['miss']), (2, 0))
        self.assertEqual(out['primary_sentinel'], 'smolvlm2')
        s = P['sentinel_smolvlm2']
        self.assertEqual((s['miss'], s['false_stops']), (1, 0))                    # f0 caught, f1 missed, c0 not stopped
        self.assertEqual(s['mean_views_clean'], 3 + 3 / 20)                       # only c0 triggers the extra views
        self.assertTrue(out['claims']['JC1_primary_sentinel_misses_within_3_of_always_six'])
        self.assertTrue(out['claims']['P1_primary_sentinel_fewer_misses_than_always_three'])
        self.assertTrue(out['claims']['P2_primary_sentinel_faster_than_always_six_estimate'])

    def test_sentinel_never_decides_alone(self):
        sc, kind = scores()
        sc['smolvlm2'][('c1', 'F')] = 0.99          # a screaming sentinel on a clean world: more views, never a refusal
        out = jc.analyse(sc, kind, THR, CTHR, {'internvl3': 6.0, 'idefics3': 7.0, 'smolvlm2': 1.0}, 2.0)
        self.assertEqual(out['policies']['sentinel_smolvlm2']['false_stops'], 0)


if __name__ == '__main__':
    unittest.main()
