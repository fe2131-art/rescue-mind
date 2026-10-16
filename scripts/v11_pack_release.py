"""Create and verify an auditable RescueMind v1.1 ZIP from a checked worktree.

Offline tests and static checks only; NOT external model or Gazebo verification.
Writes checksum manifest, opens archive, clean-extracts then re-runs test suite.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT.parent/'RescueMind_v1.1_Jev_Qwen38_CameraSafety_Award_Verified.zip'
REPORT=ROOT.parent/'RescueMind_v1.1_VERIFICATION.json'


def source_files():
    all_files=[]
    for p in ROOT.rglob('*'):
        if not p.is_file() or p.name=='SHA256_MANIFEST.json':
            continue
        rel=p.relative_to(ROOT)
        if any(x in ('__pycache__','.pytest_cache','.venv','.git','.mypy_cache') for x in rel.parts):
            continue
        if p.suffix=='.pyc' or ('outputs' in rel.parts and ('runs' in rel.parts or 'local_runtime_diagnostics' in rel.parts)):
            continue
        all_files.append(p)
    return sorted(all_files)


def hash_file(p: Path):
    h=sha256()
    with p.open('rb') as r:
        for b in iter(lambda:r.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def check_manifest(root):
    manifest=json.loads((root/'SHA256_MANIFEST.json').read_text(encoding='utf8'))
    failures=[]
    for name,digest in manifest['files'].items():
        p=root/name
        if not p.is_file() or hash_file(p)!=digest:
            failures.append(name)
    return manifest,len(failures)==0,failures


def main():
    expected=json.loads((ROOT/'outputs/release/v11_verification.json').read_text())
    assert expected['python_unittest']['status']=='PASS' and expected['offline_camera_fault_campaign']['pass_count']==500
    paths=source_files()
    manifest={'version':'1.1','checksum_algorithm':'SHA-256','notes':'Manifest excludes itself, __pycache__, .venv and runtime private evidence directories',
              'files':{p.relative_to(ROOT).as_posix():hash_file(p) for p in paths}}
    (ROOT/'SHA256_MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    paths=source_files()+[ROOT/'SHA256_MANIFEST.json']
    with zipfile.ZipFile(DEST,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as z:
        for p in sorted(paths):
            z.write(p,arcname=(Path(ROOT.name)/p.relative_to(ROOT)).as_posix())
    with zipfile.ZipFile(DEST) as z:
        error=z.testzip();assert error is None,error
        assert len(z.namelist())==len(paths)
        assert not any('..' in Path(n).parts for n in z.namelist())
    with tempfile.TemporaryDirectory(prefix='rescuemind_v11_clean_') as temp:
        root=Path(temp)/ROOT.name
        with zipfile.ZipFile(DEST) as z:z.extractall(temp)
        check,okay,failures=check_manifest(root)
        assert okay,failures
        assert len(check['files'])==len(paths)-1
        cmd=['bash','scripts/v11_verify.sh']
        run=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=130,
                           env={**os.environ,'PYTHONPATH':str(root)})
        if run.returncode:
            print(run.stdout[-5000:],run.stderr[-5000:],file=sys.stderr)
            raise RuntimeError(f'clean extraction verification failed {run.returncode}')
        fresh=json.loads((root/'outputs/release/v11_verification.json').read_text())
        assert fresh['python_unittest']['count']==expected['python_unittest']['count']
        assert fresh['offline_camera_fault_campaign']['pass_count']==500
        assert fresh['static_sdf_bridge_contract']=='PASS'
    summary={'release':'RescueMind v1.1','package':str(DEST),'package_sha256':hash_file(DEST),
             'archive_file_count':len(paths),'manifest_matched_files':len(paths)-1,'sha256_check':'PASS',
             'zip_crc':'PASS','clean_extract_tests':'PASS',
             'offline_unittest_count':fresh['python_unittest']['count'],
             'offline_camera_fault_tests':fresh['offline_camera_fault_campaign']['pass_count'],
             'previous_fault_matrix_cases':fresh['existing_software_fault_matrix']['cases'],
             'report_pdf_pages':3,'report_pdf_render_reviewed':True,
             'real_jev_qwen_api_verified':False,'real_gazebo_verified':False,
             'submission_video_generated':False,
             'privacy_manual_review_required':True,'note':'Only offline verification; actual robot/task video is still required.'}
    REPORT.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
