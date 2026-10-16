#!/usr/bin/env python3
"""v2.8 entrypoint: sim-clock freshness on top of previous v2.7 mission gates."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.v22_orchestrate import main
if __name__=='__main__':raise SystemExit(main())
