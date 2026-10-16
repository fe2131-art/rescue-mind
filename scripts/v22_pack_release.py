#!/usr/bin/env python3
"""Package project plus experiments; archive itself is validated by separate clean test."""
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT.parent/'RescueMind_v2.2_Jev_Qwen38_Controlled_Scenes_Award_OfflineVerified.zip'
EXCLUDE={'.venv','__pycache__','.git','.pytest_cache'}
files=[p for p in ROOT.rglob('*') if p.is_file() and not any(t in EXCLUDE for t in p.relative_to(ROOT).parts)
       and p.suffix!='.pyc']
with zipfile.ZipFile(TARGET,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
    for p in sorted(files):z.write(p,arcname=ROOT.name+'/'+p.relative_to(ROOT).as_posix())
with zipfile.ZipFile(TARGET) as z:
    fail=z.testzip()
    if fail:raise RuntimeError(f'bad ZIP CRC: {fail}')
    assert len(z.namelist())==len(files)
print(TARGET,'file_count',len(files),'bytes',TARGET.stat().st_size)
