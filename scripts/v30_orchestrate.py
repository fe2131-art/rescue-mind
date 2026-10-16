#!/usr/bin/env python3
"""v3.0 live/denial rosbag graceful-finalization entrypoint.

Dispatches to the same validated controlled-scene orchestrator for real Ubuntu
ROS 2 Jazzy + Gazebo Harmonic; --plan is offline and has no side effects.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.v22_orchestrate import main
if __name__=='__main__': raise SystemExit(main())
