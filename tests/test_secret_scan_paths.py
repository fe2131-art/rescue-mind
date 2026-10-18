"""secret_scan.py flags home-directory and scratch paths in tracked text files (EVAL 10 #1), and only those."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import secret_scan  # noqa: E402

HOME = '/ho' + 'me/'          # pieces: this file must not contain a real-looking path itself
SCRATCH = '/tm' + 'p/claude-'


class PathScan(unittest.TestCase):
    def kinds(self, text):
        return [k for k, _, _ in secret_scan.scan_text('x.txt', text)]

    def test_home_path_flagged(self):
        self.assertIn('PERSONAL:home-or-scratch-path', self.kinds(f'run at {HOME}alice/work/rescue-mind/a.png'))
        self.assertIn('PERSONAL:home-or-scratch-path', self.kinds(f'"path": "{HOME}bob.smith/x"'))

    def test_scratch_path_flagged(self):
        self.assertIn('PERSONAL:home-or-scratch-path', self.kinds(f'{SCRATCH}1008/-x/scratchpad/out.json'))

    def test_placeholder_and_relative_paths_allowed(self):
        self.assertEqual(self.kinds(f'{HOME}<user>/work'), [])
        self.assertEqual(self.kinds('experiments/results/a_checklist.json and ~/rescue-mind-trash/'), [])
        self.assertEqual(self.kinds('the home directory /home alone, /tmp/x, /tmp/claude'), [])

    def test_line_number_is_reported(self):
        hits = secret_scan.scan_text('f.json', f'ok\nok\n{HOME}carol/x\n')
        self.assertEqual(hits, [('PERSONAL:home-or-scratch-path', 'f.json', 3)])

    def test_scan_tracked_finds_it_in_a_git_repo_and_the_cli_fails(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            subprocess.run(['git', 'init', '-q'], cwd=d, check=True)
            (d / 'r.json').write_text(f'{{"p": "{HOME}dave/work/x.png"}}\n', encoding='utf8')
            (d / 'ok.json').write_text('{"p": "experiments/x.png"}\n', encoding='utf8')
            subprocess.run(['git', 'add', '.'], cwd=d, check=True)
            _, findings, _ = secret_scan.scan_tracked(d)
            self.assertEqual([(k, f) for k, f, _ in findings], [('PERSONAL:home-or-scratch-path', 'r.json')])

    def test_the_repository_itself_is_clean(self):
        _, findings, _ = secret_scan.scan_tracked(ROOT)
        self.assertEqual([f for f in findings if f[0].startswith('PERSONAL')], [])

    def test_findings_never_print_the_path(self):
        out = subprocess.run([sys.executable, str(ROOT / 'scripts/secret_scan.py')], capture_output=True, text=True, cwd=ROOT).stdout
        self.assertNotIn(HOME, out)


if __name__ == '__main__':
    unittest.main()
