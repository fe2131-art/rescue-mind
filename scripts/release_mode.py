#!/usr/bin/env python3
"""Development or public mode of the checks (I-180).

The internal development notes (docs/HANDOFF.md, docs/SUBMISSION.md, ...) stay in the working tree but are not tracked
(.gitignore), so a fresh clone of the public repository does not have them.  The checks that read them run only in the
development mode:

  RESCUEMIND_MODE=dev      internal notes are required; a missing one is an error (use this while developing)
  RESCUEMIND_MODE=public   internal notes are ignored even when present (what a fresh clone sees)
  unset (auto)             dev when docs/HANDOFF.md exists, else public

  python3 scripts/release_mode.py      # prints the mode and the internal notes found
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERNAL = ('docs/HANDOFF.md', 'docs/SUBMISSION.md')      # the internal notes some checks read


def mode() -> str:
    m = os.environ.get('RESCUEMIND_MODE', '').strip().lower()
    if m in ('dev', 'public'):
        return m
    return 'dev' if (ROOT / 'docs/HANDOFF.md').is_file() else 'public'


def internal(rel: str) -> bool:
    """True when the check of the internal note `rel` should run.  In dev mode a missing note raises."""
    if mode() == 'public':
        return False
    if not (ROOT / rel).is_file():
        raise FileNotFoundError(f'{rel} is missing but RESCUEMIND_MODE is dev (set RESCUEMIND_MODE=public to skip it)')
    return True


if __name__ == '__main__':
    print('mode:', mode())
    for r in INTERNAL:
        print(f"  {r}: {'present' if (ROOT / r).is_file() else 'absent'}")
    sys.exit(0)
