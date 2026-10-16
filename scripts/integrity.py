"""Reproducible SHA256 manifest for immutable source/docs only.

Generated outputs and verification logs can legitimately change on rerun.
Their bytes remain checked against ZIP entries during release packaging.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'SHA256_MANIFEST.json'

def files():
    return sorted(p for p in ROOT.rglob('*') if p.is_file() and '.venv' not in p.parts and
                  '__pycache__' not in p.parts and '.git' not in p.parts and
                  not any(x.endswith('.egg-info') for x in p.parts) and
                  p.name!='SHA256_MANIFEST.json' and p.suffix!='.pyc' and
                  p.relative_to(ROOT).parts[0] not in ('verification','outputs'))

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    now={str(x.relative_to(ROOT)):digest(x) for x in files()}
    if a.check:
        expect=json.loads(MANIFEST.read_text(encoding='utf-8'))['sha256']
        mismatch={'missing':[k for k in expect if k not in now],
                  'extra':[k for k in now if k not in expect],
                  'changed':[k for k in now if k in expect and now[k]!=expect[k]]}
        print(json.dumps(mismatch,ensure_ascii=False,indent=2))
        if any(mismatch.values()):raise SystemExit(1)
        print(f'OK: {len(expect)} paths hash matched')
    else:
        MANIFEST.write_text(json.dumps({'schema':'sha256-manifest-v1','sha256':now},ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'Wrote {MANIFEST} with {len(now)} files')

if __name__=='__main__':main()
