"""Submission snapshot mode (SNAPSHOT=1, `make snapshot`): studies without results read "registered, not yet run at submission".

  * no TBD / pending marker survives in the snapshot output (paper macros and tables, expanded sources, README, YouTube text);
  * FINAL=1 stays strict (a pending result refuses the build) and excludes SNAPSHOT;
  * a pending study's sentence is its pending form, a study with results keeps its normal sentence;
  * check_consistency.py --snapshot accepts the pending wording and still catches a TBD / a wrong number.

Host python3 only (subprocesses write to a temporary directory; the tracked documents are never touched).
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import advice_numbers  # noqa: E402

ALL = 'X'                                         # the studies without a result file (A has results since 2026-10-18 18:00, IF since the evening: IF1 failed; S since 20:16, B since 22:30, XD since 2026-10-19 04:21, Q since 04:54, IF2 since 05:17)
TEX = [ROOT / 'docs/paper' / f for f in ('main.tex', 'supplement.tex', 'sec_formal.tex')]


def run(args, env=None, **kw):
    e = {**os.environ, **(env or {})}
    for k in ('SNAPSHOT', 'FINAL', 'SNAPSHOT_PENDING', 'SNAPSHOT_DIR'):
        if not env or k not in env:
            e.pop(k, None)
    return subprocess.run([sys.executable, *args], cwd=ROOT, env=e, capture_output=True, text=True, **kw)


def numbers(out, extra=(), env=None, snapshot=True):
    r = run(['scripts/paper_numbers.py', *(['--snapshot'] if snapshot else []), '--out', str(out), *extra], env=env)
    assert r.returncode == 0, r.stderr[-800:]
    return Path(out, 'numbers.tex').read_text(encoding='utf8')


class TestSnapshotNumbers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'paper'
        cls.num = numbers(cls.out, env={'SNAPSHOT_PENDING': ALL})

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_no_tbd_in_snapshot_output(self):
        # no macro value is TBD; the only TBD left is the definition of the fallback, which prints "not run"
        self.assertEqual([ln for ln in self.num.splitlines() if 'TBD' in ln and not ln.startswith(('\\providecommand{\\TBD}', '\\newcommand{\\TBDfor}'))], [])
        self.assertIn('\\providecommand{\\TBD}{\\SnapNA{}}', self.num)
        self.assertNotIn('red', self.num.split('\\newcommand{\\NTests}')[0])
        for f in sorted(self.out.glob('tab_*.tex')):
            self.assertNotIn('\\TBD', f.read_text(encoding='utf8'), f.name)
        # the pending studies' claim column and the study table say "registered, not run"
        self.assertNotIn('\\newcommand{\\StatA}{registered, not run}', self.num)      # A has results: its claim column is the result
        self.assertIn('\\newcommand{\\StatX}{registered, not run}', self.num)
        prereg = (self.out / 'tab_prereg.tex').read_text(encoding='utf8')
        self.assertNotIn('pending', prereg)
        rows = {ln.split(' & ')[0]: ln for ln in prereg.splitlines() if ' & ' in ln}
        self.assertNotIn('not run', rows['A'].split(' & ')[2])                         # A: first-results commit is shown
        for k_ in ('XD', 'Q'):
            self.assertNotIn('not run', rows[k_].split(' & ')[2])                       # first-results commit is shown
        for k_ in ('IF2',):
            self.assertNotIn('not run', rows[k_].split(' & ')[2])
        for k in ('X',):
            self.assertIn('not run', rows[k].split(' & ')[2], k)               # first-results cell
            self.assertRegex(rows[k].split(' & ')[1], r'\\texttt\{[0-9a-f]{7} \d{4}-\d\d-\d\d\}')   # registered (commit, date)

    def test_every_number_of_a_pending_study_is_wrapped(self):
        self.assertEqual(
            __import__('paper_numbers').snapshot_problems(TEX, self.num, set(ALL.split(','))), [])

    def test_counts_use_the_snapshot_table(self):
        rows = [ln for ln in (self.out / 'tab_prereg.tex').read_text(encoding='utf8').splitlines() if ln.count('&') >= 4 and not ln.startswith('Study')]
        c = advice_numbers.study_counts_from_rows(rows)
        self.assertEqual(c['pending'], len(ALL.split(',')))
        self.assertIn(f"\\newcommand{{\\NStudiesPending}}{{{c['pending']}}}", self.num)
        self.assertIn('\\newcommand{\\PendList}{X}', self.num)

    def test_default_build_prints_the_normal_form(self):
        with tempfile.TemporaryDirectory() as td:
            num = numbers(td, snapshot=False)
        self.assertIn('\\providecommand{\\TBD}{\\textcolor{gray}{\\textit{(pending)}}}', num)
        for k in ('A', 'S', 'X', 'XD', 'B', 'IF', 'Q', 'IFtwo'):
            self.assertIn(f'\\newcommand{{\\IfPend{k}}}[2]{{#2}}', num)
        self.assertIn('\\newcommand{\\IfAnyPend}[2]{#2}', num)
        self.assertNotIn('registered, not run', num)

    def test_snapshot_and_final_exclude_each_other(self):
        with tempfile.TemporaryDirectory() as td:
            r = run(['scripts/paper_numbers.py', '--snapshot', '--final', '--out', td])
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('exclude each other', r.stderr)
        r = subprocess.run(['bash', 'scripts/build_paper.sh'], cwd=ROOT, env={**os.environ, 'SNAPSHOT': '1', 'FINAL': '1'}, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn('exclude each other', r.stderr)


class TestStrictFinalStillRefuses(unittest.TestCase):
    def test_check_final_refuses_a_pending_macro_or_table(self):
        import paper_numbers as pn
        m = pn.Macros()
        m['Fine'] = '3'
        pn.check_final(m, {'tab_x.tex': r'\begin{tabular}{l}1\end{tabular}'})          # nothing pending: accepted
        m['APairs'] = r'\TBD'
        with self.assertRaises(SystemExit) as cm:
            pn.check_final(m, {})
        self.assertIn('APairs', str(cm.exception))
        m2 = pn.Macros()
        with self.assertRaises(SystemExit):
            pn.check_final(m2, {'tab_h_arms.tex': r'\begin{tabular}{l}\TBD\end{tabular}'})

    def test_final_run_refuses_while_a_result_is_missing(self):
        if all(advice_numbers.pending_all().values()):
            self.skipTest('every study has results: nothing is pending')
        with tempfile.TemporaryDirectory() as td:
            r = run(['scripts/paper_numbers.py', '--final', '--out', td])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('pending (TBD)', r.stderr)
        # and the FINAL-mode definition of \TBD is a LaTeX error, never a printed phrase
        self.assertIn('PackageError', subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0,"scripts"); import paper_numbers as p; print(p.TBD_DEF)'],
                                                      cwd=ROOT, env={**os.environ, 'FINAL': '1'}, capture_output=True, text=True).stdout)


class TestPendingSentence(unittest.TestCase):
    main = (ROOT / 'docs/paper/main.tex').read_text(encoding='utf8')

    def expand(self, pending):
        import paper_numbers as pn
        return pn.snapshot_expand(self.main, set(pending))

    def test_pending_study_a_gets_the_pending_form(self):
        t = self.expand({'A'})
        self.assertRegex(t, r'Study A\} \(registered: \\RegA\) was not run at submission')
        self.assertNotIn('Worlds with an unsafe delivery', t)       # the sentence that needs the numbers of A is gone (forced pending form, results exist)
        self.assertNotIn('\\AUnsafeNaive', t)
        abstract = t.split('\\begin{abstract}')[1].split('\\end{abstract}')[0]
        self.assertIn('Not run at submission: \\PendList{}', abstract)
        self.assertIn('only the structural result (Prop.~2; A not run at submission)', t.split('\\section{Conclusion}')[1])          # claims that depend on A are conditional

    def test_a_study_with_results_keeps_its_sentence(self):
        t = self.expand({'S'})                                      # only S pending: A keeps its normal sentence
        self.assertIn('Worlds with an unsafe delivery', t)
        self.assertRegex(t, r'Study S \(registered: \\RegS; image level, 64 worlds')      # S itself is pending
        self.assertNotIn('Study S (image level, \\SNPairs', t)
        t_s = self.expand({'A'})                                    # only A pending: S keeps its normal sentence
        self.assertIn('Study S (image level, \\SNPairs', t_s)
        t0 = self.expand(set())                                     # nothing pending: the normal text everywhere
        self.assertIn('Signs flipped a refusal', t0)
        self.assertNotIn('not run at submission', t0)

    def test_snapshot_expansion_matches_the_switches_of_numbers_tex(self):
        with tempfile.TemporaryDirectory() as td:
            num = numbers(td, env={'SNAPSHOT_PENDING': 'A,Q'})
        self.assertIn('\\newcommand{\\IfPendA}[2]{#1}', num)
        self.assertIn('\\newcommand{\\IfPendS}[2]{#2}', num)
        self.assertIn('\\newcommand{\\IfPendQ}[2]{#1}', num)
        self.assertIn('\\newcommand{\\StatA}{registered, not run}', num)
        self.assertNotIn('\\newcommand{\\StatS}{registered, not run}', num)

    def test_wording_helpers(self):
        self.assertIn('登録済み・提出時点で未実施', advice_numbers.pending_ja('A'))
        self.assertRegex(advice_numbers.pending_en('A'), r'registered, not yet run at submission \(registration [0-9a-f]{7}, \d{4}-\d\d-\d\d\)')
        old = os.environ.get('SNAPSHOT_PENDING'), os.environ.get('SNAPSHOT')
        try:
            os.environ['SNAPSHOT_PENDING'], os.environ['SNAPSHOT'] = 'B,A', '1'
            self.assertEqual(advice_numbers.pending_list(), ['A', 'B'])
            self.assertTrue(advice_numbers.is_pending('A') and not advice_numbers.is_pending('S'))
            os.environ['SNAPSHOT'] = '0'
            self.assertFalse(advice_numbers.is_pending('A'))        # outside the snapshot nothing changes
        finally:
            for k, v in zip(('SNAPSHOT_PENDING', 'SNAPSHOT'), old):
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


class TestSnapshotDocuments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        env = {'SNAPSHOT_DIR': str(cls.dir), 'SNAPSHOT_PENDING': ALL}
        for args in (['scripts/update_readme_results.py', '--snapshot'], ['scripts/make_youtube_description.py', '--snapshot']):
            r = run(args, env=env)
            assert r.returncode == 0, r.stderr[-600:]
        numbers(cls.dir / 'paper', env=env)
        cls.env = env
        cls.readme = (cls.dir / 'README.md').read_text(encoding='utf8')
        cls.yt = (cls.dir / 'YOUTUBE_DESCRIPTION.md').read_text(encoding='utf8')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_readme_and_youtube_say_registered_not_run(self):
        for t in (self.readme, self.yt):
            self.assertIn('登録済み・提出時点で未実施', t)
            self.assertNotRegex(t, r'TBD|\(pending\)|\bpending\b|実行中（事前登録済み）|結果待ち|実行待ち|pre-registered, running|not yet run(?! at submission)')
        self.assertIn('registered, not yet run at submission', self.readme)
        self.assertIn('X', self.yt)
        self.assertLessEqual(len(self.yt.split('## 概要欄\n', 1)[1].split('\n\n## 公開設定', 1)[0]), 4900)

    def test_tracked_documents_are_untouched(self):
        # the snapshot never writes the tracked README / YouTube text (the default text still names the running study A)
        self.assertNotEqual((ROOT / 'README.md').read_text(encoding='utf8'), self.readme)

    def test_check_consistency_accepts_the_snapshot_and_catches_a_tbd(self):
        r = run(['scripts/check_consistency.py', '--snapshot', '--no-report'], env=self.env)
        self.assertIn('snapshot README: no TBD / pending / running / waiting marker', r.stdout)
        bad = [ln for ln in r.stdout.splitlines() if ln.startswith('MISMATCH')]
        self.assertEqual(bad, [], r.stdout[-1500:])
        # inconsistency 1: a TBD and a "running" in the README
        (self.dir / 'README.md').write_text(self.readme + '\n評価A：TBD、実行中（事前登録済み）\n', encoding='utf8')
        try:
            r = run(['scripts/check_consistency.py', '--snapshot', '--no-report'], env=self.env)
            self.assertEqual(r.returncode, 1)
            self.assertTrue(any(ln.startswith('MISMATCH') and 'snapshot README: no TBD' in ln for ln in r.stdout.splitlines()), r.stdout[-800:])
            # inconsistency 2: a wrong number is still caught in snapshot mode
            wrong = re.sub(r'\*\*(\d+)/(\d+) → (\d+)/(\d+)\*\*', lambda m: f'**{int(m.group(1)) + 1}/{m.group(2)} → {m.group(3)}/{m.group(4)}**', self.readme)     # study G's headline numbers (every occurrence)
            self.assertNotEqual(wrong, self.readme)
            (self.dir / 'README.md').write_text(wrong, encoding='utf8')
            r = run(['scripts/check_consistency.py', '--snapshot', '--no-report'], env=self.env)
            self.assertEqual(r.returncode, 1)
        finally:
            (self.dir / 'README.md').write_text(self.readme, encoding='utf8')

    def test_check_consistency_catches_a_stale_snapshot(self):
        # a snapshot built for another pending set than the result files say: the Table S9 count differs
        r = run(['scripts/check_consistency.py', '--snapshot', '--no-report'], env={**self.env, 'SNAPSHOT_PENDING': 'A,' + ALL})
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any(ln.startswith('MISMATCH') and 'Table S9' in ln for ln in r.stdout.splitlines()), r.stdout[-800:])


if __name__ == '__main__':
    unittest.main()
