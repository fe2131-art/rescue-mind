#!/usr/bin/env python3
"""Pack reproducible v1.8 source and records; CRC, SHA256, checked manifest."""
from __future__ import annotations
import hashlib,json,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'RescueMind_v1.8_Jev_required_Qwen38_IndependentMotion_Evidence_OfflineVerified.zip'
SUMMARY=ROOT.parent/'RescueMind_v1.8_RELEASE_CHECK.json'
EXCLUDE={'.venv','__pycache__','.git','.pytest_cache'}

def paths():
    return sorted((p for p in ROOT.rglob('*') if p.is_file() and
                   not any(x in EXCLUDE for x in p.parts) and p.suffix!='.pyc'),
                  key=lambda p:p.relative_to(ROOT).as_posix())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    test=json.loads((ROOT/'verification/v18/v18_TEST_REPORT.json').read_text())
    if not(test.get('python_tests_passed',0)>=219 and
           test.get('synthetic_motion_expected_results_matched')==6 and
           test.get('scripted_closed_loop_expected_results_matched')==6):
        raise SystemExit('Missing verified v18 experiment results')
    pdf=ROOT/'docs/RescueMind_v18_REPORT_DRAFT_NOT_SUBMISSION.pdf'
    if pdf.stat().st_size<20000:raise SystemExit('PDF missing')
    subprocess.run([sys.executable,str(ROOT/'scripts/integrity.py'),'--check'],check=True,cwd=ROOT)
    sources=paths(); ts=(2026,10,16,0,0,0)
    with zipfile.ZipFile(OUT,'w') as z:
        for p in sources:
            name=(Path('rescuemind_v18')/p.relative_to(ROOT)).as_posix()
            info=zipfile.ZipInfo(name,date_time=ts)
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o100644<<16)
            z.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(OUT) as z:
        bad=z.testzip()
        if bad:raise SystemExit('ZIP CRC failure '+bad)
        if len(z.namelist())!=len(sources):raise SystemExit('ZIP missing/extra entries')
        for p in sources:
            if hashlib.sha256(z.read((Path('rescuemind_v18')/p.relative_to(ROOT)).as_posix())).hexdigest()!=sha(p):
                raise SystemExit('ZIP entry SHA-256 mismatch '+str(p))
    result={'version':'1.8.0','source_files':len(sources),'bytes':OUT.stat().st_size,
            'zip_sha256':sha(OUT),'sha256_manifest':'PASS','zip_crc':'PASS',
            'zip_entry_hashes':'PASS','python_tests':test['python_tests_passed'],
            'synthetic_motion_cases':6,'scripted_closed_loop_cases':6,
            'real_Jev':'UNTESTED','real_Qwen':'UNTESTED','Gazebo':'UNTESTED',
            'actual_robot_video':'NOT_CREATED',
            'disclaimer':'Offline verified; real ROS/Gazebo and remote model execution not run'}
    SUMMARY.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
