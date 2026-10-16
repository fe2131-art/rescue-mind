#!/usr/bin/env python3
"""v2.6 entrypoint: stationarity-gated v2.2 scene supervisor.

Both live accept and expected-denial paths require a stationary-evidence
receipt, in addition to independent odometry and (optional) ROS bag audits.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.v22_orchestrate import main
if __name__=='__main__':raise SystemExit(main())
