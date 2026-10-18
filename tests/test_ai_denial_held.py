"""X pilot finding (Amendment 1): an AI denial with a completed hold is classified as an expected denial also in the depot, where the
empty / swapped world comes from the world spec and --scene stays 'nominal'."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT))
import v32_orchestrate as vo  # noqa: E402


def write(d, events):
    (Path(d) / 'mission.json').write_text(json.dumps({'events': events}))


class AiDenialHeld(unittest.TestCase):
    def test_denial_and_hold_are_recognised(self):
        with tempfile.TemporaryDirectory() as d:
            write(d, [{'stage': 'checkpoint_decision', 'allow': False}, {'stage': 'checkpoint_denial_dwell_finished'}])
            self.assertTrue(vo.ai_denial_held(Path(d)))

    def test_no_hold_means_failed_not_expected(self):
        with tempfile.TemporaryDirectory() as d:
            write(d, [{'stage': 'checkpoint_decision', 'allow': False}])
            self.assertFalse(vo.ai_denial_held(Path(d)))

    def test_an_allow_is_never_a_denial(self):
        with tempfile.TemporaryDirectory() as d:
            write(d, [{'stage': 'checkpoint_decision', 'allow': True}, {'stage': 'checkpoint_denial_dwell_finished'}])
            self.assertFalse(vo.ai_denial_held(Path(d)))

    def test_missing_or_bad_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(vo.ai_denial_held(Path(d)))
            (Path(d) / 'mission.json').write_text('{bad')
            self.assertFalse(vo.ai_denial_held(Path(d)))

    def test_both_gates_use_it(self):
        src = (ROOT / 'scripts/v32_orchestrate.py').read_text()
        self.assertEqual(src.count('or ai_denial_held(log_dir)'), 2)


if __name__ == '__main__':
    unittest.main()
