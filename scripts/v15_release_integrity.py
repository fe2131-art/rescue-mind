#!/usr/bin/env python3
"""Verify pristine source package against the SHA-256 manifest. No network calls."""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
ROOT=Path(__file__).resolve().parents[1]

def check(root=ROOT):
    manifest=json.loads((root/'SHA256_MANIFEST.json').read_text(encoding='utf-8'))
    rows=manifest['files']
    issues=[]
    for rel,expected in rows.items():
        p=root/rel
        if not p.is_file():
            issues.append('missing: '+rel)
        elif hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
            issues.append('hash mismatch: '+rel)
    return {'ok':not issues,'files_checked':len(rows),'errors':issues,
            'note':'This verifies package integrity, not origin/authenticity or execution safety.'}

if __name__=='__main__':
    out=check()
    print(json.dumps(out,ensure_ascii=False,indent=2))
    raise SystemExit(0 if out['ok'] else 3)
