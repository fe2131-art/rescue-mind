#!/usr/bin/env python3
"""Write the two measured facts of docs/SUBMISSION.md from the actual files (no hand-typed values):
  * the video length / size / codecs from `ffprobe` on outputs/video/PAI最終課題_tetsutetsu.mp4 (git-ignored file),
  * the explanation PDF's main-part and appendix page counts from the PDF text (the appendix starts on the page that carries the
    heading "付録（詳細・証明・過去の評価・失敗の一覧）").
The values sit between <!--FACT:video-->...<!--/FACT:video--> and <!--FACT:report-->...<!--/FACT:report--> in docs/SUBMISSION.md.
Run after the last video render and the last report build:  nice -n 19 python3 scripts/update_submission_facts.py
Keep the CPU low: ffprobe only reads the header; pdftotext runs in the LaTeX image with one CPU.
"""
from __future__ import annotations
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO = Path('/home/tetsutani/work/rescue-mind/outputs/video/PAI最終課題_tetsutetsu.mp4')
if not VIDEO.is_file():
    VIDEO = ROOT / 'outputs/video/PAI最終課題_tetsutetsu.mp4'
PDF = ROOT / 'docs/report/説明資料_PAI最終課題_tetsutetsu.pdf'
SUB = ROOT / 'docs/SUBMISSION.md'
CHAP = ROOT / 'docs/video_chapters.json'
LATEX_IMG = 'rescuemind:latex'
APPENDIX_HEADING = '付録（詳細・証明・過去の評価・失敗の一覧）'


def video_fact():
    if not VIDEO.is_file():
        return None
    r = subprocess.run(['nice', '-n', '19', 'ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,codec_name,width,height',
                        '-of', 'json', str(VIDEO)], capture_output=True, text=True, check=True)
    j = json.loads(r.stdout)
    d = float(j['format']['duration'])
    v = next(s for s in j['streams'] if s['codec_type'] == 'video')
    a = next((s for s in j['streams'] if s['codec_type'] == 'audio'), None)
    txt = f"{d:.1f}秒（{int(d // 60)}分{int(round(d % 60)):02d}秒、`ffprobe` による実測）。{v['width']}×{v['height']}、{v['codec_name'].upper()}/{a['codec_name'].upper() if a else '音声なし'}"
    if CHAP.is_file():
        end = json.loads(CHAP.read_text(encoding='utf8'))[-1]['end_s']
        txt += f"。`docs/video_chapters.json` の終端は {end:.1f}秒" + ('（実測と一致）' if abs(end - d) < 0.5 else '（実測と**一致しない**：動画か章立てを再生成する）')
    return txt


def report_fact():
    if not PDF.is_file():
        return None
    cmd = ['nice', '-n', '19', 'docker', 'run', '--rm', '--cpus=1', '-v', f'{PDF.parent}:/w:ro', LATEX_IMG, 'bash', '-c',
           f'n=$(pdfinfo "/w/{PDF.name}" | sed -n "s/^Pages: *//p"); echo PAGES $n; for i in $(seq 1 $n); do echo "=== PAGE $i"; pdftotext -f $i -l $i "/w/{PDF.name}" -; done']
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    total = int(re.search(r'^PAGES (\d+)', out, re.M).group(1))
    pages = re.split(r'(?:^|\f)=== PAGE (\d+)\n', out, flags=re.M)[1:]
    start = next((int(pages[i]) for i in range(0, len(pages), 2) if re.search(r'^' + re.escape(APPENDIX_HEADING), pages[i + 1], re.M)), None)
    if start is None:
        return f"全{total}ページ（付録の見出しがページ内で見つからない）"
    return f"本文{start - 1}ページ＋付録{total - start + 1}ページ（全{total}ページ。付録は{start}ページから、`pdfinfo` と本文抽出による実測）"


def main():
    s = SUB.read_text(encoding='utf8')
    for name, fn in (('video', video_fact), ('report', report_fact)):
        t = fn()
        if t is None:
            print(f'{name}: file missing, left as is')
            continue
        s, n = re.subn(rf'(<!--FACT:{name}-->).*?(<!--/FACT:{name}-->)', lambda m: m.group(1) + t + m.group(2), s, flags=re.S)
        assert n == 1, f'marker {name} not found in docs/SUBMISSION.md'
        print(f'{name}: {t}')
    SUB.write_text(s, encoding='utf8')


if __name__ == '__main__':
    main()
