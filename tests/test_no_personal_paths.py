"""Publication guard: no tracked text file may contain a real home directory or scratch path."""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAD = re.compile(r'/home/(?!<user>)[A-Za-z0-9_.-]+|/tmp/claude-\d+')
SKIP = ('.png', '.jpg', '.jpeg', '.pdf', '.mp4', '.wav', '.mcap', '.db3')


class NoPersonalPaths(unittest.TestCase):
    def test_tracked_text_files(self):
        files = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout.split(b'\0')
        hits = []
        for raw in files:
            if not raw:
                continue
            name = raw.decode()
            if name.endswith(SKIP) or name == 'tests/test_no_personal_paths.py':
                continue
            try:
                text = (ROOT / name).read_text(encoding='utf8')
            except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
                continue
            m = BAD.search(text)
            if m:
                hits.append(f'{name}: {m.group(0)}')
        self.assertEqual(hits, [])


if __name__ == '__main__':
    unittest.main()
