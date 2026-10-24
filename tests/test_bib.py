"""I-139: references.bib has no duplicate paper and every cited key is defined; the checker catches a duplicate arXiv id under a new key."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_bib  # noqa: E402


class Bib(unittest.TestCase):
    def test_repository_bib_is_clean(self):
        self.assertEqual(check_bib.problems(), [])

    def test_duplicate_under_new_key_is_caught(self):
        t = ('@misc{a2025x,\n  title = {Some Paper},\n  eprint = {2512.11215}\n}\n'
             '@misc{b2026y,\n  title = {Some paper.},\n  eprint = {2512.11215}\n}\n')
        self.assertEqual(check_bib.duplicates(t), {'b2026y': 'a2025x'})


if __name__ == '__main__':
    unittest.main()
