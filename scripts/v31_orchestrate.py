#!/usr/bin/env python3
"""v3.1 entrypoint: ROS runtime command publisher topology watch + v3.0."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.v22_orchestrate import main
if __name__=='__main__':
    raise SystemExit(main())
