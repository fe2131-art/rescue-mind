"""Package verified project; ZIP CRC, manifest, and tests from clean extraction.

No claim of real model/Gazebo runtime verification is made.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
import sys

ROOT=Path(__file__).resolve().parents[1]
ZIP=ROOT.parent/'RescueMind_v1.2_Jev_Qwen38_IndependentGuard_Award_OfflineVerified.zip'
SUM=ROOT.parent/'RescueMind_v1.2_VERIFICATION_SUMMARY.json'

def files():
    names=[]
    for p in ROOT.rglob('*'):
        if not p.is_file() or p.name=='SHA256_MANIFEST.json':continue
        r=p.relative_to(ROOT)
        if any(k in ('__pycache__','.pytest_cache','.venv','.git','.mypy_cache','runs','local_runtime_diagnostics') for k in r.parts):continue
        if p.suffix in ('.pyc','.pyo'):continue
        names.append(p)
    return sorted(names)

def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<19),b''):h.update(b)
    return h.hexdigest()

def main():
    run_info=json.loads((ROOT/'outputs/release/v12_verification.json').read_text())
    assert run_info['python_test_status']=='PASS' and run_info['velocity_relay_fault_pass']==1125
    src=files()
    man={'release':'1.2','algorithm':'sha256','exclude':['SHA256_MANIFEST.json','__pycache__','.venv','runtime evidence'],
         'files':{p.relative_to(ROOT).as_posix():sha256(p) for p in src}}
    (ROOT/'SHA256_MANIFEST.json').write_text(json.dumps(man,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    arc=src+[ROOT/'SHA256_MANIFEST.json']
    with zipfile.ZipFile(ZIP,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as z:
        for p in sorted(arc):z.write(p,arcname=(Path(ROOT.name)/p.relative_to(ROOT)).as_posix())
    with zipfile.ZipFile(ZIP) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(arc)
        assert not any('..' in Path(n).parts for n in z.namelist())
    with tempfile.TemporaryDirectory(prefix='rescuemind_v12_ziptest_') as temp:
        with zipfile.ZipFile(ZIP) as z:z.extractall(temp)
        project=Path(temp)/ROOT.name
        read=json.loads((project/'SHA256_MANIFEST.json').read_text())
        for name,digest in read['files'].items():
            assert sha256(project/name)==digest,name
        env={**os.environ,'PYTHONPATH':str(project)}
        run=subprocess.run(['bash','scripts/v12_verify.sh'],cwd=project,capture_output=True,text=True,timeout=160,env=env)
        if run.returncode:
            print(run.stdout[-4000:],run.stderr[-4000:],file=sys.stderr)
            raise RuntimeError(f'Clean re-run failed {run.returncode}')
        fresh=json.loads((project/'outputs/release/v12_verification.json').read_text())
        assert fresh['python_tests']==run_info['python_tests'] and fresh['velocity_relay_fault_pass']==1125
    report={'release':'RescueMind v1.2','zip':ZIP.name,'zip_sha256':sha256(ZIP),
            'zip_crc':'PASS','archive_entries':len(arc),'manifest_file_matches':len(src),
            'clean_extraction':'PASS','clean_extraction_test_count':fresh['python_tests'],
            'software_velocity_fault_cases':1125,'software_camera_fault_cases':500,
            'legacy_software_gate_cases':972,'pdf_pages':3,
            'real_jev_api':'NOT_TESTED','real_qwen_api':'NOT_TESTED','real_gazebo':'NOT_TESTED',
            'submission_video':'NOT_CREATED',
            'limitations':"Simulator-only; real ROS2/Gazebo and API validation remains for the Ubuntu host."}
    SUM.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
