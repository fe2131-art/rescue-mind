#!/usr/bin/env python3
"""v2.9 supervised Gazebo entrypoint; rosbag finalization occurs before evidence audit."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.v22_orchestrate import main
if __name__=='__main__': raise SystemExit(main())
