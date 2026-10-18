"""Study XD-R: manifest validation, the seeded draw and the false-alarm analysis on synthetic scores (no images, no model)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import xd_realphoto as xr  # noqa: E402


def row(name, **kw):
    return {'file': name, 'source_url': 'https://example.org/' + name, 'licence': 'CC0', 'fire_free_checked': True, 'kind': 'warehouse', **kw}


class Manifest(unittest.TestCase):
    def test_validation(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            for n in ('a.jpg', 'b.png', 'c.jpg', 'd.jpg', 'e.jpg', 'f.txt'):
                (d / n).write_bytes(b'x')
            rows = [row('a.jpg'), row('b.png', licence='All rights reserved'), row('a.jpg'), row('c.jpg', fire_free_checked=False),
                    row('d.jpg', kind='kitchen'), row('missing.jpg'), row('f.txt'), row('e.jpg', source_url='')]
            bad = ' | '.join(xr.validate(rows, d))
            for needle in ('b.png: licence', 'a.jpg: duplicate', 'c.jpg: fire_free_checked', 'd.jpg: kind', 'missing.jpg: file missing',
                           'f.txt: not an image', 'e.jpg: no source_url'):
                self.assertIn(needle, bad)
            self.assertEqual(xr.validate([row('a.jpg'), row('b.png', licence='cc-by-4.0')], d), [])

    def test_draw_is_reproducible_and_order_independent(self):
        rows = [row(f'{i:03d}.jpg') for i in range(300)]
        a = xr.draw(rows)
        self.assertEqual(len(a), 200)
        self.assertEqual([r['file'] for r in a], [r['file'] for r in xr.draw(list(reversed(rows)))])
        self.assertNotEqual([r['file'] for r in a], [r['file'] for r in xr.draw(rows, seed='other')])
        with self.assertRaises(SystemExit):
            xr.draw(rows[:150])


class Analysis(unittest.TestCase):
    def recs(self, probs, kinds=None):
        return [{'file': f'{i}.jpg', 'hazard_prob': p, 'kind': (kinds or ['warehouse'] * len(probs))[i]} for i, p in enumerate(probs)]

    def test_false_alarms_per_threshold(self):
        probs = [0.0] * 120 + [0.1] * 40 + [0.4] * 30 + [None] * 10
        out = xr.analyse_scores(self.recs(probs), {'frozen': 0.05, 'p2_h36': 0.35, 'xd_depot': 0.15})
        fa = out['false_alarm']
        self.assertEqual((fa['frozen']['k'], fa['frozen']['n']), (80, 200))               # a missing score counts as an alarm
        self.assertEqual(fa['p2_h36']['k'], 40)
        self.assertEqual(fa['xd_depot']['k'], 40)
        self.assertEqual(fa['p2_h36']['rate'], 0.2)
        self.assertTrue(out['claim_false_alarm_at_depot_tau_at_most_0.20'])                # 0.20 is allowed (<=)
        out = xr.analyse_scores(self.recs(probs + [0.5]), {'frozen': 0.05, 'xd_depot': 0.15})
        self.assertFalse(out['claim_false_alarm_at_depot_tau_at_most_0.20'])

    def test_no_depot_threshold_means_no_claim(self):
        out = xr.analyse_scores(self.recs([0.0] * 10), {'frozen': 0.05})
        self.assertFalse(out['claim_false_alarm_at_depot_tau_at_most_0.20'])

    def test_by_kind(self):
        out = xr.analyse_scores(self.recs([0.9, 0.0, 0.9], ['warehouse', 'storeroom', 'storeroom']), {'frozen': 0.05})
        self.assertEqual(out['false_alarm']['frozen']['by_kind'], {'warehouse': '1/1', 'storeroom': '1/2'})

    def test_thresholds_read_the_registered_files(self):
        t = xr.thresholds()
        self.assertEqual(t['frozen'], 0.05)
        self.assertEqual(t['p2_h36'], 0.35)                                               # experiments/results/p2_summary.json
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'xd_summary.json').write_text(json.dumps({'XD_recalibration': {'calibration': {'tau_star': 0.2}}}))
            self.assertEqual(xr.thresholds(Path(td)), {'frozen': 0.05, 'xd_depot': 0.2})


if __name__ == '__main__':
    unittest.main()
