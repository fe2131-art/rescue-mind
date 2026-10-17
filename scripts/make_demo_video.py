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
import sys  # noqa: E402
sys.path.insert(0, str(ROOT))
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


# ---------------------------------------------------------------- narration (I-07)
class Narration:
    """Queue of narration clips on the output timeline; clips never overlap."""
    def __init__(self, speaker):
        self.speaker = speaker
        self.clips = []
        self.busy_until = 0.0

    def clip(self, text):
        sys.path.insert(0, str(ROOT / 'scripts'))
        from tts_voicevox import synthesize, duration
        wav = synthesize(text, self.speaker)
        return wav, duration(wav)

    def say(self, text, t_now):
        if not text:
            return
        wav, dur = self.clip(text)
        start = max(t_now, self.busy_until)
        self.clips.append((start, wav))
        self.busy_until = start + dur + 0.2


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
    plan_file = run_dir / 'stack_plan.json'
    if plan_file.is_file():
        sp = json.loads(plan_file.read_text(encoding='utf8'))
        mission['world_variant'] = sp.get('world_variant')
        mission['model_label'] = (sp.get('model') or '').split('/')[-1]
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
def checkpoint_episodes(run):
    """Every on-site check in time order (a recovery run has two)."""
    m, ev = run['mission'], run['events']
    eps = []
    rec = m.get('recovery')
    if rec and 'recovery_checkpoint_decision' in ev:
        cp = rec.get('first_checkpoint') or {}
        eps.append({'station': rec['first_station'], 'arrive': ev.get('recovery_supply_station'),
                    'frame': ev.get('recovery_checkpoint_frame'), 'decision_t': ev['recovery_checkpoint_decision'],
                    'end': ev.get('recovery_search_started') or ev['recovery_checkpoint_decision'] + int(3e9),
                    'decision': cp.get('decision') or {}, 'calls': cp.get('model_calls') or {},
                    'explain': (cp.get('explanation') or {}).get('text_ja')})
    if 'checkpoint_decision' in ev:
        cp = m.get('checkpoint') or {}
        dec = cp.get('decision') or {}
        station = m.get('checkpoint_station') or m['intent']['item']
        peeks = (m.get('look_around') or {}).get('peeks') or []
        if not peeks:
            eps.append({'station': station, 'arrive': ev.get('supply_station'),
                        'frame': ev.get('checkpoint_frame'), 'decision_t': ev['checkpoint_decision'],
                        'end': ev.get('checkpoint_denial_dwell_finished') or ev['checkpoint_decision'] + int(2.5e9),
                        'decision': dec, 'calls': cp.get('model_calls') or {},
                        'explain': (cp.get('explanation') or {}).get('text_ja')})
            return eps
        # I-14 look-around: the front check approved, then one check per side view (a hazard there denies)
        front_t = ev.get('front_checkpoint_decision') or ev['checkpoint_decision']
        eps.append({'station': station, 'arrive': ev.get('supply_station'), 'frame': ev.get('checkpoint_frame'),
                    'decision_t': front_t, 'end': ev.get('look_around_scheduled') or front_t + int(1e9),
                    'decision': {'allow': True, 'reason': dec.get('front_reason') or dec.get('reason')},
                    'calls': cp.get('model_calls') or {}, 'explain': (cp.get('explanation') or {}).get('text_ja')})
        start = m['mission_start_unix_ns']
        arrivals = {e['target'].split(':')[-1]: start + int(e['t_wall_s'] * 1e9)
                    for e in m['events'] if e.get('stage') == 'look_around_arrival'}
        for k, pk in enumerate(peeks):
            sd = pk['side']
            d_t = ev.get(f'peek_{sd}_checkpoint_decision')
            if d_t is None:
                continue
            nxt = arrivals.get(peeks[k + 1]['side']) if k + 1 < len(peeks) else None
            end = (ev.get('checkpoint_denial_dwell_finished') if pk.get('hazard') else None) or nxt or d_t + int(1e9)
            eps.append({'station': station, 'peek': sd, 'arrive': arrivals.get(sd), 'frame': ev.get(f'peek_{sd}_checkpoint_frame'),
                        'decision_t': d_t, 'end': end,
                        'decision': {'allow': not pk.get('hazard'), 'reason': pk.get('reason')},
                        'calls': pk.get('model_calls') or {}, 'explain': None})
    return eps


def key_episode(e, eps):
    """Checks whose outcome changes the course are shown at real time; a side view that finds nothing is not."""
    return not e.get('peek') or not e['decision'].get('allow')


