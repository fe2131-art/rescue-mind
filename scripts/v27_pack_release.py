#!/usr/bin/env python3
"""Build deterministic-ish sanitized offline release ZIP, with sha256 manifest.

The zip includes production code, tests, documents, previous provenance and
current offline evidence. Dynamic run folders, caches, credentials excluded.
"""
from __future__ import annotations
import hashlib,json,os,re,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT.parent/'RescueMind_v2.7_Jev_Qwen38_TwoFrame_QualityGate_Award_OfflineVerified.zip'
MANIFEST=ROOT/'release/v27_SHA256_MANIFEST.json'

EXCLUDE_DIR={'.git','.venv','__pycache__','.pytest_cache','.mypy_cache','node_modules','egg-info','dist','build'}
EXCLUDE_SUFFIX={'.pyc','.pyo','.swp','.tmp','.bak','.lock'}

def paths():
    for p in ROOT.rglob('*'):
        if not p.is_file() or p.is_symlink():continue
        rel=p.relative_to(ROOT)
        if any(part in EXCLUDE_DIR or part.endswith('.egg-info') for part in rel.parts):continue
        if rel.parts[:2] == ('outputs','runs'):continue
        if p.suffix in EXCLUDE_SUFFIX:continue
        if p==MANIFEST:continue
        # Only package source and deterministic verification artifacts.
        if any(str(part).startswith('.') and part not in ('.gitignore',) for part in rel.parts):continue
        yield p

def scan(path_list):
    # Best effort heuristic; text fixtures may contain benign phrases.
    email=re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b')
    likely_api=re.compile(r'(?i)(?:api_key|token|password|secret)\s*[=:]\s*[\'\"](?:sk-[A-Za-z0-9]{15,}|[A-Za-z0-9_\-]{32,})[\'\"]')
    issues=[];scanned=0
    for p in path_list:
        if p.suffix.lower() not in ('.py','.md','.json','.txt','.sh','.yaml','.yml','.toml','.csv','.sdf'):continue
        try:s=p.read_text(encoding='utf8')
        except UnicodeDecodeError:continue
        scanned+=1
        if email.search(s) or likely_api.search(s):
            issues.append(p.relative_to(ROOT).as_posix())
    return {'scope':'regex_only_not_credential_forensics','text_files_scanned':scanned,
            'files_with_possible_sensitive_patterns':issues,'manual_review_required':True}

def run():
    files=sorted(paths(),key=lambda p:p.relative_to(ROOT).as_posix())
    privacy=scan(files)
    REPORT=ROOT/'release/v27_PRIVACY_SCAN.json'
    REPORT.parent.mkdir(exist_ok=True,parents=True)
    REPORT.write_text(json.dumps(privacy,ensure_ascii=False,indent=2)+'\n')
    if privacy['files_with_possible_sensitive_patterns']:
        raise SystemExit('Possible sensitive patterns: '+str(privacy['files_with_possible_sensitive_patterns']))
    files=sorted(paths(),key=lambda p:p.relative_to(ROOT).as_posix())
    entries={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    manifest={'release':'2.7.0','root_name':ROOT.name,'sha256':entries,
              'note':'Dynamic verification logs may change after rerunning tests; compare source files unchanged.'}
    MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    files=sorted([*files,MANIFEST],key=lambda p:p.relative_to(ROOT).as_posix())
    ARCHIVE.unlink(missing_ok=True)
    with zipfile.ZipFile(ARCHIVE,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as z:
        for p in files:
            arc=ROOT.name+'/'+p.relative_to(ROOT).as_posix()
            info=zipfile.ZipInfo(arc,date_time=(2026,10,16,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o644<<16)
            z.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=8)
    with zipfile.ZipFile(ARCHIVE) as z:
        bad=z.testzip();assert bad is None,bad
        assert len(z.namelist())==len(files)
    report={'release':'2.7.0','archive':ARCHIVE.name,'zip_sha256':hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
            'zip_bytes':ARCHIVE.stat().st_size,'zip_files':len(files),'manifest_entries':len(entries),
            'crc':'PASS','privacy_scan':privacy,'verification':json.loads((ROOT/'verification/v27/verification.json').read_text())}
    out=ROOT.parent/'RescueMind_v2.7_RELEASE_CHECK.json'
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':run()
