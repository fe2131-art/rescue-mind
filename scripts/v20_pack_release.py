#!/usr/bin/env python3
"""Pack source/doc/report with sha manifest; include mutable experiment outputs unpinned."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'RescueMind_v2.0_Jev_Qwen38_SimClock_Award_OfflineVerified.zip'
MANIFEST=ROOT/'SHA256_MANIFEST.json'
EXCLUDED={'.venv','__pycache__','.git','.pytest_cache','runs','.tox','egg-info'}
def included(p):
    rel=p.relative_to(ROOT)
    return (p!=MANIFEST and not any(t in EXCLUDED for t in rel.parts)
            and p.suffix not in ('.pyc','.pyo') and not p.name.startswith('.env'))
def all_files():
    return sorted((p for p in ROOT.rglob('*') if p.is_file() and included(p)),key=lambda p:p.relative_to(ROOT).as_posix())
def main():
    files=all_files()
    pinned={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files
            if p.relative_to(ROOT).parts[0] not in ('outputs','verification')}
    MANIFEST.write_text(json.dumps({
       'version':'v2.0.0', 'algorithm':'sha256','sha256':pinned,'files':pinned,
       'mutable_directories_not_pinned':['outputs','verification'],
       'reason':'verification reruns change timestamps/logs; contents remain included in ZIP',
       'integrity_scope':'file integrity, not live simulator/API validation'},indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    archive=files+[MANIFEST]
    with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as z:
        for f in sorted(archive):z.write(f,'rescuemind_v20/'+f.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(OUT) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(archive)
        for file,sha in pinned.items():
            assert hashlib.sha256(z.read('rescuemind_v20/'+file)).hexdigest()==sha
    report={'version':'2.0.0','archive':OUT.name,'size_bytes':OUT.stat().st_size,
           'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),
           'member_count':len(archive),'pinned_file_count':len(pinned),
           'zip_crc':'PASS','source_hashes':'PASS',
           'external_ros_gazebo':'UNTESTED','external_jev_qwen':'UNTESTED'}
    (ROOT.parent/'RescueMind_v2.0_RELEASE_CHECK.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