def speed_plan(run, spec):
    """[(t_from_ns, t_to_ns, playback_speed)] -- driving fast, aiming/settling and waiting at check_speed,
    the last second before a course-changing decision and 1.5 s after it at 1x.  The video estimate uses this too."""
    ev, eps = run['events'], checkpoint_episodes(run)
    f0 = run['film'][0][0] if run['film'] else run['mission']['mission_start_unix_ns']
    f1 = run['film'][-1][0] if run['film'] else run['truth'][-1][0]
    t0 = f0 + int(spec.get('skip_s', 0.5) * 1e9)
    t1 = min(f1, (ev.get('shelter_approach') or (eps[-1]['end'] if eps else f1)) + int(spec.get('tail_s', 2.0) * 1e9))
    fast, slow = spec.get('fast', 3.0), spec.get('check_speed', 2.0)
    plan, cur = [], t0
    for e in eps:
        a = max(cur, (e['arrive'] or e['frame']) - int(1.0e9))
        if key_episode(e, eps):
            r0 = max(a, e['decision_t'] - int(1.0e9))
            r1 = e['decision_t'] + int(1.5e9)
        else:
            r0 = r1 = e['decision_t']
        b = max(r1, e['end'] + int(0.8e9))
        plan += [(cur, a, fast), (a, r0, slow), (r0, r1, 1.0), (r1, b, slow)]
        cur = b
    plan.append((cur, t1, fast if 'shelter_approach' in ev else 1.0))
    return plan


STATION_JA = {'water': '拠点W', 'medicine': '拠点M'}
SIDE_JA = {'L': '左', 'R': '右'}


