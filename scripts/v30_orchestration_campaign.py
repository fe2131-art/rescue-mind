#!/usr/bin/env python3
"""Re-execute offline orchestration fault matrix (NOT live ROS/Gazebo)."""
from __future__ import annotations
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
TEST=ROOT/'tests/test_v30_denial_bag_orchestration.py'
suite=unittest.defaultTestLoader.discover(str(TEST.parent),pattern=TEST.name)
result=unittest.TextTestRunner(stream=sys.stderr,verbosity=1).run(suite)
report={'version':'3.0.0','scope':'MOCKED_ORCHESTRATOR_NO_LIVE_ROS_GAZEBO_JEV_QWEN',
        'scenario_tests':result.testsRun,'successful':result.wasSuccessful(),
        'failures':len(result.failures),'errors':len(result.errors)}
ROOT.joinpath('verification/v30').mkdir(parents=True,exist_ok=True)
ROOT.joinpath('verification/v30/orchestration_campaign.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
if not result.wasSuccessful():raise SystemExit(1)
