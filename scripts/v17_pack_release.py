#!/usr/bin/env python3
"""Package the completed offline-verified v1.7 source tree reproducibly.

MUST run v17_verify.sh and v17_make_pdf.py first. No artifact is mislabelled as a
real ROS/Gazebo/AI run. Writes a release JSON next to ZIP, not inside release.
"""
from pathlib import Path
import hashlib,json,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'RescueMind_v1.7_Jev_Qwen38_ClosedLoop_Award_OfflineVerified.zip'
RESULT=ROOT.parent/'RescueMind_v1.7_RELEASE_CHECK.json'

def file_paths(root):
    return sorted((p for p in root.rglob('*') if p.is_file() and
                   not any(z in p.parts for z in ('.venv','__pycache__','.git','.pytest_cache')) and
                   p.suffix!='.pyc'), key=lambda x:x.as_posix())

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    report=json.loads((ROOT/'verification/v17/v17_TEST_REPORT.json').read_text())
    if not (report.get('unittest')=='PASS' and report.get('unittest_count',0)>=207
            and report.get('scripted_expected_outcomes_matched')==6
            and report.get('gazebo_ros_bridge_static_contract')=='PASS'):
        raise SystemExit('v1.7 verification report missing/incomplete')
    pdf=ROOT/'docs/RescueMind_v17_REPORT_DRAFT_NOT_SUBMISSION.pdf'
    if not pdf.exists() or pdf.stat().st_size<10000:raise SystemExit('report missing')
    if (ROOT/'outputs/release/v09_public_release_audit.json').is_file():
        privacy=json.loads((ROOT/'outputs/release/v09_public_release_audit.json').read_text())
        if privacy['status']!='PASS':raise SystemExit('privacy audit FAILED')
    # Manifest must be generated only after all in-tree build files are final.
    subprocess.run([sys.executable,str(ROOT/'scripts/integrity.py'),'--check'],check=True,cwd=ROOT)
    entries=file_paths(ROOT)
    with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in entries:z.write(p,arcname=str(Path('rescuemind_v17')/p.relative_to(ROOT)))
    with zipfile.ZipFile(OUT,'r') as z:
        bad=z.testzip()
        if bad:raise RuntimeError('bad ZIP CRC: '+bad)
        if len(z.namelist())!=len(entries):raise RuntimeError('incomplete ZIP')
        for path in entries:
            packed=z.read(str(Path('rescuemind_v17')/path.relative_to(ROOT)))
            if hashlib.sha256(packed).hexdigest()!=digest(path):
                raise RuntimeError('hash changed in ZIP: '+str(path))
    data={'version':'1.7.0','file_count':len(entries),'zip_size_bytes':OUT.stat().st_size,
          'zip_sha256':digest(OUT),'source_manifest_sha256_verification':'PASS',
          'zip_crc':'PASS','zip_entry_file_hashes':'PASS',
          'offline_python_tests':report['unittest_count'],
          'scripted_closed_loop_expected_results':6,
          'real_gazebo':'UNTESTED','real_jev':'UNTESTED','real_qwen':'UNTESTED',
          'submission_video':'NOT_CREATED'}
    RESULT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(data,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
