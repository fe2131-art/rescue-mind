#!/usr/bin/env python3
"""Package release after off-line verification; check ZIP CRC, hashes and names."""
from __future__ import annotations
import hashlib,json,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'RescueMind_v1.9_Jev_Qwen38_Causal_Chronology_ROSBag_OfflineVerified.zip'
SUMMARY=ROOT.parent/'RescueMind_v1.9_RELEASE_CHECK.json'
EXCLUDE={'.venv','__pycache__','.pytest_cache','.git','runs','build','dist'}

def entries():
    return sorted((p for p in ROOT.rglob('*') if p.is_file() and
                   not any(e in p.relative_to(ROOT).parts for e in EXCLUDE) and
                   p.suffix not in ('.pyc','.pyo') and p.name not in ('.env','credentials.json')),
                  key=lambda p:p.relative_to(ROOT).as_posix())

def sha_bytes(data):return hashlib.sha256(data).hexdigest()
def main():
    report=json.loads((ROOT/'verification/v19/v19_TEST_REPORT.json').read_text())
    campaign=json.loads((ROOT/'verification/v19/v19_synthetic_chronology_campaign.json').read_text())
    if report['python_unittest_passed']<232 or campaign['matched']!=10:
        raise SystemExit('Offline verification gates not met')
    pdf=ROOT/'docs/RescueMind_v19_REPORT_DRAFT_NOT_SUBMISSION.pdf'
    if not pdf.is_file() or pdf.stat().st_size <20000:
        raise SystemExit('PDF missing or unexpectedly short')
    subprocess.run([sys.executable,str(ROOT/'scripts/integrity.py'),'--check'],check=True,cwd=ROOT)
    files=entries()
    with zipfile.ZipFile(OUT,'w') as z:
        for p in files:
            arc=(Path('rescuemind_v19')/p.relative_to(ROOT)).as_posix()
            info=zipfile.ZipInfo(arc,date_time=(2026,10,16,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o100644<<16)
            z.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(OUT) as z:
        if z.testzip() is not None:raise SystemExit('ZIP CRC FAILED')
        if len(z.namelist())!=len(files) or len(set(z.namelist()))!=len(files):
            raise SystemExit('ZIP count/duplicate mismatch')
        for p in files:
            rel=(Path('rescuemind_v19')/p.relative_to(ROOT)).as_posix()
            if sha_bytes(z.read(rel))!=sha_bytes(p.read_bytes()):
                raise SystemExit('ZIP SHA failed '+rel)
    summary={'version':'1.9.0','archive_bytes':OUT.stat().st_size,
             'zip_members':len(files),'zip_sha256':sha_bytes(OUT.read_bytes()),
             'zip_crc':'PASS','zip_member_sha256':'PASS',
             'source_manifest':'PASS','python_unittests':report['python_unittest_passed'],
             'synthetic_causal_timeline_cases':campaign['total'],
             'synthetic_causal_timeline_expected_matched':campaign['matched'],
             'real_gazebo':'UNTESTED','real_Jev':'UNTESTED','real_Qwen':'UNTESTED',
             'robot_submission_video':'NOT_CREATED',
             'caution':'Offline tests only; metadata is not evidence of authenticated physics.'}
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
