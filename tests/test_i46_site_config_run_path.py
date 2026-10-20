"""I-46: `--site-config` must reach the mission command on the RUN path of the orchestrator, not only in --plan (study GC's pilot found it: the
mission did not record the site config, so the completion audit compared the server's tau_h with the default 0.05)."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))


class SiteConfigRunPath(unittest.TestCase):
    def test_every_build_plan_call_in_main_passes_the_site_config(self):
        src = (ROOT / 'scripts/v32_orchestrate.py').read_text()
        main = src[src.index('def main('):]
        calls = [m.start() for m in re.finditer(r'build_plan\(', main)]
        self.assertEqual(len(calls), 2)                          # the --plan path and the --run path
        for i in calls:
            block = main[i:i + 1100]
            self.assertIn("'site_config': args.site_config", block)

    def test_the_planned_mission_command_carries_the_flag(self):
        import v32_orchestrate as o
        plan = o.build_plan('live', 'x', mission_timeout=60, site_config='experiments/gc_site_cal.json')
        self.assertIn('--site-config experiments/gc_site_cal.json', str(vars(plan['mission'])))


if __name__ == '__main__':
    unittest.main()
