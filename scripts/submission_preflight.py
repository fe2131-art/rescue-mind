"""Audit actual submission artifacts. Does not upload to OmniCampus/YouTube.

Exit 0 only if video, public GitHub URL, YouTube URL and PDF have been supplied.
Requires ffprobe to validate video stream and duration.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


def inspect_submission(report: str, video: str, github: str, youtube: str,
                       account: str, ffprobe='ffprobe') -> dict:
    checks={}
    pdf=Path(report)
    checks['report_pdf_exists'] = pdf.is_file() and pdf.suffix.lower()=='.pdf' and pdf.stat().st_size>1000
    checks['report_filename'] = bool(account and pdf.name==f'説明資料_PAI最終課題_{account}.pdf')
    uri=urlsplit(github)
    checks['github_public_url_format'] = uri.scheme=='https' and uri.hostname=='github.com' and len([x for x in uri.path.split('/') if x])>=2
    # A URL syntactically valid here is NOT an independent verification of repository visibility.
    checks['github_public_verified'] = False
    y=urlsplit(youtube)
    checks['youtube_url_format'] = y.scheme=='https' and y.hostname in ('www.youtube.com','youtube.com','youtu.be') and bool(y.path.strip('/'))
    checks['youtube_visibility_verified'] = False
    v=Path(video)
    checks['video_exists'] = v.is_file() and v.suffix.lower()=='.mp4'
    video_info={}
    if checks['video_exists']:
        try:
            res=subprocess.run([ffprobe,'-v','error','-show_entries','format=duration','-of','json',str(v)],
                               capture_output=True,text=True,check=True,timeout=20)
            sec=float(json.loads(res.stdout)['format']['duration'])
            video_info={'duration_seconds':round(sec,3)}
            checks['video_duration_1_to_3_minutes'] = 60<=sec<=180
        except (OSError,ValueError,KeyError,subprocess.SubprocessError):
            checks['video_duration_1_to_3_minutes']=False
    else:
        checks['video_duration_1_to_3_minutes']=False
    checks['real_robot_recording_verified'] = False
    checks['personal_data_absent_verified'] = False
    checks['youtube_title_settings_verified'] = False
    return {'checks':checks,'video':video_info,
            'automatable_pass':all(checks[k] for k in ('report_pdf_exists','report_filename','github_public_url_format','youtube_url_format','video_exists','video_duration_1_to_3_minutes')),
            'submission_ready':False,
            'manual_checks_required':['GitHub repository public','YouTube visibility & title/settings','actual robot visible','privacy & secrets review', 'OmniCampus submission']}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--report',required=True);p.add_argument('--video',required=True)
    p.add_argument('--github',required=True);p.add_argument('--youtube',required=True);p.add_argument('--account',required=True)
    p.add_argument('--out',default='outputs/submission_preflight.json');a=p.parse_args()
    r=inspect_submission(a.report,a.video,a.github,a.youtube,a.account)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(r,ensure_ascii=False,indent=2))
    raise SystemExit(0 if r['automatable_pass'] else 2)

if __name__ == '__main__': main()
