"""I-09 regression: `nice` carries a file capability in the image; an exec through it runs in
glibc secure mode and strips LD_LIBRARY_PATH.  It must therefore wrap the shell that sources
ROS, never sit between the sourced shell and a ROS executable (rosbag broke exactly so)."""
import unittest
from pathlib import Path
import scripts.v32_orchestrate as orch


class PriorityWrapping(unittest.TestCase):
    def test_no_nice_inside_sourced_shell(self):
        plan = orch.build_plan('live', '避難所Bに飲料水を届けて', mission_timeout=900,
                               evidence_dir=Path('/tmp/abcdef0123456789'), capture_rosbag=True, film=True)
        for spec in plan['services'] + [plan['mission']]:
            argv = list(spec.argv)
            if 'bash' in argv and '-c' in argv:
                inner = argv[argv.index('-c') + 1]
                self.assertNotIn('exec nice', inner, spec.name)
                self.assertNotIn('&& nice ', inner, spec.name)

    def test_shell_scripts_do_not_exec_nice(self):
        root = Path(__file__).resolve().parents[1]
        for script in (root / 'scripts').glob('*.sh'):
            self.assertNotIn('exec nice', script.read_text(), script.name)


if __name__ == '__main__':
    unittest.main()