def mission_segment(run_dir: Path, spec: dict, cam: FilmCamera, emit, narr=None, now=None):
    run = load_run(run_dir)
    ev, mission = run['events'], run['mission']
    eps = checkpoint_episodes(run)
    plan = speed_plan(run, spec)
    item = mission['intent']['item']
    route_pts = [(0.0, 0.0)] + [tuple(r[2]) for r in mission['route']]
    labels = [((2.0, 2.0, 1.05), '物資拠点 W', WATER), ((-2.0, 2.0, 1.05), '物資拠点 M', MED),
              ((3.0, -2.0, 0.95), '避難所 B', GOOD)]
    hz = (mission.get('world_variant') or {}).get('hazard_at') or spec.get('hazard_at')
    if hz:
        from rescuemind.robust_scenes import hazard_xy
        hx, hy = hazard_xy(hz)
        labels.append(((hx, hy, 1.25), '火災', BAD))
    instr = mission['instruction']
    intent_gate = mission.get('intent_gate') or {}
    total = spec.get('total', 3)

    for (sa, sb, speed) in plan:
        if sb <= sa:
            continue
        n = max(1, int((sb - sa) / 1e9 / speed * FPS))
        for i in range(n):
            t = sa + int(i * speed * 1e9 / FPS)
            img = Image.new('RGB', (W, H), BG)
            d = ImageDraw.Draw(img, 'RGBA')
            text(d, (40, 26), 'RescueMind', 40, ACCENT, True)
            text(d, (318, 36), f'デモ {spec["index"]}/{total} ｜ {spec.get("title") or SCENE_JA[spec["scene"]]}', 28, INK, True)
            rounded(d, (1150, 20, 1880, 84), PANEL, 16)
            text(d, (1172, 34), f'指示：「{instr}」'[:30], 28, INK, True)
            main = Image.open(nearest(run['film'], t)).convert('RGB').resize((1280, 720), Image.BILINEAR)
            md = ImageDraw.Draw(main, 'RGBA')
            pts = [cam.project((x, y, 0.02)) for (tt, x, y) in run['truth'] if tt <= t]
            pts = [q for q in pts if q]
            plan_px = [q for q in (cam.project((x, y, 0.01)) for x, y in route_pts) if q]
            for q1, q2 in zip(plan_px, plan_px[1:]):
                md.line([q1, q2], fill=(255, 255, 255, 110), width=3)
            if len(pts) > 1:
                md.line(pts, fill=(255, 140, 30, 235), width=6, joint='curve')
            for pos, lab, col in labels:
                q = cam.project(pos)
                if q:
                    w_ = font(24, True).getlength(lab) + 24
                    md.rounded_rectangle((q[0] - w_ / 2, q[1] - 44, q[0] + w_ / 2, q[1] - 8), radius=10,
                                         fill=(15, 22, 35, 210), outline=col + (255,), width=2)
                    md.text((q[0], q[1] - 26), lab, font=font(24, True), fill=INK, anchor='mm')
            img.paste(main, (40, 104))
            d.rectangle((40, 104, 1320, 824), outline=(60, 75, 100), width=2)
            badge = '等速 ×1' if speed == 1.0 else f'{speed:g}倍速'
            rounded(d, (60, 124, 60 + 30 + font(28, True).getlength(badge), 172),
                    (255, 140, 30, 230) if speed != 1.0 else (60, 200, 120, 230), 12)
            text(d, (75, 128), badge, 28, (10, 10, 10), True)
            wm = 'Gazebo Harmonic 実レンダリング（俯瞰カメラ）'
            d.rounded_rectangle((60, 772, 84 + font(20).getlength(wm), 806), radius=8, fill=(15, 22, 35, 190))
            text(d, (72, 777), wm, 20, (220, 228, 240))
            rcam = Image.open(nearest(run['robot'], t)).convert('RGB').resize((540, 405), Image.BILINEAR)
            img.paste(rcam, (1340, 130))
            text(d, (1340, 100), 'ロボット搭載カメラ  /camera', 22, MUTED, True)
            d.rectangle((1340, 130, 1880, 535), outline=(60, 75, 100), width=2)
            # ---- AI panel
            rounded(d, (1340, 552, 1880, 1048), PANEL, 18)
            text(d, (1362, 566), 'AI 判断パネル', 28, ACCENT, True)
            how = 'ローカルLLM' if intent_gate.get('backend') == 'llm' else 'TF-IDF'
            text(d, (1362, 608), f'指示理解（{how}）→ {ITEM_JA[item]} を避難所Bへ', 21, INK)
            y = 640
            active = None
            for k, e in enumerate(eps):
                if e['frame'] and t >= e['frame']:
                    active = e
                nxt = eps[k + 1] if k + 1 < len(eps) else None
                if e['decision_t'] and nxt is not None and t >= (nxt['arrive'] or nxt['frame']) - int(1e9):
                    ok = e['decision'].get('allow')
                    if e.get('peek'):
                        msg = f"横から見直し（{SIDE_JA[e['peek']]}）：{'火・煙なし' if ok else '火を検知'}"
                    else:
                        msg = f"確認（{STATION_JA[e['station']]}・正面）：{'許可' if ok else '依頼物資なし → 別拠点へ'}"
                    text(d, (1362, y), msg, 21, MUTED)
                    y += 28
            if active is None:
                text(d, (1362, y), '物資拠点へ移動中 …', 22, INK)
            else:
                where = f"横から見直し（{SIDE_JA[active['peek']]} 0.4 m）" if active.get('peek') else f"現地確認：{STATION_JA[active['station']]}"
                text(d, (1362, y), f"{where}  {mission.get('model_label') or spec.get('model_label', '')}", 21, INK)
                y += 32
                if t >= active['decision_t']:
                    for kk, title in (('first', '質問1'), ('second', '質問2')):
                        probs = ((active['calls'].get(kk) or {}).get('scores') or {}).get('supply_probs') or {}
                        text(d, (1362, y), title, 19, MUTED, True)
                        y += 24
                        for lab, col in (('water', WATER), ('medicine', MED), ('other', OTHER)):
                            prob_bar(d, 1380, y, 240, ITEM_JA[lab], float(probs.get(lab, 0.0)), col)
                            y += 27
                    hz = ((active['calls'].get('first') or {}).get('scores') or {}).get('hazard_prob')
                    if hz is not None and y < 950:
                        prob_bar(d, 1380, y + 2, 240, '火・煙', float(hz), BAD)
                        y += 29
                    dec = active['decision']
                    reason = dec.get('reason')
                    later_peek = any(x.get('peek') for x in eps[eps.index(active) + 1:])
                    if dec.get('allow') and active.get('peek'):
                        verdict, colr = '横から見ても火・煙なし', (30, 90, 60)
                    elif dec.get('allow') and later_peek:
                        verdict, colr = '正面は許可 → 横からも見直す', (30, 90, 60)
                    elif dec.get('allow'):
                        verdict, colr = '判定：許可 → 避難所Bへ出発', (30, 90, 60)
                    elif active.get('peek'):
                        verdict, colr = '横から火を検知 → 許可を取消・停止', (110, 35, 40)
                    elif reason == 'visible_hazard_at_checkpoint':
                        verdict, colr = '判定：危険（火災）→ 停止', (110, 35, 40)
                    elif active is not eps[-1]:
                        verdict, colr = '判定：依頼物資なし → 別拠点を確認', (120, 80, 20)
                    else:
                        verdict, colr = '判定：拒否 → その場で停止', (110, 35, 40)
                    rounded(d, (1362, 980, 1858, 1036), colr, 14)
                    text(d, (1610, 1008), verdict, 26, INK, True, anchor='mm')
                else:
                    dots = '.' * (1 + int((t / 3e8) % 3))
                    text(d, (1380, y + 10), '静止確認 → 新規フレーム → 推論中' + dots, 22, ACCENT)
            # ---- caption + robot report (explanation, never used for the decision)
            phase = 'go'
            for k, e in enumerate(eps):
                if e['frame'] and t >= (e['arrive'] or e['frame']) and not e.get('peek'):
                    phase = 'check'
                if t >= e['decision_t']:
                    nxt = eps[k + 1] if k + 1 < len(eps) else None
                    phase = 'after' if nxt is None else ('peek' if nxt.get('peek') else 'search')
            if narr is not None and phase != spec.get('_last_phase'):
                spec['_last_phase'] = phase
                narr.say((spec.get('narration') or {}).get(phase), now())
            cap = spec['captions'].get(phase) or spec['captions'].get('after')
            rounded(d, (40, 846, 1320, 1048), PANEL, 18)
            lines = wrap_lines(cap, 30, 1230, True)
            for k, ln in enumerate(lines[:2]):
                text(d, (64, 862 + k * 42), ln, 30, INK, True)
            said = None
            for e in eps:
                if e['explain'] and t >= e['decision_t']:
                    said = e['explain']
                if e.get('peek') and t >= (e['arrive'] or e['frame']):
                    said = None     # a side view has its own decision; the front report no longer describes it
            if said:
                text(d, (64, 958), 'ロボットの報告（VLMの説明文・判断には不使用）', 19, MUTED, True)
                for k, ln in enumerate(wrap_lines(f'「{said}」', 25, 1230)[:2]):
                    text(d, (64, 984 + k * 30), ln, 25, (255, 214, 150))
            emit(img)
            last = img
    # hold the final frame until the narration of this demo has finished
    if narr is not None and now is not None:
        while narr.busy_until > now() + 0.05:
            emit(last)


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
    ap.add_argument('--narrate', type=int, default=None, help='VOICEVOX speaker id (engine on 127.0.0.1:50021)')
    a = ap.parse_args(argv)
    plan = json.loads(Path(a.plan).read_text(encoding='utf8'))
    narr = Narration(a.narrate) if a.narrate is not None else None
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
        now = lambda: count['n'] / FPS
        if narr is not None and kind in ('card', 'table') and part.get('narration'):
            narr.say(part['narration'], start + 0.3)
            part['seconds'] = max(part['seconds'], narr.busy_until - start + 0.4)
        if kind == 'card':
            image = Image.open(ROOT / part['image']).convert('RGB') if part.get('image') else None
            card(part['title'], part.get('body', []), part['seconds'], emit, part.get('sub'), image=image,
                 layout=part.get('layout', 'side'))
        elif kind == 'table':
            rows = [[tuple(c) if isinstance(c, list) else c for c in r] for r in part['rows']]
            table_card(part['title'], part['sub'], part['header'], rows, part.get('notes', []),
                       part['seconds'], emit)
        elif kind == 'mission':
            mission_segment(ROOT / part['run_dir'], part, cam, emit, narr=narr, now=now)
        print(f"{kind}: total {count['n'] / FPS:.1f}s", flush=True)
        label = part.get('title') if kind != 'mission' else f"デモ{part['index']}：{part.get('title') or SCENE_JA[part['scene']]}"
        chapters.append({'start_s': round(start, 2), 'end_s': round(count['n'] / FPS, 2), 'title': label,
                         'kind': kind, 'speed': None if kind != 'mission' else f"走行{part.get('fast', 3.0):g}倍速・確認動作{part.get('check_speed', 2.0):g}倍速・AI判断の瞬間は等速",
                         'run_id': Path(part['run_dir']).name if kind == 'mission' else None})
    ff.stdin.close()
    ff.wait()
    if narr is not None and narr.clips:
        silent = out.with_suffix('.silent.mp4')
        out.replace(silent)
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', str(silent)]
        filt = []
        for k, (t, wav) in enumerate(narr.clips):
            cmd += ['-i', str(wav)]
            ms = int(t * 1000)
            filt.append(f'[{k + 1}:a]adelay={ms}|{ms},aformat=channel_layouts=stereo[a{k}]')
        filt.append(''.join(f'[a{k}]' for k in range(len(narr.clips))) +
                    f'amix=inputs={len(narr.clips)}:normalize=0,volume=1.6[aout]')
        cmd += ['-filter_complex', ';'.join(filt), '-map', '0:v', '-map', '[aout]', '-c:v', 'copy',
                '-c:a', 'aac', '-b:a', '160k', '-t', f"{count['n'] / FPS:.2f}", '-movflags', '+faststart', str(out)]
        subprocess.run(cmd, check=True)
        silent.unlink()
    (ROOT / 'docs/video_chapters.json').write_text(json.dumps(chapters, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    print(json.dumps({'out': str(out), 'seconds': round(count['n'] / FPS, 2)}))


if __name__ == '__main__':
    main()
