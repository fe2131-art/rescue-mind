"""Study V wording (scripts/advice_numbers.py): a failed registered claim is stated as failed, with its reasons, in every language."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import advice_numbers as an  # noqa: E402

FACTS = {'diff': 14.94, 'pred_lo': 11.3, 'pred_hi': 20.08, 'unsafe': {'M0': 0, 'M1': 20, 'M2': 1}, 'n_per_arm': 50,
         'model_claim': True, 'memory_claim': False, 'v1': True, 'v2': True, 'v3': True, 'v3_p': 0.00586, 'v4': False,
         'margin_ok': True, 'm2_minus_m0': 1, 'margin': 3, 'strict_ok': False, 'seq_n': 10, 'seq_unsafe': {'M0': 0, 'M1': 6, 'M2': 1},
         'disc': [5, 0], 'mcnemar_p': 0.0625}


class StudyVText(unittest.TestCase):
    def test_failed_memory_claim_is_stated_with_reasons(self):
        ja, en = an.v_claims_ja(FACTS), an.v_claims_en(FACTS)
        self.assertIn('記憶はランダムな変化でも安全：不成立', ja)
        self.assertIn('p=0.0625', ja)
        self.assertIn('V156', ja)
        self.assertIn('not supported', en)
        self.assertIn('p=0.0625', en)
        self.assertIn('check error', en)

    def test_supported_memory_claim_has_no_failure_text(self):
        f = dict(FACTS, memory_claim=True)
        self.assertNotIn('V156', an.v_claims_ja(f))
        self.assertNotIn('failure is kept', an.v_claims_en(f))

    def test_markdown_bold_has_no_html(self):
        self.assertNotIn('<b>', an.v_claims_ja(FACTS, bold='md'))
        self.assertIn('<b>', an.v_claims_ja(FACTS))

    def test_missing_summary_gives_none(self):
        self.assertIsNone(an.v_claims_ja(None) if an.v_facts() is None else None)


if __name__ == '__main__':
    unittest.main()
