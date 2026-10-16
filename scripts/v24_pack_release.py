#!/usr/bin/env python3
"""Package v2.4, excluding transient run data and Python caches; CRC check."""
from pathlib import Path
import argparse,hashlib,json,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT.parent/'RescueMind_v2.4_Jev_Qwen38_ExpectedDenial_TrialRegistry_OfflineVerified.zip'
SKIP_PARTS={'__pycache__','.venv','.git','.pytest_cache'}
def include(p):
    rel=p.relative_to(ROOT)
    if any(x in SKIP_PARTS for x in rel.parts) or p.suffix=='.pyc':return False
    if rel.parts[:2]==('outputs','runs'):return False
    if p.is_symlink():return False
    return True

def pack(output=DEFAULT):
    output=Path(output); files=sorted(p for p in ROOT.rglob('*') if p.is_file() and include(p))
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8,strict_timestamps=False) as z:
        for path in files:z.write(path,'rescuemind_v24/'+path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(output) as z:
        corrupt=z.testzip()
        if corrupt:raise RuntimeError('ZIP CRC failed: '+corrupt)
        paths=z.namelist()
        if len(paths)!=len(set(paths)):raise RuntimeError('duplicate ZIP filename')
        assert len(paths)==len(files)
    return {'release':'2.4','path':str(output),'zip_bytes':output.stat().st_size,
            'zip_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'zip_file_count':len(files),
            'crc':'PASS','exclude_runtime_runs':True}

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--out',type=Path,default=DEFAULT)
    args=a.parse_args();r=pack(args.out)
    print(json.dumps(r,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
