"""Study IJ: the text set (families, splits, no overlap with earlier sets), the analysis on synthetic features (a planted signal is found, claims are computed), and the run script's guards."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import ij_analysis as ija  # noqa: E402
import make_intent_ij_set as mk  # noqa: E402


class Set(unittest.TestCase):
    def test_families_splits_and_labels(self):
        rows = mk.rows()
        self.assertEqual(len(rows), len({r['text'] for r in rows}))
        fam = {(r['family'], r['split']) for r in rows if r['label'] == 'unknown'}
        self.assertEqual(len({f for f, s in fam if s == 'dev'}), 5)
        self.assertEqual(len({f for f, s in fam if s == 'test'}), 5)
        self.assertEqual(len({f for f, s in fam if s == 'dev'} & {f for f, s in fam if s == 'test'}), 0)           # whole families are held out
        self.assertTrue(all(r['split'] in ('dev', 'test') for r in rows))
        self.assertEqual({r['label'] for r in rows}, {'unknown', 'known', 'none'})

    def test_committed_file_matches_generator(self):
        got = [json.loads(l) for l in (ROOT / 'experiments/intent_eval/ij_v1.jsonl').read_text(encoding='utf8').splitlines() if l.strip()]
        self.assertEqual(got, mk.rows())

    def test_known_names_do_not_trigger_the_list_rule(self):
        from rescuemind.intent_llm import names_other_destination
        self.assertTrue(all(not names_other_destination(r['text']) for r in mk.rows() if r['label'] in ('known', 'none')))


class Analysis(unittest.TestCase):
    def test_auroc(self):
        self.assertAlmostEqual(ija.auroc(np.array([3., 4.]), np.array([1., 2.])), 1.0)
        self.assertAlmostEqual(ija.auroc(np.array([1., 2.]), np.array([3., 4.])), 0.0)
        self.assertAlmostEqual(ija.auroc(np.array([1., 1.]), np.array([1., 1.])), 0.5)

    def test_planted_signal_is_found_and_claims_are_computed(self):
        rows = mk.rows()
        rng = np.random.default_rng(0)
        y = np.array([1 if r['label'] == 'unknown' else 0 for r in rows])
        d = 16
        H = rng.normal(size=(len(rows), 3, d)).astype(np.float16)
        H[:, 1, 0] += (y * 4.0).astype(np.float16)                      # layer index 1 carries the label
        with tempfile.TemporaryDirectory() as t:
            res = Path(t)
            np.savez_compressed(res / 'ij_features.npz', H=H, layers=np.array([8, 16, 24]), yes_prob=rng.uniform(size=len(rows)), texts=np.array([r['text'] for r in rows]))
            (res / 'ij_closed_set.jsonl').write_text(''.join(json.dumps({'text': r['text'], 'p_other': float(rng.uniform())}) + '\n' for r in rows), encoding='utf8')
            old = ija.RES
            ija.RES = res
            try:
                ija.analyse()
                out = json.loads((res / 'ij_summary.json').read_text())
            finally:
                ija.RES = old
        self.assertEqual(out['chosen']['layer'], 16)
        self.assertGreater(out['scorers']['probe']['auroc'], 0.95)
        self.assertLess(out['scorers']['zero_shot_yes']['auroc'], 0.7)
        self.assertTrue(out['criteria']['IJ1_probe_auroc_beats_best_baseline_by_0.05'])
        self.assertTrue(out['criteria']['IJ2_probe_pass_through_at_most_15pct'])
        self.assertEqual((set(out['test_groups']) & set(out['dev_groups'])) - {'B', 'none'}, set())          # unknown families are disjoint; B and none are split by spelling variant and phrasing


class Guards(unittest.TestCase):
    def test_run_script(self):
        s = (ROOT / 'scripts/ij_run.sh').read_text()
        self.assertIn('flock 9', s)
        for f in ('PREREGISTRATION_IJ.md', 'ij_v1.jsonl', 'ij_extract.py', 'ij_analysis.py', 'intent_llm.py'):
            self.assertIn(f, s)


if __name__ == '__main__':
    unittest.main()
