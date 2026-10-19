"""Study X readout (I-41) and the X numbers of the documents: the readout reads the saved model outputs only; the numbers come from x_summary.json."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT))
import advice_numbers  # noqa: E402
import x_readout  # noqa: E402


def mission(front, peeks):
    call = lambda p: {'first': {'scores': {'hazard_prob': p, 'hazard_threshold': 0.05}}}
    return {'checkpoint': {'model_calls': call(front)}, 'checkpoint_station': 'M2',
            'look_around': {'peeks': [{'side': s, 'model_calls': call(p)} for s, p in peeks]}, 'memory': {'caution': {'M2': {'tau_h': 0.01}}}}


class Readout(unittest.TestCase):
    def test_scores_and_max_over_views(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / 'runs/r1').mkdir(parents=True)
            (td / 'runs/r1/mission.json').write_text(json.dumps(mission(0.009, [('L', 0.0057), ('R', 0.7187)])))
            ledger = td / 'ledger.jsonl'
            ledger.write_text(json.dumps({'trial_id': 'X058', 'condition': 'steer_fire', 'final': True, 'run_id': 'r1', 'world': 'XC15', 'observed_action': 'DENY_HAZARD'}) + '\n'
                              + json.dumps({'trial_id': 'X999', 'condition': 'persist', 'final': True, 'run_id': 'r2', 'world': 'W', 'observed_action': 'ALLOW'}) + '\n')
            real = x_readout.RES
            x_readout.RES = td
            try:
                (td / 'x_summary.json').write_text(json.dumps({'trials': [{'trial_id': 'X058', 'arm': 'monotone'}]}))
                rows = x_readout.readout(ledger, td / 'runs')
            finally:
                x_readout.RES = real
        self.assertEqual(len(rows), 1)                    # only the steering cells
        r = rows[0]
        self.assertEqual((r['arm'], r['front_hazard_prob'], r['max_view_hazard_prob'], r['tau_h_caution']), ('monotone', 0.009, 0.7187, 0.01))
        self.assertEqual([(p['side'], p['hazard_prob']) for p in r['peeks']], [('L', 0.0057), ('R', 0.7187)])

    def test_missing_record_is_listed_not_invented(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            ledger = td / 'ledger.jsonl'
            ledger.write_text(json.dumps({'trial_id': 'X001', 'condition': 'steer_clean', 'final': True, 'run_id': 'nope', 'world': 'W', 'observed_action': 'ALLOW'}) + '\n')
            real, real_main = x_readout.RES, x_readout.MAIN
            x_readout.RES, x_readout.MAIN = td, td
            try:
                (td / 'x_summary.json').write_text(json.dumps({'trials': []}))
                rows = x_readout.readout(ledger, td)
            finally:
                x_readout.RES, x_readout.MAIN = real, real_main
        self.assertFalse(rows[0]['have_record'])
        self.assertNotIn('front_hazard_prob', rows[0])


class XFacts(unittest.TestCase):
    def test_facts_follow_the_summary_and_the_texts_carry_the_caveats(self):
        f = advice_numbers.x_facts()
        if f is None:
            self.skipTest('x_summary.json absent')
        s = json.loads((ROOT / 'experiments/results/x_summary.json').read_text())
        self.assertEqual(f['n'], s['n_planned'])
        self.assertEqual(f['failed'], sum(s['n_failed_by_part'].values()))
        ja, en = advice_numbers.x_ja(), advice_numbers.x_en()
        for t in (ja, en):
            self.assertIn(f"{f['u_mono']}", t)
            self.assertIn('S4', t)
        self.assertIn('descriptive', en)
        self.assertIn(f"{f['failed']} failures kept", en)


if __name__ == '__main__':
    unittest.main()
