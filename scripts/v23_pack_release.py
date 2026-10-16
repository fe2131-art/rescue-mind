#!/usr/bin/env python3
"""Package all project source/research/results as a deterministic ZIP.

Immutable source/docs SHA256 are in SHA256_MANIFEST.json; verification/outputs
are mutable when tests are repeated. ZIP CRC + per-entry SHA256 are checked.
"""
from __future__ import annotations
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT.parent/'RescueMind_v2.3_Jev_Qwen38_Controlled30Trial_OfflineVerified.zip'

def files():
    return sorted(p for p in ROOT.rglob('*') if p.is_file() and
                  not any(part in {'.venv','__pycache__','.git','.pytest_cache'} or part.endswith('.egg-info') for part in p.relative_to(ROOT).parts))

def main():
    f=files();OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(OUTPUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for p in f:
            name=ROOT.name+'/'+p.relative_to(ROOT).as_posix()
            info=zipfile.ZipInfo(name,date_time=(2026,10,16,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o644 & 0xffff)<<16
            z.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=7)
    with zipfile.ZipFile(OUTPUT) as z:
        if z.testzip():raise RuntimeError('CRC failure')
        for p in f:
            name=ROOT.name+'/'+p.relative_to(ROOT).as_posix()
            if hashlib.sha256(z.read(name)).digest()!=hashlib.sha256(p.read_bytes()).digest():
                raise RuntimeError('hash mismatch '+name)
    out={'zip':str(OUTPUT),'files':len(f),'bytes':OUTPUT.stat().st_size,
         'zip_sha256':hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
         'crc_test':'PASS','entry_sha256':'PASS'}
    print(json.dumps(out,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
