"""Study A figure (scripts/make_a_figure.py) and the wording about the A configuration (EVAL 10 items 4, 6, 7)."""
import copy
import re
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import advice_numbers  # noqa: E402
import make_a_figure  # noqa: E402

FACTS = advice_numbers.a_facts()


@unittest.skipIf(FACTS is None, 'no a_summary.json')
class AFigure(unittest.TestCase):
    def test_facts_carry_the_per_world_values_of_the_figure(self):
        self.assertEqual(len(FACTS['time_saved_s']), FACTS['time_n'])
        self.assertEqual(len(FACTS['extra_s']), FACTS['price']['n'])
        self.assertEqual(max(FACTS['extra_s']), FACTS['price']['max_extra'])

    def test_builds_pdf_and_png_from_facts(self):
        with tempfile.TemporaryDirectory() as d, warnings.catch_warnings():
            warnings.simplefilter('ignore')
            outs = [Path(d) / 'a.pdf', Path(d) / 'a.png']
            self.assertTrue(make_a_figure.build('en', outs))
            for o in outs:
                self.assertGreater(o.stat().st_size, 5000)
            self.assertTrue(outs[0].read_bytes().startswith(b'%PDF'))
            self.assertTrue(make_a_figure.build('ja', [Path(d) / 'ja.png']))

    def test_no_result_no_figure(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(advice_numbers, 'a_facts', return_value=None):
                self.assertFalse(make_a_figure.build('en', [Path(d) / 'x.pdf']))
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_unsafe_world_counts_are_not_invented(self):
        f = copy.deepcopy(FACTS)
        f['worlds']['naive'] = None
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(make_a_figure.build('en', [Path(d) / 'x.pdf'], f))

    def test_labels_exist_in_both_languages(self):
        self.assertEqual(set(make_a_figure.T['en']), set(make_a_figure.T['ja']))

    def test_committed_figures_exist(self):
        for f in ('docs/paper/fig_a_results.pdf', 'docs/figures/a_results_en.png', 'docs/figures/a_results_ja.png'):
            self.assertTrue((ROOT / f).is_file(), f)


@unittest.skipIf(FACTS is None, 'no a_summary.json')
class AConfigurationWording(unittest.TestCase):
    def test_i38_and_guardrail_blindness_in_every_text(self):
        for txt in (advice_numbers.a_ja(), advice_numbers.a_en()):
            self.assertIn('i38', txt)
            self.assertIn('i35', txt)
            self.assertIn('#34', txt)
            self.assertIn('#30', txt)
        self.assertIn(f"{FACTS['filter_flag_operator'][0]}/{FACTS['filter_flag_operator'][1]}", advice_numbers.a_ja())
        self.assertIn(f"{FACTS['filter_flag_file'][0]}/{FACTS['filter_flag_file'][1]}", advice_numbers.a_ja())

    def test_readme_key_row_carries_the_conditions(self):
        txt = (ROOT / 'README.md').read_text(encoding='utf8')
        row = next(l for l in txt.splitlines() if l.startswith('| 悪意のある助言でも危険にならない（評価A'))
        self.assertIn('ファイル経由の助言を見ず', row)
        self.assertIn('i38', row)
        self.assertIn('i35', row)
        self.assertIn('a_results_ja.png', txt)

    def test_paper_states_i38_and_the_guardrail_condition(self):
        main = (ROOT / 'docs/paper/main.tex').read_text(encoding='utf8')
        self.assertIn('intent prompt i38', main)
        self.assertIn('submitted default is i35', main)
        self.assertIn("read every item's text", main)           # R9: the guardrail READ the peer items and flagged none (not 'does not see the file channel')
        self.assertNotIn('does not see the file channel', main)
        self.assertIn('fig_a_results.pdf', (ROOT / 'docs/paper/supplement.tex').read_text(encoding='utf8'))

    def test_checklist_c9_line_is_plain(self):
        md = (ROOT / 'experiments/results/a_checklist.md').read_text(encoding='utf8')
        self.assertNotIn('Nfailed', md)
        self.assertRegex(md, r'C9: A adds no failed claim; the paper\'s total of failed registered claims is \d+')


class SubmissionFacts(unittest.TestCase):
    def test_report_page_counts_line_has_the_generated_form(self):
        s = (ROOT / 'docs/SUBMISSION.md').read_text(encoding='utf8')
        m = re.search(r'<!--FACT:report-->(.*?)<!--/FACT:report-->', s, re.S)
        self.assertIsNotNone(m)
        self.assertRegex(m.group(1), r'^本文\d+ページ＋付録\d+ページ（全\d+ページ。付録は\d+ページから')
        nums = [int(x) for x in re.findall(r'\d+', m.group(1))[:3]]
        self.assertEqual(nums[0] + nums[1], nums[2])


if __name__ == '__main__':
    unittest.main()
