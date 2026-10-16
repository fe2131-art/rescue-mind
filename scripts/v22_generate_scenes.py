#!/usr/bin/env python3
"""Generate and static-audit three controlled Gazebo experiment worlds."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.scene_variants import build_scenarios,audit_scenarios

if __name__=='__main__':
    print(json.dumps(build_scenarios(ROOT/'worlds/rescuemind_test_arena.sdf',ROOT/'worlds/scenarios'),indent=2))
    print(json.dumps(audit_scenarios(ROOT/'worlds/scenarios'),indent=2))
