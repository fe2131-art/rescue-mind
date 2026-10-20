"""Study GC readout (post hoc): scores per run from mission.json, the threshold-decided flag and the fire-free margin (synthetic runs, no Gazebo, no model)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import gc_readout as gcr  # noqa: E402


def call(p, th):
    return {'first': {'scores': {'hazard_prob': p, 'hazard_threshold': th}}}


def mission(front, peeks=(), th=0.01):
    return {'checkpoint': {'model_calls': call(front, th)}, 'look_around': {'peeks': [{'side': s, 'model_calls': call(p, th)} for s, p in peeks]}}


class Readout(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        runs = {'r1': mission(0.02), 'r2': mission(0.2), 'r3': mission(0.004, [('left', 0.006)]), 'r4': mission(0.003)}
        for k, m in runs.items():
            (self.tmp / k).mkdir()
            (self.tmp / k / 'mission.json').write_text(json.dumps(m))
        self.ledger = self.tmp / 'l.jsonl'
        rows = [{'trial_id': 'T1', 'run_id': 'r1', 'observed_action': 'DENY_HAZARD', 'final': True},
                {'trial_id': 'T2', 'run_id': 'r2', 'observed_action': 'DENY_HAZARD', 'final': True},
                {'trial_id': 'T3', 'run_id': 'r3', 'observed_action': 'ALLOW', 'final': True},
                {'trial_id': 'T4', 'run_id': 'r4', 'observed_action': 'ALLOW', 'final': True}]
        self.ledger.write_text('\n'.join(json.dumps(r) for r in rows))
        t = lambda i, arm, fire, **k: {'trial_id': i, 'world': 'W' + i, 'arm': arm, 'fire': fire, 'stratum': 'side_only' if fire else None, **k}
        self.summary = {'trials': [t('T1', 'cal', True, hazard_refused=True, delivery_into_fire=False), t('T2', 'v36', True, hazard_refused=True, delivery_into_fire=False),
                                   t('T3', 'cal', False, hazard_refused=False, false_hazard_stop=False), t('T4', 'cal', True, hazard_refused=False, delivery_into_fire=True)]}

    def test_scores_flags_and_digest(self):
        rows = gcr.readout(self.ledger, self.tmp, self.summary, [])
        by = {r['trial_id']: r for r in rows}
        self.assertTrue(by['T1']['threshold_decided'])            # cal refused with every score below 0.05
        self.assertFalse(by['T2']['threshold_decided'])           # v36 arm: never threshold-decided
        self.assertEqual(by['T3']['check']['max_p'], 0.006)       # the largest of front and views
        d = gcr.digest(rows)
        self.assertEqual(d['fire_free_cal_max_score'], 0.006)
        self.assertEqual(d['cal_refusals_decided_by_the_threshold'], ['WT1'])
        self.assertEqual([u['trial_id'] for u in d['unsafe_deliveries']], ['T4'])

    def test_failed_and_non_final_rows_are_skipped(self):
        self.summary['trials'][0]['failed'] = True
        rows = gcr.readout(self.ledger, self.tmp, self.summary, [])
        self.assertNotIn('T1', {r['trial_id'] for r in rows})


if __name__ == '__main__':
    unittest.main()
