#!/usr/bin/env python3
"""v2.7 entrypoint: guarded scenes, stationary + dual fresh-image gating.

The actual supervisor is implemented in v22_orchestrate and the production
mission ROS node, reused rather than duplicated for award demo consistency.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.v22_orchestrate import main
if __name__=='__main__':raise SystemExit(main())
