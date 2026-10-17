#!/usr/bin/env python3
"""Count the unit tests discovered by `python3 -m unittest discover -s tests` and write
experiments/results/test_count.json.  Run inside rm-dev (needs the ROS Python environment):

  docker exec rm-dev rescuemind-entrypoint python3 scripts/count_tests.py

Also provides n_tests() / n_findings() so that every document reads the same two generated counts.
"""
from __future__ import annotations
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COUNT = ROOT / 'experiments/results/test_count.json'
FINDINGS = ROOT / 'docs/FINDINGS.md'


def n_tests():
    """Test count from test_count.json (None if the file has not been generated yet)."""
    return json.loads(COUNT.read_text(encoding='utf8'))['n_tests'] if COUNT.is_file() else None


def n_findings():
    """Number of rows in the main table of docs/FINDINGS.md (rows whose first cell is an integer)."""
    rows = []
    for line in FINDINGS.read_text(encoding='utf8').splitlines():
        if line.startswith('|'):
            first = line.split('|')[1].strip()
            if first.isdigit():
                rows.append(int(first))
        elif rows:
            break      # the main table is the first one: stop at its end
    assert rows == list(range(1, len(rows) + 1)), 'FINDINGS.md numbering is not 1..N'
    return len(rows)


def main():
    sys.path.insert(0, str(ROOT))
    n = unittest.TestLoader().discover(str(ROOT / 'tests'), top_level_dir=str(ROOT / 'tests')).countTestCases()
    COUNT.write_text(json.dumps({'n_tests': n, 'command': 'python3 -m unittest discover -s tests',
                                 'generator': 'scripts/count_tests.py'}, indent=1) + '\n', encoding='utf8')
    print('tests discovered:', n)


if __name__ == '__main__':
    main()
