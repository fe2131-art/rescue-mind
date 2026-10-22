"""Study QI: a failed registered claim must reach advice_numbers.failed_claims() (so the abstract count, the Discussion list and the README move together); a held or unscored one must not."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import advice_numbers as an  # noqa: E402


class QiClaims(unittest.TestCase):
    def keys(self, claims):
        old = an.RES
        with tempfile.TemporaryDirectory() as d:
            for f in old.glob('*_summary.json'):                       # the real summaries, so the other studies' claims stay as they are
                (Path(d) / f.name).write_text(f.read_text(encoding='utf8'), encoding='utf8')
            (Path(d) / 'qi_summary.json').write_text(json.dumps({'claims': claims}), encoding='utf8')
            an.RES = Path(d)
            try:
                return [c['key'] for c in an.failed_claims()]
            finally:
                an.RES = old

    def test_failed_claim_is_listed(self):
        ks = self.keys({'QI1_realised_miss_not_much_worse': False, 'QI2_generated_fire_miss_rate': True})
        self.assertIn('QI1', ks)
        self.assertNotIn('QI2', ks)

    def test_unscored_claims_are_not_listed(self):
        ks = self.keys({})
        self.assertFalse([k for k in ks if k.startswith('QI')])


if __name__ == '__main__':
    unittest.main()
