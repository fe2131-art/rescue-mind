"""I-136: every registered study appears in every audit artifact, and the checker would have caught the incident (Table S9 stopping at study Y)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_study_coverage as cov  # noqa: E402


class Coverage(unittest.TestCase):
    def test_repository_is_complete(self):
        self.assertEqual(cov.problems(), [])

    def test_a_table_that_stops_early_is_caught(self):
        rows = cov.row_labels(ROOT / 'docs/paper/tab_prereg.tex')
        cut = [r for r in rows][:26]                      # the incident: the table ended at study Y
        with tempfile.TemporaryDirectory() as d:
            t = Path(d) / 'tab_prereg.tex'
            t.write_text('\n'.join(f'{r} & a & b & 0 & ok \\\\' for r in cut))
            labels = [s for s, _ in cov.studies()]
            self.assertTrue([s for s in labels if s not in cov.row_labels(t)])

    def test_hand_list_detector(self):
        keys = {'A', 'B', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'P', 'R', 'S', 'V', 'W', 'X', 'Y', 'Z'}
        with tempfile.TemporaryDirectory() as d:
            q = "', '".join(sorted(keys))
            (Path(d) / 'x.py').write_text(f"L = ['{q}']\n")
            old = cov.ROOT
            try:
                cov.ROOT = Path(d)
                (Path(d) / 'scripts').mkdir()
                (Path(d) / 'scripts' / 'x.py').write_text(f"L = ['{q}']\n")
                self.assertEqual(len(cov.hand_lists(keys)), 1)
                (Path(d) / 'scripts' / 'x.py').write_text(f"L = ['{q}']  # study-subset\n")
                self.assertEqual(cov.hand_lists(keys), [])
            finally:
                cov.ROOT = old


if __name__ == '__main__':
    unittest.main()
