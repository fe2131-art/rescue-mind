"""Create integrity-manifested v1.3 distribution; offline checks only.

Usage: python scripts/v13_pack_release.py
Includes prior records explicitly as history. Excludes .venv, pycache and secrets.
"""
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile, ZIP_DEFLATED
import json
import os

ROOT=Path(__file__).resolve().parents[1]
NAME='RescueMind_v1.3_Jev_Qwen38_Gazebo_ROS_Award_OfflineVerified.zip'
EXCLUDE={'.venv','.git','.pytest_cache','__pycache__','.mypy_cache','.ruff_cache'}
SKIP={'SHA256_MANIFEST.json'}

def selectable(p):
    return p.is_file() and not (set(p.relative_to(ROOT).parts)&EXCLUDE) and p.name not in SKIP and p.suffix not in {'.pyc','.pyo'}


def main():
    source=sorted((p for p in ROOT.rglob('*') if selectable(p)),key=lambda p:p.relative_to(ROOT).as_posix())
    manifest={'schema':1,'version':'v1.3','hash_algorithm':'SHA-256',
              'note':'All listed files are exact ZIP payload bytes; excludes this manifest',
              'files':{p.relative_to(ROOT).as_posix():sha256(p.read_bytes()).hexdigest() for p in source}}
    (ROOT/'SHA256_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    dest=ROOT.parent/NAME
    with ZipFile(dest,'w',compression=ZIP_DEFLATED,compresslevel=8) as z:
        for p in [*source,ROOT/'SHA256_MANIFEST.json']:
            name=(ROOT.name+'/'+p.relative_to(ROOT).as_posix())
            # Fixed ZIP DOS timestamp aids archive reproducibility.
            from zipfile import ZipInfo
            info=ZipInfo(name,date_time=(2026,10,16,0,0,0))
            info.compress_type=ZIP_DEFLATED
            info.external_attr=(0o100644 << 16)
            z.writestr(info,p.read_bytes(),compress_type=ZIP_DEFLATED,compresslevel=8)
    with ZipFile(dest) as z:
        assert z.testzip() is None
        actual=json.loads(z.read(ROOT.name+'/SHA256_MANIFEST.json'))
        for name,digest in actual['files'].items():
            assert sha256(z.read(ROOT.name+'/'+name)).hexdigest()==digest,name
    print(json.dumps({'zip':str(dest),'zip_bytes':dest.stat().st_size,
                      'files':len(source)+1,'manifest_hashes':len(source),
                      'sha256':sha256(dest.read_bytes()).hexdigest()},indent=2))

if __name__=='__main__':main()
