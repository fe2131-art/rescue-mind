"""Lightweight secret/PII pattern preflight. A PASS is not a privacy guarantee."""
from __future__ import annotations
import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PRIVATE_NAMES={'.env','credentials.json','service-account.json','id_rsa'}
PATTERNS={'secret_key':re.compile(r'(?:jv_live_|sk-)[A-Za-z0-9_=-]{16,}'),
          'email_address':re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b')}
ALLOW_SUFFIXES={'.py','.md','.txt','.json','.yml','.yaml','.sh','.toml','.sdf','.srt','.csv'}

def audit():
    findings=[];scanned=0
    for p in ROOT.rglob('*'):
        if not p.is_file() or any(n in p.parts for n in ('__pycache__','.venv','.git')):continue
        relative=str(p.relative_to(ROOT))
        if p.name in PRIVATE_NAMES:findings.append({'path':relative,'issue':'private_filename'});continue
        if p.suffix not in ALLOW_SUFFIXES:continue
        scanned+=1
        text=p.read_text(encoding='utf-8',errors='ignore')
        for kind,pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append({'path':relative,'issue':kind})
    return {'status':'PASS' if not findings else 'FAIL','scanned_text_files':scanned,
            'findings':findings,'manual_privacy_and_screen_recording_review_still_required':True}

if __name__=='__main__':
    out=audit();print(json.dumps(out,ensure_ascii=False,indent=2))
    path=ROOT/'outputs/release/v09_public_release_audit.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2))
    if out['status']!='PASS':raise SystemExit(1)
