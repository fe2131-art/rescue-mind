"""Package *existing* Ubuntu runtime evidence; never manufacture Gazebo success.

Requires a 60-180 s MP4, a ROS mission JSON passing the audit, and the exact
camera frame whose digest is recorded in the mission event. Checks never imply
external provenance or actual Gazebo authenticity: manual verification required.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.audit_robot_run import audit


def sha256(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):
            digest.update(block)
    return digest.hexdigest()


def video_probe(path: Path, probe='ffprobe', runner=subprocess.run) -> dict:
    proc=runner([probe,'-v','error','-show_entries','format=duration:stream=codec_type,codec_name',
                 '-of','json',str(path)],check=True,capture_output=True,text=True,timeout=30)
    obj=json.loads(proc.stdout)
    duration=float(obj['format']['duration'])
    codecs=[s.get('codec_name','') for s in obj.get('streams',[]) if s.get('codec_type')=='video']
    return {'duration_seconds':duration,'video_codecs':codecs,
            'passes_format':60<=duration<=180 and bool(codecs)}


def validate_bundle(log: Path, video: Path, frame: Path, *, probe='ffprobe') -> dict:
    for f in (log,video,frame):
        if not f.is_file() or f.stat().st_size==0:
            raise ValueError(f'missing/empty evidence: {f.name}')
    proof=audit(log)
    record=json.loads(log.read_text(encoding='utf-8'))
    events=[x for x in record.get('events',[]) if x.get('stage')=='checkpoint_frame']
    if len(events)!=1:
        raise ValueError('expected exactly one checkpoint frame event')
    h=sha256(frame)
    # Stronger than JSON-only audit: examine actual image bytes.
    if h!=events[0].get('image_sha256') or h!=(record.get('checkpoint') or {}).get('image_sha256'):
        raise ValueError('frame bytes do not match mission log')
    if record.get('version') in ('1.0','1.1','1.6'):
        stamp=events[0].get('ros_acquisition_stamp_ns')
        if not isinstance(stamp,int) or stamp<=0:
            raise ValueError('missing positive on-site ROS acquisition timestamp')
    # v1.1 defaults to unique run directories. Require an explicit link to the supplied frame.
    if record.get('version') in ('1.1','1.6'):
        run_id=record.get('run_id','')
        if not isinstance(run_id,str) or len(run_id)!=16 or not all(ch in '0123456789abcdef' for ch in run_id):
            raise ValueError('missing or invalid v1.1 run_id')
        recorded_path=record.get('checkpoint_image_path','')
        if Path(recorded_path).name!=frame.name:
            raise ValueError('supplied frame does not match checkpoint_image_path')
    video_meta=video_probe(video,probe)
    return {'audit_pass':proof['automated_pass'], 'image_sha256_verified':True,
            'video':video_meta, 'can_package':bool(proof['automated_pass'] and video_meta['passes_format']),
            'independent_gazebo_authenticity_verified':False,
            'independent_jev_api_provenance_verified':False,
            'manual_review_required':['Confirm on-screen actual Gazebo simulation, no cuts misrepresenting behavior',
                                      'Review API logs and actual network inference',
                                      'Review desktop recording for personal information',
                                      'Confirm published GitHub and YouTube visibility']}


def create_bundle(log: Path,video: Path,frame: Path,out: Path,*,probe='ffprobe') -> dict:
    checks=validate_bundle(log,video,frame,probe=probe)
    if not checks['can_package']:
        raise ValueError('evidence preflight failed; refusing to assemble bundle')
    if len({x.resolve() for x in (log,video,frame,out)})<4:
        raise ValueError('output and input paths must be distinct')
    out.parent.mkdir(parents=True,exist_ok=True)
    manifest={'version':'1.0','created_utc':datetime.now(timezone.utc).isoformat(),
              'checks':checks,'files':{f.name:{'sha256':sha256(f),'size':f.stat().st_size}
                                        for f in (log,video,frame)}}
    if len(manifest['files'])!=3:
        raise ValueError('all input filenames must be distinct')
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for f in (log,video,frame): archive.write(f,f.name)
        archive.writestr('EVIDENCE_MANIFEST.json',json.dumps(manifest,indent=2,ensure_ascii=False))
    return manifest


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--record',type=Path,required=True);ap.add_argument('--video',type=Path,required=True)
    ap.add_argument('--frame',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    info=create_bundle(a.record,a.video,a.frame,a.out)
    print(json.dumps(info,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
