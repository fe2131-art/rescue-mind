"""Studies IJ and JM: the result hooks (failed claims, paper macros, README row, YouTube line, multiplicity family) on synthetic summaries, before any real result exists (I-122)."""
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import advice_numbers as an  # noqa: E402
import make_youtube_description as yd  # noqa: E402
import multiplicity as mu  # noqa: E402
import paper_numbers as pn  # noqa: E402
import update_readme_results as ur  # noqa: E402


def cell(k, n):
    return {'k': k, 'n': n, 'rate': k / n, 'upper95_exact': 0.1, 'worlds_unsafe': [], 'median_time_s': 100.0}


def pair(a, b, p):
    return {'n_pairs': 60, 'first_only_unsafe': a, 'second_only_unsafe': b, 'mcnemar_one_sided_p_first_worse': p}


def jm_summary(jm3=False):
    return {'n_failed': 0, 'audit_failures': 0, 'n_fire_worlds': 60,
            'arms': {'v36': {'smoke': cell(8, 60), 'no_smoke': cell(2, 60)}, 'adapt': {'smoke': cell(2, 60), 'no_smoke': cell(0, 60)}},
            'smoke_effect_v36': pair(7, 1, 0.035), 'smoke_effect_adapt': pair(2, 0, 0.25), 'adapt_vs_v36_smoke': pair(6, 0, 0.0156), 'adapt_vs_v36_no_smoke': pair(2, 0, 0.25),
            'extras': {'smoke': {'reached': 60, 'triggered': 30, 'share': 0.5}, 'no_smoke': {'reached': 60, 'triggered': 20, 'share': 0.333}},
            'criteria': {'JM1_smoke_increases_v36_misses': True, 'JM1_p': 0.035, 'JM2_extra_views_reduce_misses_in_smoke': True, 'JM2_p': 0.0156, 'JM3_adapt_smoke_at_most_4_of_60': jm3,
                         'JM3_k': 2, 'JM3_n': 60, 'JM3_upper95_exact': 0.1, 'P1_adapt_no_smoke_at_most_1': True, 'P2_trigger_share_higher_with_smoke': True,
                         'P3_time_cost_at_most_30s': True, 'time_cost_s': 12.3}}


def scorer(a, p, f):
    return {'auroc': a, 'unknown_pass_through': p, 'false_refusal': f, 'threshold': 0.5, 'by_family_pass_through': {}, 'auroc_ci95': [a - 0.05, a + 0.03]}


def ij_summary(ij2=False):
    return {'n_dev': 400, 'n_test': 384, 'chosen': {'layer': 20, 'C': 1.0},
            'scorers': {'probe': scorer(0.91, 0.12, 0.05), 'zero_shot_yes': scorer(0.7, 0.5, 0.02), 'closed_set_p_other': scorer(0.75, 0.4, 0.03),
                        'diff_in_means': scorer(0.85, 0.2, 0.04), 'list_rule': scorer(0.6, 0.7, 0.0)},
            'criteria': {'IJ1_probe_auroc_beats_best_baseline_by_0.05': True, 'IJ2_probe_pass_through_at_most_15pct': ij2, 'IJ3_probe_false_refusal_at_most_8pct': True,
                         'P1_probe_passes_fewer_than_list_rule': True, 'P2_at_least_4_of_5_test_families_pass_through_at_most_25pct': False}}


class Hooks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.res = Path(self.tmp.name)
        (self.res / 'jm_summary.json').write_text(json.dumps(jm_summary()))
        (self.res / 'ij_summary.json').write_text(json.dumps(ij_summary()))

    def tearDown(self):
        self.tmp.cleanup()

    def block(self, path, start, end):
        src = (ROOT / path).read_text()
        return textwrap.dedent(src[src.index(start):src.index(end)])

    def test_failed_claims_lists_only_the_failed_ones(self):
        old = an.RES
        an.RES = self.res
        try:
            keys = [x['key'] for x in an.failed_claims() if x['key'][:2] in ('IJ', 'JM')]
        finally:
            an.RES = old
        self.assertEqual(sorted(keys), ['IJ2', 'JM3'])

    def test_paper_macros_are_letters_only(self):
        m = {}
        exec(self.block('scripts/paper_numbers.py', '    # ---- study JM', '    # ---- study JK'), {'RES': self.res, 'json': json, 'pct': pn.pct, 'm': m})
        self.assertTrue(all(k.isalpha() for k in m), [k for k in m if not k.isalpha()])
        self.assertEqual((m['JMVSmoke'], m['JMArmSmokeP'], m['IJThreeHolds'], m['JMThreeHolds']), ('8/60', '0.0156', 'holds', 'fails'))
        for tex in ('ij_section.draft.tex', 'jm_section.draft.tex'):
            import re
            used = set(re.findall(r'\\((?:IJ|JM)[A-Za-z]+)', (ROOT / 'docs/paper' / tex).read_text()))
            self.assertFalse(used - set(m), (tex, used - set(m)))

    def test_readme_rows_name_the_failed_claim(self):
        rows = []
        exec(self.block('scripts/update_readme_results.py', "    jm_ = jl('jm_summary.json')", "    ih_ = jl('ih_summary.json')"),
             {'jl': lambda n: json.loads((self.res / n).read_text()), 'pct': ur.pct, 'rows': rows})
        self.assertEqual(len(rows), 2)
        self.assertIn('（JM3）', rows[0])
        self.assertIn('（IJ2）', rows[1])

    def test_youtube_lines(self):
        txt = yd.line_views(str(self.res))
        self.assertIn('評価JM', txt)
        self.assertIn('評価IJ', txt)

    def test_multiplicity_family_has_jm1(self):
        self.assertIn(('JM', 'jm_summary.json', ('smoke_effect_v36', 'mcnemar_one_sided_p_first_worse')), [s[:3] for s in mu.SPECS])


if __name__ == '__main__':
    unittest.main()
