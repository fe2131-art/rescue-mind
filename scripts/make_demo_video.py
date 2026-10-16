#!/usr/bin/env python3
"""Compose the submission video from REAL Gazebo run recordings (no mock footage).

Every pixel of the 3-D view comes from Gazebo-rendered cameras recorded during an
orchestrated run (`v32_orchestrate.py --film`): the static overview camera and the
robot's own /camera.  Overlays are computed from the run's own logs:
  * trajectory  = Gazebo ground-truth pose (independent_ros_topics.jsonl),
    projected through the overview camera's pinhole model (pose + HFOV from its SDF);
  * AI panel    = the checkpoint record in mission.json (model, per-pass
    probabilities, decision, latency);
  * speed badge = playback speed of the current segment (×1 at the checkpoint,
    faster while driving), always shown on screen as the assignment requires.

Usage (inside docker/run.sh so fonts/ffmpeg/OpenCV are present):
  python3 scripts/make_demo_video.py --plan docs/video_plan.json --out outputs/video/RescueMind_demo.mp4
"""
from __future__ import annotations
import argparse
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H, FPS = 1920, 1080, 30
FONT_R = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
FONT_B = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
BG = (13, 20, 33)
PANEL = (24, 34, 52)
INK = (236, 241, 248)
MUTED = (150, 165, 186)
ACCENT = (255, 140, 30)
GOOD = (60, 200, 120)
BAD = (240, 80, 80)
WATER = (80, 170, 255)
MED = (240, 90, 100)
OTHER = (160, 160, 170)

_font_cache: dict = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(FONT_B if bold else FONT_R, size)
    return _font_cache[key]


# ---------------------------------------------------------------- projection
class FilmCamera:
    """Pinhole model of worlds/film/film_camera_overview.sdf (Gazebo camera frame: x fwd, y left, z up)."""

    def __init__(self, sdf: Path, out_w: int, out_h: int):
        root = ET.parse(sdf).getroot()
        model = root.find('model')
        x, y, z, _r, p, yaw = [float(v) for v in model.findtext('pose').split()]
        cam = root.find('.//camera')
        hfov = float(cam.findtext('horizontal_fov'))
        iw = int(cam.findtext('image/width'))
        ih = int(cam.findtext('image/height'))
        self.c = np.array([x, y, z])
        cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(p), math.sin(p)
        rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
        ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
        self.R = rz @ ry
        self.f = (iw / 2) / math.tan(hfov / 2)
        self.cx, self.cy = iw / 2, ih / 2
        self.sx, self.sy = out_w / iw, out_h / ih

    def project(self, pt):
        pc = self.R.T @ (np.asarray(pt, float) - self.c)
        if pc[0] <= 0.05:
            return None
        u = self.cx - self.f * pc[1] / pc[0]
        v = self.cy - self.f * pc[2] / pc[0]
        return (u * self.sx, v * self.sy)


# ---------------------------------------------------------------- run data
def frames_in(folder: Path):
    rows = []
    for f in sorted(folder.glob('*.jpg')):
        unix_ns = int(f.stem.split('_')[0])
        rows.append((unix_ns, f))
    rows.sort()
    return rows


def load_run(run_dir: Path):
    mission = json.loads((run_dir / 'mission.json').read_text(encoding='utf8'))
    result = json.loads((run_dir / 'stack_result.json').read_text(encoding='utf8'))
    start = mission['mission_start_unix_ns']
    events = {}
    for e in mission['events']:
        if isinstance(e.get('t_wall_s'), (int, float)):
            events.setdefault(e['stage'], start + int(e['t_wall_s'] * 1e9))
    truth = []
    for line in (run_dir / 'independent_ros_topics.jsonl').read_text(encoding='utf8').splitlines():
        r = json.loads(line)
        if r.get('kind') == 'ground_truth':
            truth.append((r['wall_unix_ns'], r['x'], r['y']))
    return {'mission': mission, 'result': result, 'events': events, 'truth': truth,
            'film': frames_in(run_dir / 'film' / 'film'), 'robot': frames_in(run_dir / 'film' / 'robot')}


def nearest(rows, t):
    lo, hi = 0, len(rows) - 1
    if t <= rows[0][0]:
        return rows[0][1]
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if rows[mid][0] <= t:
            lo = mid
        else:
            hi = mid - 1
    return rows[lo][1]


