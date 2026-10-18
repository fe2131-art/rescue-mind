"""scripts/make_registrations.py: the registration ledger is generated from git (docs/REGISTRATIONS.md)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import make_registrations as mr  # noqa: E402


class TestRegistrations(unittest.TestCase):
    def test_text_later_than_commit(self):
        self.assertTrue(mr.text_later('2026-10-18', '10:30', '2026-10-18T10:09:17+09:00'))
        self.assertFalse(mr.text_later('2026-10-18', '10:00', '2026-10-18T10:09:17+09:00'))
        self.assertTrue(mr.text_later('2026-10-17', None, '2026-10-16T19:59:19+09:00'))     # date only, one day later
        self.assertFalse(mr.text_later('2026-10-18', None, '2026-10-18T01:38:00+09:00'))    # same day, no time written
        self.assertIsNone(mr.text_later(None, None, '2026-10-18T01:38:00+09:00'))

    def test_amendment_headings(self):
        txt = ('## Amendment 1 (2026-10-18 10:30, after the pilot)\n\ntext\n## Amendment 2 (2026-10-18 10:55, x)\n'
               '**Amendment 3 (2026-10-17, y).**\nsee Amendment 2 of W\n## Erratum (times)\n')
        self.assertEqual(mr.amendments(txt), [('1', '2026-10-18', '10:30'), ('2', '2026-10-18', '10:55'), ('3', '2026-10-17', None)])

    def test_every_registration_file_is_listed(self):
        keys = {f'PREREGISTRATION_{k}.md' for _, k, _ in mr.STUDIES}
        self.assertEqual({p.name for p in (ROOT / 'experiments').glob('PREREGISTRATION_*.md')}, keys)

    def test_erratum_is_not_an_amendment(self):
        self.assertEqual(mr.amendments('## Erratum (times)\nAmendment 1 (2026-10-18 10:30) was an estimate\n'), [])


if __name__ == '__main__':
    unittest.main()
