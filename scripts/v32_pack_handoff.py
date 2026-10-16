#!/usr/bin/env python3
"""Make SHA256-verifiable code / logs ZIP; exclude transient training/runtime secrets."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
ZIP=ROOT.parent/'RescueMind_v3.2_Local_V100_32GB_Final_Handoff.zip'
MANIFEST=ROOT/'MANIFEST_SHA256.txt'
IGNORE_DIRS={'__pycache__','.venv','.venv-ros','.pytest_cache','.git','runs','.cache','build','dist'}
IGNORE_SUFFIX={'.pyc','.pyo','.key','.mp4'}

def should_include(p):
    rel=p.relative_to(ROOT)
    if not p.is_file() or any(part in IGNORE_DIRS for part in rel.parts): return False
    if p==MANIFEST or p.suffix in IGNORE_SUFFIX: return False
    if p.name=='.env' or p.name.startswith('.env.'): return False
    if p.stat().st_size>12_000_000: return False
    return True

files=sorted((p for p in ROOT.rglob('*') if should_include(p)),key=lambda p:p.relative_to(ROOT).as_posix())
lines=[hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(ROOT).as_posix() for p in files]
MANIFEST.write_text('\n'.join(lines)+'\n',encoding='utf8')
with zipfile.ZipFile(ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=8) as z:
    for p in [*files,MANIFEST]:
        z.write(p,arcname=ROOT.name+'/'+p.relative_to(ROOT).as_posix())
with zipfile.ZipFile(ZIP) as z:
    assert z.testzip() is None
    count=0
    for line in z.read(ROOT.name+'/MANIFEST_SHA256.txt').decode().splitlines():
        h,path=line.split('  ',1)
        assert hashlib.sha256(z.read(ROOT.name+'/'+path)).hexdigest()==h
        count+=1
    assert count==len(files)
report={'zip':str(ZIP),'zip_size_bytes':ZIP.stat().st_size,
        'zip_files':len(files)+1,'sha256_matched':count,
        'crc_ok':True, 'model_weight_files_included':False,
        'scope':'ARCHIVE_INTEGRITY_NOT_GPU_INFERENCE',
        'zip_sha256':hashlib.sha256(ZIP.read_bytes()).hexdigest()}
print(json.dumps(report,ensure_ascii=False,indent=2))
(ROOT.parent/'RescueMind_v3.2_LOCAL_RELEASE_CHECK.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
