"""scripts/release_mode.py: RESCUEMIND_MODE switches the checks of the local development notes on (dev) and off (public) (I-180)."""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import release_mode  # noqa: E402


class ReleaseMode(unittest.TestCase):
    def test_public_skips_even_when_present(self):
        with mock.patch.dict(os.environ, {'RESCUEMIND_MODE': 'public'}):
            self.assertEqual(release_mode.mode(), 'public')
            self.assertFalse(release_mode.internal('README.md'))

    def test_dev_requires_the_note(self):
        with mock.patch.dict(os.environ, {'RESCUEMIND_MODE': 'dev'}):
            self.assertTrue(release_mode.internal('README.md'))
            with self.assertRaises(FileNotFoundError):
                release_mode.internal('docs/no_such_note.md')

    def test_auto_follows_the_handoff_note(self):
        with mock.patch.dict(os.environ, {'RESCUEMIND_MODE': ''}):
            self.assertEqual(release_mode.mode(), 'dev' if (ROOT / 'docs/HANDOFF.md').is_file() else 'public')


if __name__ == '__main__':
    unittest.main()
