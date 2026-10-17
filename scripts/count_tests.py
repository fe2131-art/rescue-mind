#!/usr/bin/env python3
"""Count the test FUNCTIONS in tests/ (static AST count of `def test*` at module or class level; parametrised or
subTest cases are not multiplied) and write experiments/results/test_count.json.  Pure host python3: nothing is
imported or executed, so it is safe on a busy host:

  python3 scripts/count_tests.py

(--discover counts the cases unittest discovery would collect instead; that imports every test module, so run it
inside rm-dev only.)  Documents say "test functions" for this number.

Also provides n_tests() / n_findings() so that every document reads the same two generated counts.
"""
from __future__ import annotations
import json
import re
import sys
import ast
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


def static_count():
    """Number of `def test*` functions/methods in tests/*.py (module level and directly inside classes)."""
    n = 0
    for f in sorted((ROOT / 'tests').glob('test*.py')):
        tree = ast.parse(f.read_text(encoding='utf8'), filename=str(f))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test'):
                n += 1
    return n


def main():
    if '--discover' in sys.argv:       # imports every test module: rm-dev only
        import unittest
        sys.path.insert(0, str(ROOT))
        n = unittest.TestLoader().discover(str(ROOT / 'tests'), top_level_dir=str(ROOT / 'tests')).countTestCases()
        how, cmd = 'unittest discovery cases', 'python3 -m unittest discover -s tests'
    else:
        n = static_count()
        how, cmd = 'test functions (static AST count)', 'python3 scripts/count_tests.py'
    COUNT.write_text(json.dumps({'n_tests': n, 'unit': how, 'command': cmd,
                                 'generator': 'scripts/count_tests.py'}, indent=1) + '\n', encoding='utf8')
    print(f'{how}:', n)


if __name__ == '__main__':
    main()
