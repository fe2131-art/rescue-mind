"""Every Markdown table block of README.md has the same number of cells in every row (GitHub drops extra cells silently)."""
import re
import unittest
from pathlib import Path

README = Path(__file__).resolve().parents[1] / 'README.md'


def cells(line: str) -> int:
    return len(re.sub(r'`[^`]*`', '', line).replace('\\|', '').strip().strip('|').split('|'))


class ReadmeTables(unittest.TestCase):
    def test_constant_cell_count_per_table(self):
        blocks, cur = [], []
        for n, line in enumerate(README.read_text(encoding='utf8').splitlines(), 1):
            if line.startswith('|'):
                cur.append((n, cells(line)))
            elif cur:
                blocks.append(cur)
                cur = []
        if cur:
            blocks.append(cur)
        self.assertGreater(len(blocks), 5)
        for b in blocks:
            self.assertEqual({c for _, c in b}, {b[0][1]}, f'irregular table at README.md line {b[0][0]}')


if __name__ == '__main__':
    unittest.main()