# ---------------------------------------------------------------- drawing helpers
def rounded(draw, box, fill, r=18, outline=None, width=2):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def text(draw, xy, s, size, fill=INK, bold=False, anchor='la'):
    draw.text(xy, s, font=font(size, bold), fill=fill, anchor=anchor)


def wrap_lines(s, size, width_px, bold=False):
    f = font(size, bold)
    lines, cur = [], ''
    for ch in s:
        if ch == '\n':
            lines.append(cur); cur = ''; continue
        if f.getlength(cur + ch) > width_px:
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def prob_bar(draw, x, y, w, label, p, color):
    text(draw, (x, y), label, 22, MUTED)
    bx = x + 120
    draw.rounded_rectangle((bx, y + 4, bx + w, y + 26), radius=6, fill=(40, 52, 74))
    draw.rounded_rectangle((bx, y + 4, bx + max(6, int(w * p)), y + 26), radius=6, fill=color)
    text(draw, (bx + w + 12, y), f'{p:.2f}', 22, INK)


ITEM_JA = {'water': '飲料水', 'medicine': '医療物資', 'other': 'なし/不明'}
SCENE_JA = {'nominal': '正常配置', 'swapped': '物資の取り違え', 'empty': '欠品（棚が空）'}


# ---------------------------------------------------------------- mission segment
def mission_segment(run_dir: Path, spec: dict, cam: FilmCamera, emit):
    run = load_run(run_dir)
    ev, mission = run['events'], run['mission']
    cp = mission.get('checkpoint') or {}
    decision = cp.get('decision') or {}
    calls = cp.get('model_calls') or {}
    t0 = run['film'][0][0] + int(spec.get('skip_s', 0.5) * 1e9)
    t_station = ev.get('supply_station')
    t_frame = ev.get('checkpoint_frame')
    t_decision = ev.get('checkpoint_decision')
    t_end_motion = ev.get('shelter_approach') or ev.get('checkpoint_denial_dwell_finished') or run['film'][-1][0]
    t1 = min(run['film'][-1][0], t_end_motion + int(spec.get('tail_s', 2.0) * 1e9))
    fast = spec.get('fast', 3.0)
    # (source_start, source_end, speed)
    plan = []
    if t_station and t_decision:
        a = t_station - int(1.0e9)
        b = t_decision + int(2.5e9)
        plan = [(t0, a, fast), (a, b, 1.0), (b, t1, fast if 'shelter_approach' in ev else 1.0)]
    else:
        plan = [(t0, t1, fast)]
    item = mission['intent']['item']
    allow = decision.get('allow')
    route_pts = [(0.0, 0.0)] + [tuple(r[2]) for r in mission['route']]
    labels = [((2.0, 2.0, 1.05), '物資拠点 W', WATER), ((-2.0, 2.0, 1.05), '物資拠点 M', MED),
              ((3.0, -2.0, 0.95), '避難所 B', GOOD)]
    instr = mission['instruction']

    for (sa, sb, speed) in plan:
        if sb <= sa:
            continue
        n = max(1, int((sb - sa) / 1e9 / speed * FPS))
        for i in range(n):
            t = sa + int(i * speed * 1e9 / FPS)
            img = Image.new('RGB', (W, H), BG)
            d = ImageDraw.Draw(img, 'RGBA')
            # header
            text(d, (40, 26), 'RescueMind', 40, ACCENT, True)
            text(d, (318, 36), f'デモ {spec["index"]}/3 ｜ シーン：{SCENE_JA[spec["scene"]]}', 28, INK, True)
            rounded(d, (1150, 20, 1880, 84), PANEL, 16)
            text(d, (1172, 34), f'指示：「{instr}」', 28, INK, True)
            # main view
            main = Image.open(nearest(run['film'], t)).convert('RGB').resize((1280, 720), Image.BILINEAR)
            md = ImageDraw.Draw(main, 'RGBA')
            pts = [cam.project((x, y, 0.02)) for (tt, x, y) in run['truth'] if tt <= t]
            pts = [p for p in pts if p]
            plan_px = [cam.project((x, y, 0.01)) for x, y in route_pts]
            plan_px = [p for p in plan_px if p]
            if len(plan_px) > 1:
                for p, q in zip(plan_px, plan_px[1:]):
                    md.line([p, q], fill=(255, 255, 255, 110), width=3)
            if len(pts) > 1:
                md.line(pts, fill=(255, 140, 30, 235), width=6, joint='curve')
            for pos, lab, col in labels:
                p = cam.project(pos)
                if p:
                    w_ = font(24, True).getlength(lab) + 24
                    md.rounded_rectangle((p[0] - w_ / 2, p[1] - 44, p[0] + w_ / 2, p[1] - 8), radius=10,
                                         fill=(15, 22, 35, 210), outline=col + (255,), width=2)
                    md.text((p[0], p[1] - 26), lab, font=font(24, True), fill=INK, anchor='mm')
            img.paste(main, (40, 104))
            d.rectangle((40, 104, 1320, 824), outline=(60, 75, 100), width=2)
            # speed badge
            badge = '等速 ×1' if speed == 1.0 else f'{speed:g}倍速'
            rounded(d, (60, 124, 60 + 30 + font(28, True).getlength(badge), 172),
                    (255, 140, 30, 230) if speed != 1.0 else (60, 200, 120, 230), 12)
            text(d, (75, 128), badge, 28, (10, 10, 10), True)
            wm = 'Gazebo Harmonic 実レンダリング（俯瞰カメラ）'
            wl = font(20).getlength(wm)
            d.rounded_rectangle((60, 772, 84 + wl, 806), radius=8, fill=(15, 22, 35, 190))
            text(d, (72, 777), wm, 20, (220, 228, 240))
            # robot camera
            rcam = Image.open(nearest(run['robot'], t)).convert('RGB').resize((540, 405), Image.BILINEAR)
            img.paste(rcam, (1340, 130))
            text(d, (1340, 100), 'ロボット搭載カメラ  /camera', 22, MUTED, True)
            d.rectangle((1340, 130, 1880, 535), outline=(60, 75, 100), width=2)
            # AI panel
            rounded(d, (1340, 552, 1880, 1048), PANEL, 18)
            text(d, (1362, 566), 'AI 判断パネル', 28, ACCENT, True)
            text(d, (1362, 610), f'① 指示理解 → 物資：{ITEM_JA[item]} / 行先：避難所B', 22, INK)
            phase2 = '② 物資拠点へ移動' + (' ✓' if t_station and t >= t_station else ' …')
            text(d, (1362, 644), phase2, 22, INK)
            if t_frame and t >= t_frame:
                text(d, (1362, 678), '③ 現地VLM確認  Qwen2.5-VL-3B（V100ローカル）', 22, INK)
                if t_decision and t >= t_decision and calls:
                    y = 716
                    for k, title in (('first', '質問1'), ('second', '質問2')):
                        sc = (calls.get(k) or {}).get('scores') or {}
                        probs = sc.get('supply_probs') or {}
                        text(d, (1362, y), title, 20, MUTED, True)
                        y += 28
                        for lab, col in (('water', WATER), ('medicine', MED), ('other', OTHER)):
                            prob_bar(d, 1380, y, 250, ITEM_JA[lab], float(probs.get(lab, 0.0)), col)
                            y += 30
                        y += 6
                    ok = bool(allow)
                    rounded(d, (1362, 962, 1858, 1030), (30, 90, 60) if ok else (110, 35, 40), 14)
                    verdict = '判定：許可 → 避難所Bへ出発' if ok else '判定：拒否 → その場で停止'
                    text(d, (1610, 996), verdict, 30, INK, True, anchor='mm')
                else:
                    dots = '.' * (1 + int((t / 3e8) % 3))
                    text(d, (1380, 730), '静止確認 → 新規フレーム取得 → 推論中' + dots, 22, ACCENT)
            # caption
            cap = spec['captions']
            phase = 'go' if (not t_station or t < t_station) else (
                'check' if (not t_decision or t < t_decision) else 'after')
            rounded(d, (40, 846, 1320, 1048), PANEL, 18)
            lines = wrap_lines(cap[phase], 32, 1220, True)
            for k, ln in enumerate(lines[:4]):
                text(d, (64, 866 + k * 44), ln, 32, INK, True)
            emit(img)


