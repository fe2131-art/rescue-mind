#!/usr/bin/env python3
"""Reproducible-ish zipped source tree: excludes working venv, caches, live runs."""
from pathlib import Path
import argparse,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT.parent/'RescueMind_v2.6_Jev_Qwen38_PhysicalStationarity_Award_OfflineVerified.zip'
SKIP={'__pycache__','.venv','.git','.pytest_cache'}
def included(p):
    rel=p.relative_to(ROOT)
    return (p.is_file() and not p.is_symlink() and p.suffix!='.pyc'
            and not any(x in SKIP for x in rel.parts)
            and rel.parts[:2]!=('outputs','runs'))
def pack(output=DEFAULT):
    output=Path(output)
    allfiles=sorted((p for p in ROOT.rglob('*') if included(p)),key=lambda p:str(p.relative_to(ROOT)))
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8,strict_timestamps=False) as z:
        for path in allfiles:z.write(path,'rescuemind_v26/'+path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(output) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or len(names)!=len(allfiles):raise ValueError('Duplicate/incomplete ZIP')
        if z.testzip() is not None:raise ValueError('ZIP CRC failure')
    return {'release':'v2.6.0','zip_path':str(output),'bytes':output.stat().st_size,
            'zip_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'entries':len(allfiles),'crc_pass':True,'unverified_api_or_simulator':True}
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,default=DEFAULT)
    print(json.dumps(pack(a.parse_args().out),ensure_ascii=False,indent=2))
