"""scripts/set_video_url.py (dry run by default, URL check, idempotent) and scripts/secret_scan.py (patterns, no false alarm on placeholders).
Host python3 only; the repository files are never written (a temporary copy of the two documents is used for --apply)."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import secret_scan  # noqa: E402
import set_video_url as sv  # noqa: E402

VID = 'dQw4w9WgXcQ'
URL = f'https://www.youtube.com/watch?v={VID}'


class NormalizeUrl(unittest.TestCase):
    def test_accepted_forms(self):
        for raw in (URL, f'https://youtu.be/{VID}', f'https://youtu.be/{VID}?si=abc', f'https://m.youtube.com/watch?v={VID}&t=5s',
                    f'https://youtube.com/watch?v={VID}', f'https://www.youtube.com/shorts/{VID}', f'  {URL}\n'):
            self.assertEqual(sv.normalize_url(raw), URL, raw)

    def test_rejected_forms(self):
        for raw in ('', 'https://example.com/watch?v=' + VID, 'https://www.youtube.com/watch?v=short', 'https://www.youtube.com/playlist?list=PL123',
                    'ftp://youtu.be/' + VID, 'https://youtu.be/', 'not a url'):
            with self.assertRaises(ValueError, msg=raw):
                sv.normalize_url(raw)


class Rewrite(unittest.TestCase):
    def test_marker_pair_required(self):
        with self.assertRaises(ValueError):
            sv.rewrite('no marker', 'x', 'f')
        with self.assertRaises(ValueError):
            sv.rewrite('<!--VIDEOURL-->a<!--/VIDEOURL--> <!--VIDEOURL-->b<!--/VIDEOURL-->', 'x', 'f')

    def test_idempotent_and_reversible(self):
        t = '前 <!--VIDEOURL-->' + sv.PLACEHOLDER + '<!--/VIDEOURL--> 後'
        a = sv.rewrite(t, f'[YouTube]({URL})', 'f')
        self.assertEqual(sv.rewrite(a, f'[YouTube]({URL})', 'f'), a)
        self.assertEqual(sv.rewrite(a, sv.PLACEHOLDER, 'f'), t)

    def test_real_documents_have_exactly_one_marker_pair(self):
        for rel in SUBS:
            self.assertEqual(len(sv.MARK.findall((ROOT / rel).read_text(encoding='utf8'))), 1, rel)
        self.assertIn('<!--VIDEOURL-->', '\n'.join((ROOT / 'README.md').read_text(encoding='utf8').splitlines()[:36]), 'README first screen')


sys.path.insert(0, str(ROOT / 'scripts'))
import release_mode  # noqa: E402
DEV = release_mode.mode() == 'dev'
SUBS = ['README.md'] + (['docs/SUBMISSION.md'] if DEV else [])


class CommandLine(unittest.TestCase):
    def run_cli(self, *args, root=ROOT):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/set_video_url.py'), *args], capture_output=True, text=True, cwd=root)

    def test_dry_run_changes_nothing(self):
        before = [(ROOT / r).read_bytes() for r in SUBS]
        r = self.run_cli(URL, '--no-report')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('DRY RUN', r.stdout)
        self.assertIn(URL, r.stdout)
        self.assertEqual(before, [(ROOT / r_).read_bytes() for r_ in SUBS])

    def test_bad_url_exit_2(self):
        r = self.run_cli('https://example.com/x', '--no-report')
        self.assertEqual(r.returncode, 2)

    @unittest.skipUnless(DEV, 'docs/SUBMISSION.md is a local note: RESCUEMIND_MODE=public (I-180)')
    def test_apply_in_a_copy(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / 'scripts').mkdir()
            (d / 'docs').mkdir()
            shutil.copy(ROOT / 'scripts/set_video_url.py', d / 'scripts')
            shutil.copy(ROOT / 'scripts/release_mode.py', d / 'scripts')
            (d / 'docs/HANDOFF.md').parent.mkdir(exist_ok=True)
            (d / 'docs/HANDOFF.md').write_text('', encoding='utf8')      # dev mode in the copy
            shutil.copy(ROOT / 'README.md', d)
            shutil.copy(ROOT / 'docs/SUBMISSION.md', d / 'docs')
            r = subprocess.run([sys.executable, str(d / 'scripts/set_video_url.py'), URL, '--apply', '--no-report'], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(f'[YouTube]({URL})', (d / 'README.md').read_text(encoding='utf8'))
            self.assertIn(URL, (d / 'docs/SUBMISSION.md').read_text(encoding='utf8'))
            r = subprocess.run([sys.executable, str(d / 'scripts/set_video_url.py'), '--clear', '--apply', '--no-report'], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((d / 'README.md').read_text(encoding='utf8'), (ROOT / 'README.md').read_text(encoding='utf8'))


class SecretScan(unittest.TestCase):
    def kinds(self, text):
        return {k for k, _, _ in secret_scan.scan_text('f.txt', text)}

    def test_detects(self):       # tokens are assembled at run time so that this file itself stays clean
        cases = {
            'SECRET:aws-access-key': 'k = "' + 'AKIA' + 'ABCDEFGHIJKLMNOP' + '"',
            'SECRET:github-token': 'x ' + 'ghp_' + 'a1B2' * 9,
            'SECRET:sk-token': 'OPENAI=' + 'sk-' + 'proj-' + 'Ab12' * 8,
            'SECRET:google-api-key': 'key=' + 'AIza' + 'Sy' + 'A' * 33,
            'SECRET:huggingface-token': 't=' + 'hf_' + 'abcDEF1234' * 4,
            'SECRET:private-key': '-----BEGIN ' + 'RSA PRIVATE KEY-----',
            'SECRET:assigned-secret': 'api_key = "' + 'q8Zr4TnV7mLp2WxY9c' + '"',
            'PERSONAL:email': 'contact: ' + 'taro' + '@' + 'some-univ.ac.jp',
        }
        for kind, text in cases.items():
            self.assertIn(kind, self.kinds(text), kind)

    def test_no_false_alarm(self):
        for text in ('git@github.com:fe2131-art/rescue-mind.git', '232701181+fe2131-art@users.noreply.github.com', 'noreply@anthropic.com',
                     'api_key = "your-api-key-goes-here-1234"', 'token = os.environ["HF_TOKEN"]', 'password: "<password>"',
                     'sk-learn', 'see https://huggingface.co/Qwen/Qwen3.5-9B', 'ratio = a@b'):
            self.assertEqual(self.kinds(text), set(), text)

    def test_file_names(self):
        self.assertTrue(secret_scan.BAD_NAMES.search('configs/.env'))
        self.assertTrue(secret_scan.BAD_NAMES.search('x/id_rsa'))
        self.assertFalse(secret_scan.BAD_NAMES.search('docs/environment.md'))

    def test_repository_is_clean(self):
        names, findings, _ = secret_scan.scan_tracked(ROOT)
        self.assertGreater(len(names), 100)
        self.assertEqual(findings, [])


if __name__ == '__main__':
    unittest.main()
