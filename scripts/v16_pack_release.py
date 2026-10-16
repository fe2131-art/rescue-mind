#!/usr/bin/env python3
"""Create integrity-manifested source archive with immutable verification snapshot."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'RescueMind_v1.6_Jev_Qwen38_Award_Research_OfflineVerified.zip'
def included(path):
    rel=path.relative_to(ROOT)
    if path.name=='SHA256_MANIFEST.json':return False
    if any(x in rel.parts for x in ('.venv','__pycache__','.pytest_cache','.git','egg-info','runs')):return False
    if path.suffix in ('.pyc','.pyo'):return False
    return True

def files():
    return sorted((p for p in ROOT.rglob('*') if p.is_file() and included(p)),key=lambda p:str(p.relative_to(ROOT)))
def main():
    rows={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files()
          if p.relative_to(ROOT).parts[0]!='outputs'}  # rerunnable outputs are mutable
    manifest={'version':'v1.6','hash_algorithm':'SHA-256','files':rows,
              'excluded_from_manifest':'generated outputs/ may change when verification reruns',
              'scope':'source files + docs + verification snapshot; not proof of external API or Gazebo'}
    (ROOT/'SHA256_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    all_files=files()+[ROOT/'SHA256_MANIFEST.json']
    with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as z:
        for p in sorted(all_files):z.write(p,'rescuemind_v16/'+str(p.relative_to(ROOT)))
    with zipfile.ZipFile(OUT) as z:
        corrupt=z.testzip();assert corrupt is None,corrupt
        assert len(z.namelist())==len(all_files)
    result={'version':'v1.6','archive':str(OUT),'archive_bytes':OUT.stat().st_size,
            'archive_sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),
            'zip_members':len(all_files),'sha256_tracked_immutable_files':len(rows),
            'zip_crc_pass':True,'runtime_Gazebo_verified':False,'real_Jev_Qwen_verified':False}
    (ROOT.parent/'RescueMind_v1.6_RELEASE_CHECK.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
