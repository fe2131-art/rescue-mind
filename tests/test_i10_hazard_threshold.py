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

    def test_default_is_registered_v34_value(self):
        plan = orch.build_plan('live', '避難所Bに飲料水を届けて', mission_timeout=900,
                               evidence_dir=Path('/tmp/abcdef0123456789'))
        vlm = next(s for s in plan['services'] if s.name == 'primary_local_vlm')
        self.assertIn('--hazard-threshold 0.5', ' '.join(vlm.argv))


if __name__ == '__main__':
    unittest.main()