# ---------------------------------------------------------------- cards
def card(title, body, seconds, emit, sub=None, accent=ACCENT, image=None, layout='side'):
    """layout: 'side' = text left / image right, 'image' = large image under the title."""
    base = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(base, 'RGBA')
    d.rectangle((0, 0, W, 10), fill=accent)
    text(d, (110, 90), title, 76, INK, True)
    y0 = 200
    if sub:
        text(d, (114, 196), sub, 38, accent, True)
        y0 = 280
    if image is not None and layout == 'image':
        im = image.copy()
        im.thumbnail((1700, 1080 - y0 - (150 if body else 60)))
        base.paste(im, ((W - im.width) // 2, y0))
        y = y0 + im.height + 30
        for para in body[:2]:
            text(d, (W // 2, y), para, 34, INK, anchor='ma')
            y += 52
    else:
        col = 1700 if image is None else 760
        y = y0 + 20
        for para in body:
            for ln in wrap_lines(para, 40, col):
                text(d, (114, y), ln, 40, INK)
                y += 60
            y += 22
        if image is not None:
            im = image.copy()
            im.thumbnail((900, 1080 - y0 - 80))
            base.paste(im, (W - im.width - 90, y0 + 10))
    for _ in range(int(seconds * FPS)):
        emit(base)


def table_card(title, sub, header, rows, notes, seconds, emit):
    base = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(base, 'RGBA')
    d.rectangle((0, 0, W, 10), fill=ACCENT)
    text(d, (110, 90), title, 68, INK, True)
    text(d, (114, 190), sub, 34, ACCENT, True)
    x0, y0 = 114, 290
    widths = [560] + [300] * (len(header) - 1)
    x = x0
    for h, w in zip(header, widths):
        text(d, (x, y0), h, 30, MUTED, True)
        x += w
    y = y0 + 56
    for row in rows:
        d.line((x0, y - 10, x0 + sum(widths), y - 10), fill=(50, 64, 90), width=2)
        x = x0
        for j, (cell, w) in enumerate(zip(row, widths)):
            col = INK
            if isinstance(cell, tuple):
                cell, col = cell
                col = tuple(col)
            text(d, (x, y), str(cell), 38, col, j == 0)
            x += w
        y += 74
    y += 30
    for n in notes:
        for ln in wrap_lines(n, 34, 1680):
            text(d, (x0, y), ln, 34, INK)
            y += 52
    for _ in range(int(seconds * FPS)):
        emit(base)


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    plan = json.loads(Path(a.plan).read_text(encoding='utf8'))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cam = FilmCamera(ROOT / 'worlds/film/film_camera_overview.sdf', 1280, 720)
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                           '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium',
                           '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(out)],
                          stdin=subprocess.PIPE)
    count = {'n': 0}

    def emit(img):
        ff.stdin.write(img.tobytes())
        count['n'] += 1

    chapters = []
    for part in plan['parts']:
        kind = part['kind']
        start = count['n'] / FPS
        if kind == 'card':
            image = Image.open(ROOT / part['image']).convert('RGB') if part.get('image') else None
            card(part['title'], part.get('body', []), part['seconds'], emit, part.get('sub'), image=image,
                 layout=part.get('layout', 'side'))
        elif kind == 'table':
            rows = [[tuple(c) if isinstance(c, list) else c for c in r] for r in part['rows']]
            table_card(part['title'], part['sub'], part['header'], rows, part.get('notes', []),
                       part['seconds'], emit)
        elif kind == 'mission':
            mission_segment(ROOT / part['run_dir'], part, cam, emit)
        print(f"{kind}: total {count['n'] / FPS:.1f}s", flush=True)
        label = part.get('title') if kind != 'mission' else f"デモ{part['index']}：{SCENE_JA[part['scene']]}"
        chapters.append({'start_s': round(start, 2), 'end_s': round(count['n'] / FPS, 2), 'title': label,
                         'kind': kind, 'speed': None if kind != 'mission' else f"走行{part.get('fast', 3.0):g}倍速・AI判断は等速",
                         'run_id': Path(part['run_dir']).name if kind == 'mission' else None})
    ff.stdin.close()
    ff.wait()
    (ROOT / 'docs/video_chapters.json').write_text(json.dumps(chapters, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    print(json.dumps({'out': str(out), 'seconds': round(count['n'] / FPS, 2)}))


if __name__ == '__main__':
    main()
