#!/usr/bin/env python3
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.bridge_contract import audit
print(json.dumps(audit(ROOT/'worlds/rescuemind_test_arena.sdf',ROOT/'configs/ros_gz_bridge_v20.yaml'),indent=2))
