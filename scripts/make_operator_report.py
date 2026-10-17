#!/usr/bin/env python3
"""I-18: render the one-page operator report of a run (PNG + PDF) from its mission.json / stack_result.json.

  python3 scripts/make_operator_report.py outputs/runs/<run_id>            # -> <run>/operator_report.{png,pdf}
  python3 scripts/make_operator_report.py outputs/runs/<run_id> --out docs/figures/operator_report_example.png

The renderer lives in rescuemind/operator_report_render.py (also called automatically by v32_orchestrate.py).
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind.operator_report_render import render  # noqa: E402,F401


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('run_dir', type=Path)
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    print(render(a.run_dir, a.out or a.run_dir / 'operator_report.png'))


if __name__ == '__main__':
    main()
