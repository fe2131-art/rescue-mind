#!/usr/bin/env python3
"""Regenerate/verify stable-file SHA-256 manifest (exclude mutable outputs)."""
from pathlib import Path
import hashlib,json,argparse
ROOT=Path(__file__).resolve().parents[1]
EXCLUDE_DIRS={'outputs','verification','__pycache__','.venv','.git','.pytest_cache'}
EXCLUDE_FILES={'SHA256_MANIFEST.json'}

def stable_files():
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file() or p.name in EXCLUDE_FILES or any(part in EXCLUDE_DIRS for part in p.relative_to(ROOT).parts):
            continue
        if p.suffix == '.pyc':continue
        yield p

def build():
    sha={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in stable_files()}
    return {'version':'v2.1.0','algorithm':'sha256','sha256':sha,
            'files':len(sha),'mutable_directories_not_pinned':['verification','outputs']}

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--write',action='store_true')
    args=a.parse_args()
    current=build();path=ROOT/'SHA256_MANIFEST.json'
    if args.write:
        path.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print('WROTE immutable SHA manifest:',current['files']);return 0
    try: saved=json.loads(path.read_text(encoding='utf8'))
    except (OSError,ValueError) as e:
        print('INVALID MANIFEST',e);return 2
    ok=saved==current
    print(('PASS' if ok else 'FAIL')+f' sha256 stable source files: {current["files"]}')
    return 0 if ok else 3

if __name__=='__main__':raise SystemExit(main())
