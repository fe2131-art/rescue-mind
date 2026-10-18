"""Pre-flight checks of the queued GPU studies (docs/PREFLIGHT_2026-10-18.md): syntax and structure of the run scripts, the
stale-ledger guard, and the study A intent-prompt switch of the protocol generator."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import ledger_stack_check as lsc  # noqa: E402
from scripts import make_protocol_a as mpa  # noqa: E402

QUEUE = ('a_run', 'if_run', 's_render', 's_eval', 'b_run', 'xd_render', 'xd_eval', 'x_run', 'q_run')


def src(name):
    return (ROOT / 'scripts' / f'{name}.sh').read_text()


class QueueScripts(unittest.TestCase):
    def test_syntax(self):
        for n in QUEUE:
            self.assertEqual(subprocess.run(['bash', '-n', str(ROOT / 'scripts' / f'{n}.sh')]).returncode, 0, n)

    def test_no_unbounded_server_wait(self):
        for n in ('s_eval', 'xd_eval'):
            self.assertNotRegex(src(n), r'until curl', n)
            self.assertIn('docker exec -d', src(n))           # the server runs in rm-next, the host python has no transformers
            self.assertIn('/.dockerenv', src(n))

    def test_a_run_gate_before_pilot_and_guards(self):
        s = src('a_run')
        self.assertLess(s.index('A_REGISTERED'), s.index('run_campaign.py --protocol "$PILOT"'))
        self.assertLess(s.index('ledger_stack_check.py --protocol "$PILOT"'), s.index('run_campaign.py --protocol "$PILOT"'))
        self.assertIn('port 8765 is in use', s)

    def test_b_x_guards(self):
        for n in ('b_run', 'x_run'):
            self.assertIn('ledger_stack_check.py', src(n))
            self.assertIn('port 8765 is in use', src(n))
        self.assertIn('git diff --quiet HEAD', src('x_run'))

    def test_q_zeroshot_container_has_sentencepiece(self):
        self.assertIn('Q_ZS_CONTAINER:-rm-dev', src('q_run'))

    def test_if_q_error_guard(self):
        self.assertIn('parser error', src('if_run'))
        self.assertIn('ended in an error', src('q_run'))


class LedgerGuard(unittest.TestCase):
    proto = {'common_stack_args': ['--intent-prompt', 'i38'], 'trials': [{'id': 'T1'}, {'id': 'T2', 'stack_args': ['--x']}]}

    def test_match_and_mismatch(self):
        ok = [{'trial_id': 'T1', 'stack_args': ['--intent-prompt', 'i38']}, {'trial_id': 'T2', 'stack_args': ['--intent-prompt', 'i38', '--x']}]
        self.assertEqual(lsc.mismatches(self.proto, ok), [])
        old = [{'trial_id': 'T1', 'stack_args': []}, {'trial_id': 'other', 'stack_args': []}]
        bad = lsc.mismatches(self.proto, old)
        self.assertEqual([b[0] for b in bad], ['T1'])

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            p, l = Path(d) / 'p.json', Path(d) / 'l.jsonl'
            p.write_text(json.dumps(self.proto))
            self.assertEqual(lsc.main(['--protocol', str(p), '--ledger', str(l)]), 0)          # no ledger
            l.write_text(json.dumps({'trial_id': 'T1', 'stack_args': []}) + '\n')
            self.assertEqual(lsc.main(['--protocol', str(p), '--ledger', str(l)]), 1)


class StudyAIntentPrompt(unittest.TestCase):
    def tearDown(self):
        mpa.INTENT_PROMPT = None

    def test_default_is_the_registered_protocol(self):
        self.assertEqual(mpa.INTENT_PROMPT, None)
        self.assertEqual(mpa.build()['common_stack_args'], [])
        self.assertEqual(mpa.build_pilot()['common_stack_args'], [])

    def test_amended_protocol_only_changes_the_stack_arguments(self):
        base, pilot = mpa.build(), mpa.build_pilot()
        mpa.INTENT_PROMPT = 'i38'
        a, ap = mpa.build(), mpa.build_pilot()
        self.assertEqual(a['common_stack_args'], ['--intent-prompt', 'i38'])
        self.assertEqual(ap['common_stack_args'], ['--intent-prompt', 'i38'])
        self.assertEqual(a['trials'], base['trials'])
        self.assertEqual(ap['trials'], pilot['trials'])

    def test_write_refuses_a_different_protocol_without_amend(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'p.json'
            out.write_text(json.dumps({'x': 1}))
            with self.assertRaises(SystemExit):
                mpa.write({'x': 2, 'advice_files': {}}, out)
            mpa.write({'x': 2, 'advice_files': {}}, out, amend=True)
            self.assertEqual(json.loads(out.read_text())['x'], 2)

    def test_cli_needs_amend(self):
        r = subprocess.run([sys.executable, str(ROOT / 'scripts/make_protocol_a.py'), '--intent-prompt', 'i38'], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('--amend', r.stderr + r.stdout)


if __name__ == '__main__':
    unittest.main()
