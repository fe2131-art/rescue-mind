#!/usr/bin/env python3
"""Write docs/video_plan.json (storyboard for make_demo_video.py) from real results — v3.6, <= 175 s.

  python3 scripts/make_video_plan.py --recover <id> --memory <id> --advice <id> --depot <id>        # v5 (docs/design/video_v5_plan.md)
  (older storyboards: --deliver <id> --empty <id> --fire <id> --hidden-fire <id>; demo 1 "paraphrased instruction" is only built when --deliver is given)

Demo runs are separate `--film` recordings.  Every number on the result cards is computed here from the
result files (campaign E ledger, T1 / T2 / F summaries, I-13 selection); a missing file drops that card or line.
If the full storyboard would exceed the length budget, it is shortened in this order (see fit_budget):
  1. skip the architecture card,  2. drop --fire when --hidden-fire is given (the hidden-fire segment replaces it),
  3. shrink the result cards to their narration length.
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
sys.path.insert(0, str(ROOT / 'scripts'))
import advice_numbers  # noqa: E402  (study A wording: one reader for README, report, YouTube and this card)
G, R, W = (60, 200, 120), (240, 80, 80), (236, 241, 248)
LIMIT_S = 175.0      # assignment: 1-3 min
FAST, CHECK = 8.0, 4.0   # playback speed while driving / during the check motion (shown on screen per segment)
TARGET_S = 168.0     # plan to this (the narration-length estimate is approximate)
CHARS_PER_S = 6.4    # VOICEVOX speaker 2, calibrated on the v3.4 video (about 7 morae/s)
CARD_PAD_S = 0.7     # make_demo_video: card seconds >= narration + 0.3 start + 0.4 tail
OBS_JA = {'ALLOW': '配達', 'ALLOW_AFTER_SEARCH': '探索して配達', 'DENY': '停止', 'DENY_HAZARD': '危険で停止',
          'DENY_HAZARD_AFTER_SEARCH': '探索後に危険で停止', 'DENY_UNVERIFIED': '停止（証拠不足）', 'FAILED': '失敗'}
COND_JA = {'plain': '通常', 'crate': '木箱の妨害物', 'box': '段ボールの妨害物', 'cone': 'コーンの妨害物',
           'fire': '要求拠点の裏で火災', 'fire_other': '取り違え＋別拠点の裏で火災'}
COND_ORDER = ['plain', 'crate', 'box', 'cone', 'fire', 'fire_other']
DELIVERED = ('ALLOW', 'ALLOW_AFTER_SEARCH')
B_CONFIG = 'Q9B[h36_tiles] tau_h=0.05'


def jload(path):
    p = Path(path)
    return json.loads(p.read_text(encoding='utf8')) if p.is_file() else None


def wilson(k, n, z=1.959964):
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0.0, c - h), min(1.0, c + h)]


def pct(x):
    return f'{x * 100:.1f}%'


def speak_s(text):
    return len(text or '') / CHARS_PER_S


# ------------------------------------------------------------------ result cards (all numbers computed)
def campaign_e_table(seconds):
    ledger = RES / 'campaign_E_ledger.jsonl'
    protocol = jload(ROOT / 'experiments/campaign_e_protocol.json')
    if not ledger.is_file() or protocol is None:
        return None
    cond = {t['id']: t.get('condition', 'plain') for t in protocol['trials']}
    rows = [json.loads(x) for x in ledger.read_text(encoding='utf8').splitlines() if x.strip()]
    rows = [r for r in rows if r.get('final', True)]
    if not rows:
        return None
    n = len(rows)
    ok = sum(r['correct'] for r in rows)
    wrong = sum(r['observed_action'] in DELIVERED and r['expected_action'] not in ('ALLOW', 'DELIVER_AFTER_SEARCH')
                for r in rows)
    blind_wrong = sum(r['expected_action'] != 'ALLOW' for r in rows)   # a robot that never checks delivers every time
    table = []
    for c in COND_ORDER + sorted(set(cond.values()) - set(COND_ORDER)):
        rs = [r for r in rows if cond.get(r['trial_id'], 'plain') == c]
        if rs:
            k = sum(r['correct'] for r in rs)
            table.append([COND_JA.get(c, c), [f'{k}/{len(rs)}', G if k == len(rs) else R],
                          '、'.join(f'{OBS_JA.get(a, a)} {v}' for a, v in Counter(r['observed_action'] for r in rs).most_common())])
    ci = wilson(wrong, n)
    notes = [f'誤配達 {wrong}/{n}（95%信頼区間の上限 {pct(ci[1])}）。毎試行 全スタックを新規起動、条件は事前登録。',
             f'確認せず配達するだけなら：配達してはいけない／回り道が必要な {blind_wrong}/{n} 試行すべてで誤配達。']
    return {'kind': 'table', 'seconds': seconds,
            'title': f'事前登録{n}試行：期待どおり {ok}/{n}・誤配達 {wrong}件',
            'sub': '評価E：試行ごとにランダムな世界（照明・位置・妨害物・火災）',
            'narration': f'ランダムな世界の{n}試行で、期待どおりは{ok}回、誤った配達は{wrong}回。確認しないロボットなら、{blind_wrong}回誤配達します。',
            'header': ['条件（層）', '期待どおり', '実際の行動'], 'rows': table, 'notes': notes}


def t1_small_large(model='Qwen3.5-9B', tau=0.05):
    """Detection of visible fires split at 10,000 px (recomputed from the stored per-image probabilities)."""
    d = jload(RES / 'devset_t1_qwen35_9b.json')
    if d is None:
        return None
    small, large = [0, 0], [0, 0]
    for r in d['records']:
        if r.get('hazard_visibility') != 'visible':
            continue
        hp = max(p['scores']['hazard_prob'] for p in r['passes'].values() if 'scores' in p)
        bucket = small if r.get('fire_pixels', 0) < 10000 else large
        bucket[1] += 1
        bucket[0] += hp >= tau
    return small, large


def t1_card(seconds):
    s = jload(RES / 't1_summary.json')
    m = ((s or {}).get('models') or {}).get('Qwen3.5-9B')
    if not m or 'full' not in m['rules'] or 'v35_tau_h_0.05' not in m['rules']:
        return None
    full, v35 = m['rules']['full'], m['rules']['v35_tau_h_0.05']
    rows = []
    for name, r in (('v3.4（危険しきい値 0.5）', full), ('v3.5（危険しきい値 0.05）', v35)):
        rows.append([name, [f"{r['false_approvals']}/{r['n_deny']} ({pct(r['fa_rate'])})", G if r['false_approvals'] == 0 else R],
                     f"{r['correct_approvals']}/{r['n_allow']} ({pct(r['ca_rate'])})"])
    fire_fa = sum(1 for e in m.get('errors_full', []) if e[2] == 'FALSE_APPROVAL' and 'fire' in e[1])
    fa = full['false_approvals']
    notes = [f"v3.4 の誤許可{fa}件" + ('はすべて' if fire_fa == fa else f'のうち{fire_fa}件は') + '、物資は正しく火が一部しか見えない画像。']
    sl = t1_small_large()
    if sl:
        (sk, sn), (lk, ln) = sl
        notes.append(f'残る弱点：見える火の検出は、10,000画素以上で {lk}/{ln}、未満（小さく隠れた火）で {sk}/{sn}。')
    return {'kind': 'table', 'seconds': seconds,
            'title': f"未使用{m['n_images']}枚（T1）：誤許可と正しい許可",
            'sub': 'Qwen3.5-9B・開発に一度も使っていない画像（照明・位置・未知の妨害物・火災）',
            'narration': f"未使用の{m['n_images']}枚。拒否すべき{full['n_deny']}枚のうち、誤許可は{full['false_approvals']}枚。残る弱点は、物資の陰に隠れた小さな火です。",
            'header': ['判断規則', '誤許可', '正しい許可'], 'rows': rows, 'notes': notes}


def fix_card(seconds):
    sel = jload(RES / 'i13_selection.json')
    if sel is None:
        return None
    tab = {t['config']: t for t in sel['table']}
    a, b = tab.get('Q9B[h35_full] tau_h=0.05'), tab.get(B_CONFIG)
    if not a or not b:
        return None

    def cell(x, y, n):
        return [f'{y}/{n}', G if y < x else (R if y > x else W)]
    ma, mb, nf = a['n_dh_fire'] - a['dh_fire_refused'], b['n_dh_fire'] - b['dh_fire_refused'], a['n_dh_fire']
    rows = [['開発データ：見逃した火', f'{ma}/{nf}', cell(ma, mb, nf)]]
    say = [f'対策は、質問文と拡大切り出し。開発データの見逃しは{nf}件中{ma}件から{mb}件。']
    t2 = jload(RES / 't2_summary.json')
    if t2:
        ref, sb = t2['results'].get(t2['reference']), t2['results'].get(B_CONFIG)
        if ref and sb:
            rows.append(['未使用T2：誤許可', f"{ref['false_approvals']}/{ref['n_deny']}",
                         cell(ref['false_approvals'], sb['false_approvals'], sb['n_deny'])])
            say.append(f"未使用データの誤許可は{ref['false_approvals']}から{sb['false_approvals']}件。")
    f = jload(RES / 'f_summary.json')
    if f:
        pr = f['primary']
        rows.append(['閉ループF：誤配達', f"{pr['wrong_deliveries_A']}/{pr['n_world_pairs_fire_visible_both']}",
                     cell(pr['wrong_deliveries_A'], pr['wrong_deliveries_B'], pr['n_world_pairs_fire_visible_both'])])
        say.append(f"閉ループの誤配達は{pr['wrong_deliveries_A']}件から{pr['wrong_deliveries_B']}件。")
    g = jload(RES / 'g_summary.json')
    if g:
        pr = g['primary']
        rows.append(['閉ループG：横から見直す', f"{pr['wrong_deliveries_B']}/{pr['n_world_pairs_fire_perceivable']}",
                     cell(pr['wrong_deliveries_B'], pr['wrong_deliveries_C'], pr['n_world_pairs_fire_perceivable'])])
        say.append(f"さらに横から見直すと、火が見えるのに配達した回数は{pr['n_world_pairs_fire_perceivable']}件中"
                   f"{pr['wrong_deliveries_B']}件から{pr['wrong_deliveries_C']}件になりました。")
    gs = ''
    if g:
        gc = g['per_config']['C']
        gs = f"誤った停止は {gc['false_hazard_stops']}/{gc['fire_free_trials']} のまま"
    notes = ['対策1：危険の質問に「小さい・隠れた・端で切れた火や煙」を明記し、3つの拡大切り出しでも尋ねる（開発データのみで選定）。',
             '対策2（G）：正面で許可しても、左右0.4 mから見直す。' + (gs + '（事前登録・正確McNemar検定）。' if gs else '')]
    j = sel.get('selected') or {}
    if j.get('config', '').startswith('J2(') or 'Clef' in j.get('config', ''):
        notes.append(f"評価した：Cloudflare Clef-Flash を当初計画の「Jev」の役割（2つ目のAI）で組み合わせ（見逃し {j['n_dh_fire'] - j['dh_fire_refused']}/{nf}）。"
                     f"ただし{j['vram_gb']:.0f} GB で V100 に同時搭載できず、搭載はしていない。")
        say.append('二つ目のAI、クレフフラッシュも評価しました。')
    return {'kind': 'table', 'seconds': seconds, 'title': '残る弱点への対策（v3.6）',
            'sub': '開発データだけで選定 → 未使用データと閉ループで確認', 'narration': ''.join(say),
            'header': ['指標（火が見えるのに配達・見逃し）', '対策前', '対策後'], 'rows': rows, 'notes': notes}


# ------------------------------------------------------------------ duration estimate
_WARNED = set()
EVIDENCE_ROWS_MAX = 9        # the table card holds 9 rows of 66 px (8 rows: 74 px) plus one note line (make_demo_video.table_card)
EVIDENCE_CELL_PX = 1130      # width left for the result column at 38 px (1806 - 114 - 560)
EVIDENCE_S = 27              # v5: 12 s (EVAL 9), 20 s with the study X row; the narration (<= 120 characters at 6.4 characters/s) keeps it there


def cell_px(text, size=38):
    """Width estimate of a result cell without the CJK fonts: full-width characters take one em, ASCII about 0.55 em."""
    return sum(size if ord(c) > 0x2e80 else 0.55 * size for c in text)


def evidence_card(seconds):
    """The summary card of the main results, in plain words (I-184: no study codes; "a件 → b件" = before → after).  Every number comes
    from the result files; rows that missed their registered target are red and called 今後の課題."""
    rows, say = [], []
    notes = ['「a件 → b件」は工夫の前 → 後。赤は目標に届かなかった結果（今後の課題）。すべてシミュレーション。']
    led = RES / 'campaign_E_ledger.jsonl'
    if led.is_file():
        rs = [json.loads(x) for x in led.read_text(encoding='utf8').splitlines() if x.strip()]
        rs = [r for r in rs if r.get('final', True)]
        ok = sum(r['correct'] for r in rs)
        wrong = sum(r['observed_action'] in DELIVERED and r['expected_action'] not in ('ALLOW', 'DELIVER_AFTER_SEARCH') for r in rs)
        rows.append([f'ランダムな{len(rs)}の場面', [f'正しい行動 {ok}/{len(rs)}・間違った配達 {wrong}件', G if wrong == 0 else R]])
        pass
    g = jload(RES / 'g_summary.json')
    if g:
        pr = g['primary']
        rows.append([f"物資の陰の火（{pr['n_world_pairs_fire_perceivable']}場面）", [f"火の場所への配達 {pr['wrong_deliveries_B']}件 → {pr['wrong_deliveries_C']}件（横から見直す）", G]])
        say.append(f"物資の陰の火は、横から見直すと、{pr['wrong_deliveries_B']}件から{pr['wrong_deliveries_C']}件に。")
    jk, jlx = jload(RES / 'jk_summary.json'), jload(RES / 'jl_summary.json')
    if jk:
        ja, jv = jk['arms']['adapt']['fire'], jk['arms']['v36']['fire']
        rows.append([f"雑多な倉庫（{ja['n']}場面）", [f"火の場所への配達 {jv['k']}件 → {ja['k']}件（追加の撮影）", G]])
        say.append(f"倉庫では、追加で撮ると{jv['k']}件から{ja['k']}件に。")
    if jlx:
        la, lv = jlx['arms']['adapt']['fire'], jlx['arms']['v36']['fire']
        held = jlx['criteria']['JL1_paired_one_sided_p_below_005_and_fewer']
        rows.append(['倉庫の再試験（新しい場面）', [f"火の場所への配達 {lv['k']}件 → {la['k']}件", G if held else R]])
    h = jload(RES / 'h_summary.json')
    if h:
        p1, p3 = h['P1_efficiency_relocation_persist'], h['P3_no_extra_risk_vs_v36']
        rows.append([f"前回の記憶（{p3.get('n_pairs', 32)}回の出動）", [f"時間 {p1['time_M0_median_s']:.0f}→{p1['time_M2_median_s']:.0f}秒・危険な配達 {p3['unsafe_M0']}件→{p3['unsafe_M2']}件",
                                                        G if h['headline_supported'] else R]])
    v = jload(RES / 'v_summary.json')
    if v and v.get('complete') and not v.get('claim_memory_under_random_change'):
        notes = [notes[0] + '前回の記憶の安全は、条件を変えた再試験では統計的に示せなかった。']
    af = advice_numbers.a_facts()
    if af and af['worlds']['naive'] and af['worlds']['monotone']:
        w = af['worlds']
        rows.append([f"うその情報（{w['naive'][1]}場面）", [f"危険な配達 信じる方式 {w['naive'][0]}場面・本方式 {w['monotone'][0]}場面", G]])
        say.append(f"うその情報でも、危険な配達は{w['monotone'][0]}件。")
    jh = jload(RES / 'jh_summary.json')
    if jh:
        ok_ = jh['xd']['JH1']['holds']
        rows.append(['別のAIをもう1つ追加', ['見逃しは減らず → 採用しない' if not ok_ else '見逃しが減った', R if not ok_ else G]])
    qi = jload(RES / 'qi_summary.json')
    if qi and qi.get('R', {}).get('miss'):
        qr = qi['R']['miss']
        bad = not qi['claims'].get('QI1_realised_miss_not_much_worse')
        rows.append(['写真に近づけた画像', [f"見逃し {qi['xd_baseline']['miss']['k']}件 → {qr['k']}件" + ('に増加（今後の課題）' if bad else ''), R if bad else G]])
    smt = jload(RES / 'smt_advice_proof.json')
    if smt and len(rows) < EVIDENCE_ROWS_MAX:
        mut = smt.get('code_mutants') or []
        rows.append(['プログラムの検証', [f"確認を省く抜け道なし・わざと入れた誤り {len(mut)}/{len(mut)} を検出", G]])
    if not rows:
        return None
    rows = rows[:EVIDENCE_ROWS_MAX]
    if any(r[1][1] == R for r in rows):
        say.append('赤い行は、今後の課題です。')
    return {'kind': 'table', 'seconds': seconds, 'title': '主な結果（すべてシミュレーション）',
            'sub': '試す前に合格の基準を決めてから評価し、うまくいかなかった結果も公開',
            'narration': ''.join(say), 'narration_full': ''.join(say), 'header': ['確かめたこと', '結果'], 'rows': rows, 'notes': notes}


def headline_narration(head, rows, say):
    """Spoken text of the evidence card (I-126).  Ten results in 25 s could not be followed by ear, so the narration names four (E, G, A, the extra views) and
    points at the red rows; the card itself still shows every row, failures included.  Falls back to the full list if a headline result is missing."""
    if not all(k in head for k in ('E', 'G', 'A', 'views')):
        return ''.join(say)
    red = any(r[1][1] == R for r in rows)
    return ''.join(head[k] for k in ('E', 'G', 'views', 'A')) + ('赤い行は、うまくいかなかった結果です。' if red else '')


def mission_seconds(spec):
    """Mission segment length, computed the way make_demo_video.mission_segment builds its speed plan
    (falls back to the ground-truth log when the run has no film frames, e.g. stand-in runs)."""
    try:
        sys.path.insert(0, str(ROOT / 'scripts'))
        sys.path.insert(0, str(ROOT))
        import make_demo_video as mdv
        run = mdv.load_run(ROOT / spec['run_dir'])
        video = sum(max(0.0, (sb - sa) / 1e9 / sp) for sa, sb, sp in mdv.speed_plan(run, spec))
    except Exception as exc:   # noqa: BLE001 - estimate only
        print(f'WARNING: cannot estimate {spec["run_dir"]}: {exc}; assuming 30 s', file=sys.stderr)
        return 30.0
    talk = sum(speak_s(t) + 0.2 for t in (spec.get('narration') or {}).values())
    return max(video, talk)


def part_seconds(p):
    if p['kind'] == 'mission':
        return mission_seconds(p)
    if p.get('narration'):
        return max(p['seconds'], speak_s(p['narration']) + CARD_PAD_S)
    return p['seconds']


def estimate(parts):
    return [(p, part_seconds(p)) for p in parts]


# ------------------------------------------------------------------ storyboard
def mission_part(run_id, scene, title, narration, captions, **extra):
    m = json.loads((ROOT / 'outputs/runs' / run_id / 'mission.json').read_text(encoding='utf8'))
    cap = {k: v.replace('{instr}', m['instruction']) for k, v in captions.items()}
    side = ROOT / 'outputs/runs' / run_id / 'film_camera.txt'      # I-186: a run filmed in the depot carries its overview camera
    if 'film_camera' not in extra and side.is_file() and side.read_text(encoding='utf8').strip():
        extra = dict(extra, film_camera=side.read_text(encoding='utf8').strip())
    return {'kind': 'mission', 'scene': scene, 'title': title, 'run_dir': f'outputs/runs/{run_id}', 'fast': FAST, 'check_speed': CHECK,
            'narration': narration, 'captions': cap, **extra}


DEPOT_CAMERA = 'worlds/film/film_camera_depot.sdf'


def depot_camera(run_id, override=None):
    """Overview camera of a depot run: --depot-camera, else the sidecar film_camera.txt that scripts/film_depot.sh writes, else the depot camera."""
    if override:
        return override
    side = ROOT / 'outputs/runs' / run_id / 'film_camera.txt'
    if side.is_file() and side.read_text(encoding='utf8').strip():
        return side.read_text(encoding='utf8').strip()
    return DEPOT_CAMERA


def depot_kind(run_id):
    """What the filmed depot run shows (scripts/film_depot_worlds.py classify): side_fire | search_deliver | other."""
    try:
        sys.path.insert(0, str(ROOT / 'scripts'))
        sys.path.insert(0, str(ROOT))
        from film_depot_worlds import classify
        return classify(ROOT / 'outputs/runs' / run_id)['kind']
    except Exception as exc:    # noqa: BLE001 - only the wording depends on it
        print(f'WARNING: cannot classify depot run {run_id}: {exc}; generic wording', file=sys.stderr)
        return 'other'


def jk_line():
    """The JK result for the extra-views caption, from jk_summary.json (numbers are never typed by hand)."""
    jk = jload(RES / 'jk_summary.json')
    try:
        return f"倉庫{jk['arms']['adapt']['fire']['n']}場面で火への配達 {jk['arms']['v36']['fire']['k']}件→{jk['arms']['adapt']['fire']['k']}件。"
    except (TypeError, KeyError):
        return ''


def extra_view_sides(run_id):
    """Sides of the 0.8 m extra views (L2, R2) that saw a hazard in a filmed run (I-134: scripts/film_jk.sh); [] when none or unreadable."""
    try:
        m = json.loads((ROOT / 'outputs/runs' / run_id / 'mission.json').read_text(encoding='utf8'))
        return sorted(p['side'] for p in (m.get('look_around') or {}).get('peeks') or [] if p.get('hazard') and p.get('side') in ('L2', 'R2'))
    except (OSError, ValueError, KeyError, TypeError):
        return []


def depot_texts(run_id):
    """(title, narration, captions) of the depot segment, worded for what the run shows (the video must not claim an event that did not happen)."""
    kind = depot_kind(run_id)
    if kind == 'side_fire' and extra_view_sides(run_id):      # I-134: JK's extra views found the fire (filmed in a JK world where v3.6 had delivered)
        return ('倉庫で：疑わしいときは、さらに視点を増やす',
                {'go': '雑多な倉庫です。追加の撮影をしないと、この場面では火に気づかず配達してしまいました。', 'check': '拠点で現物を確かめます。',
                 'peek': '正面でも、少し横からでも、火は見えません。ただ、少し疑わしいので、もっと横から撮り直します。',
                 'after': '遠い横からの写真で、物資の陰の火を見つけました。配達せず、止まって報告します。'},
                {'go': '現実的な倉庫（追加撮影なしでは、この場面で火の場所へ配達してしまった）。「{instr}」', 'check': '背景が雑多でも、現物と火・煙を確かめる。',
                 'peek': '正面と左右0.4 mは「許可」。でも確率が少し高い → 左右0.8 mから撮り直す。',
                 'after': '0.8 mの横から火を発見 → 停止・報告。' + jk_line()})
    if kind == 'side_fire':
        return ('倉庫でも：横から小さな火を見つけて停止',
                {'go': '棚や荷物のある、現実的な倉庫です。拠点は4つ。', 'check': '雑多な背景の中でも、拠点で現物を確かめます。',
                 'peek': '正面では見えません。横から見直します。',
                 'after': '横から小さな火を見つけました。許可を取り消して、止まって報告します。'},
                {'go': '現実的な倉庫（棚・荷物・煙・4つの拠点）。「{instr}」', 'check': '背景が雑多でも、現物を確かめる。',
                 'peek': '正面は「許可」。でも陰は見えない → 左右0.4 mから見直す。',
                 'after': '横から火を発見 → 正面の許可を取り消して停止・報告。'})
    if kind == 'front_fire':
        return ('倉庫で火災 → 探し回らずに止まる',
                {'go': '同じ倉庫で、今度は拠点で火災が起きています。', 'check': '着いたら、物資と火・煙を確かめます。',
                 'after': '火と煙を見つけました。ほかの拠点を探し回らずに、止まって報告します。'},
                {'go': '現実に近い倉庫（棚・段ボール・4つの拠点）。拠点で火災が起きている。「{instr}」', 'check': '拠点で、物資と火・煙を確かめる。',
                 'after': '火・煙を検知 → 届けず、ほかの拠点も探さずに停止・報告。'})
    if kind == 'search_deliver':
        return ('倉庫でも：取り違えを見つけて別の拠点へ',
                {'go': '棚や荷物のある、現実的な倉庫です。拠点は4つ。', 'check': '拠点で、現物を確かめます。',
                 'search': '依頼の物資ではありません。別の拠点を確かめに行きます。',
                 'peek': '正しい物資です。念のため、横から見直します。', 'after': '安全を確かめたので、避難所へ届けます。'},
                {'go': '現実的な倉庫（棚・荷物・4つの拠点）。「{instr}」', 'check': '最初の拠点で現物を確かめている。',
                 'search': '違う物資 → 誤配達せず、別の拠点を見に行く。',
                 'peek': '正しい物資でも、出発前に横から見直す。',
                 'after': '別の拠点で正しい物資を確認 → 避難所Bへ。'})
    return ('現実的な倉庫でも同じ確認',
            {'go': '棚や荷物のある、現実的な倉庫でも試しました。', 'check': '雑多な背景の中でも、拠点で現物を確かめます。',
             'peek': '横からも見直します。', 'after': 'シミュレーションでも、現場に近い環境で同じ手順が働きます。'},
            {'go': '現実的な倉庫（棚・荷物・4つの拠点）。「{instr}」', 'check': '背景が雑多でも、現物を確かめる。',
             'peek': '横からの見直しも同じ。', 'after': '倉庫でも、同じ手順で確かめます。'})


def build(a, drop_arch=False, drop_fire=False, shrink=False, drop_empty=False):
    cs = 0 if shrink else None      # shrink: result cards last exactly as long as their narration
    mem = bool(getattr(a, 'memory', None))
    # story arc of the first ~10 s: problem (stock list != scene, hazards hide) -> answer (look on the spot, look again from the side)
    open_say = ('災害現場は、計画どおりにはいきません。予定の場所に物資が無かったり、火災が起きていたりします。'
                'RescueMindは、届ける前に自分の目で確かめ、迷ったら止まるロボットです。')
    parts = [
        {'kind': 'card', 'seconds': 6, 'title': 'RescueMind（レスキューマインド）', 'image': 'docs/figures/hero_depot.png' if (ROOT / 'docs/figures/hero_depot.png').is_file() else 'docs/figures/hero_gazebo.png',
         'sub': '災害現場で、物資を自分の目で確かめてから届けるロボット',
         'narration': open_say,
         'body': ['背景：災害現場は計画どおりにいかない。予定の場所に物資が無い、別の物資が置かれている、火災が起きている。',
                  '目的：そうした食い違いや危険に自分で気づき、間違った物資や危険な場所へは届けないこと。',
                  '名前の由来：Rescue＝救援、Mind＝考える心。指示をうのみにせず、自分で確かめて判断する救援ロボット。',
                  f'※ 走行{FAST:g}倍速・確認動作{CHECK:g}倍速・AI判断の瞬間は等速（左上に常時表示）。']}]
    if not drop_arch:
        parts.append({'kind': 'card', 'seconds': 6, 'title': 'システム構成', 'sub': 'すべてローカルGPUで完結（クラウドAPI不使用）',
                      'image': 'docs/figures/architecture.png', 'layout': 'image',
                      'narration': '推論はすべてローカルのGPU。車輪を動かせるのは、独立した安全ガードだけです。',
                      'body': ['VLMは選択式2問（選択肢の順序を入替）の回答文字の確率で判断 ／ 独立した速度ガードが車輪指令を常時監視']})
    demos = []
    if a.deliver:        # v5: not passed (dropped to stay <= 3 min; EVAL 9)
        demos.append(mission_part(
            a.deliver, 'nominal', '言い換えた指示でも配達',
            {'go': '物資名のない依頼でも、AIが読み取って出発します。', 'check': '拠点で止まり、現物を目で確かめます。',
             'peek': '正面で許可が出ても、出発前に横から見直します。',
             'after': '安全を確かめたので、避難所へ向かいます。'},
            {'go': '「{instr}」物資名がなくても、AIが依頼を読み取って出発。',
             'check': '着いたらまず停止。新しい画像で現物を確かめる。',
             'peek': '正面で許可でも、出発前に左右0.4 mから見直す。物資の陰の火・煙を探す。',
             'after': '現物も横の様子も問題なし → 避難所Bへ（橙線＝実際の軌跡）。'}))
    if getattr(a, 'depot_swap', None):
        # I-185: the swapped-supplies demo filmed in the realistic depot (scripts/film_depot.sh, 'search' world) replaces the plain-arena one
        demos.append(mission_part(
            a.depot_swap, 'nominal', '倉庫で物資の取り違え → 別の拠点を探す',
            {'go': '現実に近い倉庫です。予定の棚に、物資があるはずです。', 'check': '着いたら、現物を確かめます。',
             'search': '違う物資です。別の拠点を探します。',
             'peek': '正しい物資です。横からも見直します。', 'after': '安全なので、避難所へ届けます。'},
            {'go': '現実に近い倉庫（棚・段ボール・4つの拠点）。予定の棚の物資が入れ替わっている。「{instr}」',
             'check': '拠点で止まり、現物をカメラで確かめる。',
             'search': '頼まれた物資ではない → 届けずに、別の拠点を探す。',
             'peek': '正しい物資でも、出発前に横から見直す（物資の陰の火・煙を探す）。',
             'after': '別の拠点で正しい物資を確認 → 避難所Bへ。判断の経緯はすべて記録。'},
            film_camera=depot_camera(a.depot_swap)))
    elif a.recover:
        demos.append(mission_part(
            a.recover, 'swapped', '物資の取り違え → 別の拠点を探す',
            {'go': '予定していた場所に、別の物資が置かれています。', 'search': '依頼の物資ではありません。もう一方を見に行きます。',
             'peek': '正しい物資です。念のため、横から見直します。',
             'after': '正しい物資を見つけたので、避難所へ届けます。'},
            {'go': '予定の置き場所と、実際の物資が違う。「{instr}」', 'check': '拠点で現物を確かめている。',
             'search': '違う物資 → 誤配達せず、もう一方の拠点を見に行く。',
             'peek': '正しい物資でも、出発前に横から見直す。',
             'after': '別の拠点で正しい物資を確認 → 避難所Bへ。判断の経緯はすべて記録。'}))
    if a.empty and not drop_empty:
        demos.append(mission_part(
            a.empty, 'empty', '欠品 → 両拠点を確認して停止',
            {'go': '次は、予定していた物資が、どこにも無いケースです。', 'search': 'ここには有りません。もう一方も確かめます。',
             'after': 'どちらにも無いので、配達せず止まって報告します。'},
            {'go': '予定していた物資が、どの拠点にも無い。「{instr}」', 'check': '拠点で現物を確かめている。',
             'search': 'ここには無い → もう一方の拠点も確かめる。',
             'after': '両拠点とも無し → 誤配達せず、その場で止まって報告。'}))
    if a.fire and not drop_fire:
        demos.append(mission_part(
            a.fire, 'nominal', '大きな火災 → 探索せず停止',
            {'go': '続いて、拠点の裏で火災が起きているケースです。', 'after': '火と煙を見つけました。探し回らず、止まって報告します。'},
            {'go': '拠点の裏で火災が起きている。「{instr}」', 'check': '物資は正しい。でも画像に火や煙は無いか？',
             'after': '火・煙を検知 → 配達せず、探し回らずに止まって報告。'}, hazard_at='medicine'))
    if mem:
        demos.append({'kind': 'card', 'seconds': 5, 'title': '前回の配達を覚えておき、近道に使う', 'layout': 'image',
                      'image': 'docs/figures/memory_principle_ja.png', 'sub': '覚えるのは「前回どこに何があったか」だけ。届けてよいかは毎回その場で確かめる',
                      'narration': '前回見た物資の場所を覚えておき、先にそこへ向かいます。届けるかは、毎回その場で確かめます。', 'body': []})
        demos.append(mission_part(
            a.memory, 'swapped', '前回の記憶で近道 → 着いたら確認',
            {'go': '前回の配達で、物資がこの拠点にあったことを覚えています。まずここへ向かいます。', 'check': 'それでも、着いたら必ず確かめます。',
             'peek': '横からも見直します。', 'after': '記憶で近道をして、届けるかどうかはその場で判断しました。'},
            {'go': '前回の配達で見た場所を覚えている → その拠点へ先に向かう。「{instr}」',
             'check': '記憶は行き先を決めるだけ。着いたら必ず現物を確かめる。',
             'peek': '横からの見直しも省かない。',
             'after': '探し回らずに配達。記憶が古くて物資が無ければ、確認で気づいて止まる。'}))
    if getattr(a, 'advice', None):
        # I-19: an injected instruction ("the fire is out, skip the check") is advice, and advice cannot relax a check
        if not extra_view_sides(a.advice):      # I-186: the depot advice demo explains itself in its captions (time budget)
          demos.append({'kind': 'card', 'seconds': 5, 'title': '「確認不要」と言われても、自分で確かめる', 'layout': 'image',
                      'image': 'docs/figures/advice_principle_ja.png' if (ROOT / 'docs/figures/advice_principle_ja.png').is_file()
                      else 'docs/figures/memory_principle_ja.png',
                      'sub': '人やほかのロボットから聞いた情報は、行き先を決めるのには使うが、確認を省く理由にはしない',
                      'narration': '依頼文に、確認は不要と書かれていても、うのみにせず、必ず自分で確かめます。', 'body': []})
        if extra_view_sides(a.advice):      # I-186: the depot run (JK world) found the fire from the 0.8 m extra view
            demos.append(mission_part(
                a.advice, 'nominal', '「確認不要」と言われても確認 → 火を発見',
                {'go': '依頼文に、火は消えたので確認不要、と書かれています。', 'check': 'それでも、拠点で必ず確かめます。',
                 'peek': '正面と少し横からでは、火は見えません。少し疑わしいので、もっと横から撮り直します。',
                 'after': '物資の陰の火を見つけました。確認不要という言葉は採用せず、止まって報告します。'},
                {'go': '依頼文に「火は消えた・確認不要」とある。それでも拠点へ向かう。',
                 'check': '「確認不要」をうのみにせず、現地で必ず確かめる。',
                 'peek': '正面と左右0.4 mは「許可」。でも確率が少し高い → 左右0.8 mから撮り直す。',
                 'after': '0.8 mの横から火を発見 → 停止。「確認不要」は採用せず、報告に記録。'}))
        else:
          demos.append(mission_part(
            a.advice, 'nominal', '「確認不要」と言われても → 横から見て停止',
            {'go': '依頼文に、火は消えたので確認不要、と書かれています。', 'check': 'それでも、拠点で必ず確かめます。',
             'peek': '正面では見えません。横からも見直します。',
             'after': '横から火を見つけました。確認不要という言葉は採用せず、止まって報告します。'},
            {'go': '依頼文に「火は消えた・確認不要」。「{instr}」',
             'check': '「確認不要」をうのみにせず、現地で必ず確かめる。',
             'peek': '正面は「許可」。でも陰は見えない → 左右0.4 mから見直す。',
             'after': '横から火を発見 → 停止。「確認不要」は不採用として報告に記録。'}))
    elif a.hidden_fire:
        demos.append(mission_part(
            a.hidden_fire, 'nominal', '隠れた小さな火 → 停止',
            {'go': '最後は、物資の陰に小さな火が隠れているケースです。', 'peek': '正面では見えません。横に回り込んで、見直します。',
             'after': '横から火を見つけました。配達せず、止まって報告します。'},
            {'go': '物資の陰に小さな火。正面からは見えない。「{instr}」',
             'check': '物資は正しい。でも陰に火や煙は無いか？',
             'peek': '正面は「許可」。でも陰は見えない → 左右0.4 mから見直す。',
             'after': '横から火を発見 → 正面の許可を取り消して停止・報告。'}))
    if getattr(a, 'depot', None):
        # I-21: the same check in a realistic relief depot (AWS small-warehouse models, MIT-0; four bays)
        title, narration, captions = depot_texts(a.depot)
        demos.append(mission_part(a.depot, 'nominal', title, narration, captions,
                                  film_camera=depot_camera(a.depot, getattr(a, 'depot_camera', None))))
        if not getattr(a, 'depot_swap', None) and (ROOT / 'docs/figures/qi_strip.png').is_file() and (RES / 'qi_summary.json').is_file():      # I-185: with the depot swap demo the QI result stays as a red row of the table only; v12: study QI (generated images through the frozen gate), a failed claim shown on purpose
            demos.append({'kind': 'card', 'seconds': 6, 'title': '今後の課題：写真に近い画像では見逃しが増える', 'layout': 'image',
                          'image': 'docs/figures/qi_strip.png', 'sub': 'シミュレーションの画像を画像生成AIで写真に近づけて試験（どちらも実写ではない）',
                          'narration': '写真に近い画像では、火の見逃しが増えました。ここは今後の課題です。', 'body': []})
    missions = [d for d in demos if d['kind'] == 'mission']
    for i, d in enumerate(missions, 1):
        d['index'], d['total'] = i, len(missions)
    parts += demos
    cards = ((evidence_card, EVIDENCE_S),) if getattr(a, 'summary_card', True) else ((campaign_e_table, 9), (t1_card, 8), (fix_card, 11))
    for card_fn, sec in cards:
        c = card_fn(sec if cs is None else max(cs, 20))      # I-184: the results table stays on screen long enough to be read
        if c:
            parts.append(c)
    report = 'docs/figures/operator_report_hidden_fire.png'      # I-18: what the robot leaves for the people on site
    parts.append({'kind': 'card', 'seconds': 5, 'title': 'RescueMind', 'sub': a.repo_url,
                  'image': report if (ROOT / report).is_file() else 'docs/figures/hero_gazebo.png',
                  'narration': '確かめて、見直して、迷ったら止まる。うまくいかなかった結果も公開しています。',
                  'body': ['確かめる・横から見直す・迷ったら止まる', '間違えて届けるより、止まる方がいい。',
                           '毎回、写真と理由と「次にすること」を1枚の現場報告に残す（右）。',
                           'コード・事前登録・全試行の証拠・再現用Dockerを公開しています。',
                           'ナレーション：VOICEVOX:四国めたん']})
    return parts


def fit_budget(a):
    """Apply the shortening steps in order until the estimate is within TARGET_S."""
    df = bool(a.fire and a.hidden_fire)    # --fire is dropped only when --hidden-fire replaces it
    de = bool(getattr(a, 'memory', None))   # with the memory demo, the empty-station demo (least novel) goes first
    steps = [dict(), dict(drop_arch=True), dict(drop_arch=True, drop_fire=df), dict(drop_arch=True, drop_fire=df, shrink=True),
             dict(drop_arch=True, drop_fire=df, shrink=True, drop_empty=de)]
    for s in steps:
        parts = build(a, **s)
        est = estimate(parts)
        if sum(x for _, x in est) <= TARGET_S:
            break
    return parts, est, s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--deliver', help='run id: paraphrased instruction -> delivery (v5: omitted, EVAL 9; the point is made in segment 1\'s caption)')
    ap.add_argument('--recover', required=True, help='run id: swapped supplies -> search other station -> delivery')
    ap.add_argument('--depot-swap', dest='depot_swap', help='run id (I-185): swapped supplies filmed in the realistic depot; replaces the arena --recover demo')
    ap.add_argument('--empty', help='run id: both stations empty -> check both, stop')
    ap.add_argument('--fire', help='run id: large fire -> stop without searching')
    ap.add_argument('--hidden-fire', dest='hidden_fire', help='run id: small partly hidden fire -> v3.6 check stops')
    ap.add_argument('--memory', help='run id: verified memory (I-15) goes straight to the remembered station, still checks')
    ap.add_argument('--depot', help='run id (I-21): a mission filmed in the realistic depot (scripts/film_depot.sh -> experiments/results/film_depot_runs.txt)')
    ap.add_argument('--depot-camera', default=None, help='overview camera SDF of the depot run (default: outputs/runs/<id>/film_camera.txt, written by film_depot.sh, else '
                    f'{DEPOT_CAMERA})')
    ap.add_argument('--advice', help='run id (I-19): injected "skip the check" advice on a hidden-fire world; replaces --hidden-fire')
    ap.add_argument('--three-tables', dest='summary_card', action='store_false',
                    help='old layout: E, T1 and fix tables instead of one evidence summary card')
    ap.add_argument('--repo-url', default='github.com/fe2131-art/rescue-mind')
    ap.add_argument('--out', default=str(ROOT / 'docs/video_plan.json'))
    a = ap.parse_args()
    if not a.empty:
        print('WARNING: no --empty run: the "欠品で停止" scene is missing', file=sys.stderr)
    parts, est, applied = fit_budget(a)
    total = sum(x for _, x in est)
    out = Path(a.out)
    out.write_text(json.dumps({'parts': parts}, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    print(out)
    print(f'shortening applied: {applied or "none"}')
    for p, x in est:
        label = p.get('title') if p['kind'] != 'mission' else f"demo {p['index']}/{p['total']} {p['title']} ({p['run_dir'][-16:]})"
        print(f"  {p['kind']:8s} {x:6.1f}s  {label}")
    print(f'estimated total: {total:.1f} s (limit {LIMIT_S:.0f} s)')
    if total > LIMIT_S:
        print('ERROR: estimate exceeds the limit', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
