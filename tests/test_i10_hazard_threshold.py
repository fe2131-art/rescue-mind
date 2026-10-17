"""I-10: the hazard threshold is configurable end to end and recorded."""
import unittest
from pathlib import Path

import scripts.v32_orchestrate as orch


class HazardThreshold(unittest.TestCase):
    def test_plan_passes_threshold_to_server(self):
        plan = orch.build_plan('live', '避難所Bに飲料水を届けて', mission_timeout=900,
                               evidence_dir=Path('/tmp/abcdef0123456789'), hazard_threshold=0.05)
        vlm = next(s for s in plan['services'] if s.name == 'primary_local_vlm')
        inner = ' '.join(vlm.argv)
        self.assertIn('--hazard-threshold 0.05', inner)

    def test_build_plan_default_keeps_v34_value(self):
        # build_plan's own default stays 0.5 (library default); the CLI default is v3.6 (see test below)
        plan = orch.build_plan('live', '避難所Bに飲料水を届けて', mission_timeout=900,
                               evidence_dir=Path('/tmp/abcdef0123456789'))
        vlm = next(s for s in plan['services'] if s.name == 'primary_local_vlm')
        self.assertIn('--hazard-threshold 0.5', ' '.join(vlm.argv))


class CliDefaults(unittest.TestCase):
    def test_cli_defaults_are_v36(self):
        import argparse, unittest.mock as um
        captured = {}
        def fake_build_plan(*a, **kw):
            captured.update(kw); raise SystemExit(0)
        with um.patch.object(orch, 'build_plan', fake_build_plan), um.patch.object(orch, 'audit_scenarios', create=True):
            try:
                orch.main(['--plan', '--scenario', 'live', '--scene', 'nominal'])
            except SystemExit:
                pass
        self.assertEqual(captured.get('hazard_threshold'), 0.05)
        self.assertEqual((captured.get('hazard_views'), captured.get('hazard_prompt')), ('tiles', 'h36'))
        self.assertEqual(captured.get('look_around'), 0.4)
        self.assertEqual(captured.get('model'), 'Qwen/Qwen3.5-9B')
        self.assertTrue(captured.get('recovery'))


if __name__ == '__main__':
    unittest.main()
