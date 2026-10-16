#!/usr/bin/env python3
"""Stable-file hash manifest (excluding outputs that change when tests rerun)."""
from pathlib import Path
import hashlib,json,argparse
ROOT=Path(__file__).resolve().parents[1]
EXCLUDE_DIRS={'outputs','verification','__pycache__','.venv','.git','.pytest_cache'}
EXCLUDE_FILES={'SHA256_MANIFEST.json'}

def build(root=ROOT):
    sha={}
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.is_symlink(): continue
        rel=path.relative_to(root)
        if path.name in EXCLUDE_FILES or any(s in EXCLUDE_DIRS for s in rel.parts) or path.suffix=='.pyc':continue
        sha[rel.as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    return {'version':'v2.6.0','algorithm':'sha256','sha256':sha,
            'files':len(sha),'mutable_directories_not_pinned':['verification','outputs']}

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--write',action='store_true')
    a=parser.parse_args(argv)
    current=build();file=ROOT/'SHA256_MANIFEST.json'
    if a.write:
        file.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n')
    else:
        recorded=json.loads(file.read_text())
        if current!=recorded:
            raise SystemExit('SHA-256 MANIFEST MISMATCH')
    print(f'{"WROTE" if a.write else "PASS"} {current["files"]} stable SHA-256 files')
if __name__=='__main__':main()
