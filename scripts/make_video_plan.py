#!/usr/bin/env python3
"""Write docs/video_plan.json (storyboard for make_demo_video.py) from real results — v3.6, <= 175 s.

  python3 scripts/make_video_plan.py --deliver <id> --recover <id> --empty <id> --fire <id> --hidden-fire <id>

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
G, R, W = (60, 200, 120), (240, 80, 80), (236, 241, 248)
LIMIT_S = 175.0      # assignment: 1-3 min
FAST, CHECK = 8.0, 3.0   # playback speed while driving / during the check motion (shown on screen per segment)
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
def evidence_card(seconds):
    """One summary card of the pre-registered evidence (replaces the three result tables; every number from files)."""
    rows, say = [], []
    led = RES / 'campaign_E_ledger.jsonl'
    if led.is_file():
        rs = [json.loads(x) for x in led.read_text(encoding='utf8').splitlines() if x.strip()]
        rs = [r for r in rs if r.get('final', True)]
        ok = sum(r['correct'] for r in rs)
        wrong = sum(r['observed_action'] in DELIVERED and r['expected_action'] not in ('ALLOW', 'DELIVER_AFTER_SEARCH') for r in rs)
        rows.append(['閉ループ E（ランダムな世界）', [f'期待どおり {ok}/{len(rs)}・誤配達 {wrong}', G if wrong == 0 else R]])
        say.append(f'ランダムな世界の{len(rs)}試行で、誤配達は{wrong}件。')
    g = jload(RES / 'g_summary.json')
    if g:
        pr = g['primary']
        rows.append(['閉ループ G（横から見直す）', [f"火が見えるのに配達 {pr['wrong_deliveries_B']}/{pr['n_world_pairs_fire_perceivable']} → "
                                                f"{pr['wrong_deliveries_C']}/{pr['n_world_pairs_fire_perceivable']}（p={pr['mcnemar_p']:.3f}）", G]])
        say.append(f"横から見直すと、火が見えるのに配達した回数は{pr['wrong_deliveries_B']}件から{pr['wrong_deliveries_C']}件。")
    h = jload(RES / 'h_summary.json')
    if h:
        p1, p2 = h['P1_efficiency_relocation_persist'], h['P2_safety_naive_vs_verified']
        t0, t2 = p1['time_M0_median_s'], p1['time_M2_median_s']
        speed = f"所要時間 {t0:.0f}→{t2:.0f}秒・" if t0 is not None and t2 is not None else ''
        p3 = h['P3_no_extra_risk_vs_v36']
        rows.append(['閉ループ H（記憶）', [f"{speed.replace('所要時間 ', '移されたまま8出動 ')}危険 記憶なし{p3['unsafe_M0']}・本方式{p3['unsafe_M2']}（素朴{p2['unsafe_M1']}）",
                                                  G if h['headline_supported'] else W]])
        say.append((f"出動をまたぐ記憶では、入れ替わりが続く出動の所要時間の中央値が、記憶なしの{t0:.0f}秒から{t2:.0f}秒。"
                    if t0 is not None and t2 is not None else '出動をまたぐ記憶では、')
                   + f"危険な配達は、記憶なしの{p3['unsafe_M0']}件に対して、本方式は{p3['unsafe_M2']}件。確認を省く素朴な記憶では{p2['unsafe_M1']}件でした。")
    j = jload(RES / 'j_summary.json')
    if j:
        c = j['per_config']
        j_ok = j['P1_runs_on_one_v100']['supported'] and j['P2_no_extra_unsafe']['supported'] and c['J']['unsafe_deliveries'] == 0
        rows.append(['閉ループ J（2つのAI）', [f"期待どおり {c['J']['correct']}/{c['J']['n']}（v3.6単独 {c['A']['correct']}/{c['A']['n']}）・危険な配達 {c['J']['unsafe_deliveries']}",
                                                      G if j_ok else R if c['J']['unsafe_deliveries'] > c['A']['unsafe_deliveries'] else W]])
    z = jload(RES / 'z_summary.json')
    if z:
        sg = z['models']['siglip']['t2']['baseline']
        rows.append(['比較 Z（CLIP系ゼロショット）', [f"未使用画像T2で SigLIP 誤許可 {sg['FA']}/{sg['n_deny']}（本手法 {z['models']['siglip']['t2']['ours']['FA']}）", G]])
    pp = jload(RES / 'p_summary.json')
    if pp:
        rows.append(['実写 P（D-Fire 400枚）', [f"火・煙を検出 {pp['recall']['k']}/{pp['recall']['n']}・火の無い写真で誤警報 {pp['false_alarm']['k']}/{pp['false_alarm']['n']}", W]])
        say.append(f"実写でも火と煙を{pp['recall']['k']}枚検出。ただし誤警報は多く、現場ごとの調整が必要です。")
    if not rows:
        return None
    return {'kind': 'table', 'seconds': seconds, 'title': '事前登録した評価のまとめ（全試行を公開）',
            'sub': '結果を見る前に条件と判定方法を固定。うまくいかなかった結果もそのまま報告',
            'narration': ''.join(say), 'header': ['評価', '結果'], 'rows': rows,
            'notes': ['すべてシミュレーション（実機なし）。数値は結果ファイルから自動生成。']}


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
    return {'kind': 'mission', 'scene': scene, 'title': title, 'run_dir': f'outputs/runs/{run_id}', 'fast': FAST, 'check_speed': CHECK,
            'narration': narration, 'captions': cap, **extra}


def build(a, drop_arch=False, drop_fire=False, shrink=False, drop_empty=False):
    cs = 0 if shrink else None      # shrink: result cards last exactly as long as their narration
    mem = bool(getattr(a, 'memory', None))
    # story arc of the first ~10 s: problem (stock list != scene, hazards hide) -> answer (look on the spot, look again from the side)
    open_say = ('災害時、在庫表と現場は違い、危険も隠れます。だから、その場で確かめ、横から見直し'
                + ('、記憶は提案だけにします。' if mem else 'ます。'))
    parts = [
        {'kind': 'card', 'seconds': 6, 'title': 'RescueMind', 'image': 'docs/figures/hero_gazebo.png',
         'sub': '在庫表と現場は食い違う。だから、現地で目で確かめる',
         'narration': open_say,
         'body': ['課題：災害時は、在庫表と現場が違う。火や煙が物資の陰に隠れていることもある。誤配達は命に関わる。',
                  '答え：拠点でその場の目（ローカルVLM Qwen3.5-9B）で確かめる → 正面で許可でも横から見直す'
                  + ' → 出動をまたぐ記憶は提案だけ。迷えば止まって報告。' if mem else
                  '答え：拠点でその場の目（ローカルVLM Qwen3.5-9B）で確かめる → 正面で許可でも横から見直す。迷えば止まって報告。',
                  f'※ 走行は{FAST:g}倍速、確認動作は{CHECK:g}倍速、AI判断の瞬間は等速。速度は常に画面左上に表示します。']}]
    if not drop_arch:
        parts.append({'kind': 'card', 'seconds': 6, 'title': 'システム構成', 'sub': 'すべてローカルGPUで完結（クラウドAPI不使用）',
                      'image': 'docs/figures/architecture.png', 'layout': 'image',
                      'narration': '推論はすべてローカルのGPU。車輪を動かせるのは、独立した安全ガードだけです。',
                      'body': ['VLMは選択式2問（選択肢の順序を入替）の回答文字の確率で判断 ／ 独立した速度ガードが車輪指令を常時監視']})
    demos = []
    if a.deliver:
        demos.append(mission_part(
            a.deliver, 'nominal', '言い換えた指示でも配達',
            {'go': '物資名のない依頼でも、AIが読み取って出発します。', 'check': '拠点で止まり、現物を目で確かめます。',
             'peek': '正面で許可が出ても、出発前に横から見直します。',
             'after': '安全を確かめたので、避難所へ向かいます。'},
            {'go': '「{instr}」物資名がなくても、AIが依頼を読み取って出発。',
             'check': '着いたらまず停止。新しい画像で現物を確かめる。',
             'peek': '正面で許可でも、出発前に左右0.4 mから見直す。物資の陰の火・煙を探す。',
             'after': '現物も横の様子も問題なし → 避難所Bへ（橙線＝実際の軌跡）。'}))
    if a.recover:
        demos.append(mission_part(
            a.recover, 'swapped', '取り違え → 別拠点を探索',
            {'go': '在庫表と現場が違います。物資が入れ替わっています。', 'search': '依頼の物資ではありません。もう一方を見に行きます。',
             'peek': '正しい物資です。念のため、横から見直します。',
             'after': '正しい物資を見つけたので、避難所へ届けます。'},
            {'go': '在庫表と現物が違う。「{instr}」', 'check': '拠点で現物を確かめている。',
             'search': '違う物資 → 誤配達せず、もう一方の拠点を見に行く。',
             'peek': '正しい物資でも、出発前に横から見直す。',
             'after': '別の拠点で正しい物資を確認 → 避難所Bへ。判断の経緯はすべて記録。'}))
    if a.empty and not drop_empty:
        demos.append(mission_part(
            a.empty, 'empty', '欠品 → 両拠点を確認して停止',
            {'go': '次は、在庫表にあるはずの物資が、どこにも無いケースです。', 'search': 'ここには有りません。もう一方も確かめます。',
             'after': 'どちらにも無いので、配達せず止まって報告します。'},
            {'go': '在庫表にあるはずの物資が、どの拠点にも無い。「{instr}」', 'check': '拠点で現物を確かめている。',
             'search': 'ここには無い → もう一方の拠点も確かめる。',
             'after': '両拠点とも無し → 誤配達せず、その場で止まって報告。'}))
    if a.fire and not drop_fire:
        demos.append(mission_part(
            a.fire, 'nominal', '大きな火災 → 探索せず停止',
            {'go': '続いて、拠点の裏で火災が起きているケースです。', 'after': '火と煙を見つけました。探し回らず、止まって報告します。'},
            {'go': '拠点の裏で火災が起きている。「{instr}」', 'check': '物資は正しい。でも画像に火や煙は無いか？',
             'after': '火・煙を検知 → 配達せず、探し回らずに止まって報告。'}, hazard_at='medicine'))
    if mem:
        demos.append({'kind': 'card', 'seconds': 5, 'title': '出動をまたぐ記憶', 'layout': 'image',
                      'image': 'docs/figures/memory_principle_ja.png', 'sub': '記憶は提案だけ。着いたら必ず、その場の目で確かめる',
                      'narration': '出動をまたぐ記憶は、提案だけ。着いたら、必ず確かめます。', 'body': []})
        demos.append(mission_part(
            a.memory, 'swapped', '出動をまたぐ記憶 → 直行',
            {'go': '前回の出動を覚えているので、その拠点へ直行します。', 'check': 'それでも、着いたら必ず確かめます。',
             'peek': '横からも見直します。', 'after': '記憶で近道をして、判断はその場の目で。'},
            {'go': '前回の出動を覚えている → 依頼物資のある拠点へ直行。「{instr}」',
             'check': '記憶は提案だけ。着いたら必ず現物を確かめる。',
             'peek': '横からの見直しも省かない。',
             'after': '探し回らずに配達。記憶が古ければ、確認で止まる（評価H）。'}))
        if (ROOT / 'docs/figures/memory_case_ja.png').is_file():
            demos.append({'kind': 'card', 'seconds': 5, 'title': '記憶が慎重さを足した例（評価H）', 'layout': 'image',
                          'image': 'docs/figures/memory_case_ja.png', 'sub': '記憶なしでは見逃した火で、記憶ありは止まった',
                          'narration': '火を覚えていた拠点では、閾値を厳しくして、見逃しを防ぎました。', 'body': []})
    if a.hidden_fire:
        demos.append(mission_part(
            a.hidden_fire, 'nominal', '隠れた小さな火 → 停止',
            {'go': '最後は、物資の陰に小さな火が隠れているケースです。', 'peek': '正面では見えません。横に回り込んで、見直します。',
             'after': '横から火を見つけました。配達せず、止まって報告します。'},
            {'go': '物資の陰に小さな火。正面からは見えない。「{instr}」',
             'check': '物資は正しい。でも陰に火や煙は無いか？',
             'peek': '正面は「許可」。でも陰は見えない → 左右0.4 mから見直す。',
             'after': '横から火を発見 → 正面の許可を取り消して停止・報告。'}))
    missions = [d for d in demos if d['kind'] == 'mission']
    for i, d in enumerate(missions, 1):
        d['index'], d['total'] = i, len(missions)
    parts += demos
    cards = ((evidence_card, 14),) if getattr(a, 'summary_card', True) else ((campaign_e_table, 9), (t1_card, 8), (fix_card, 11))
    for card_fn, sec in cards:
        c = card_fn(sec if cs is None else cs)
        if c:
            parts.append(c)
    report = 'docs/figures/operator_report_hidden_fire.png'      # I-18: what the robot leaves for the people on site
    parts.append({'kind': 'card', 'seconds': 5, 'title': 'RescueMind', 'sub': a.repo_url,
                  'image': report if (ROOT / report).is_file() else 'docs/figures/hero_gazebo.png',
                  'narration': '確かめて、見直して、迷ったら止まる。全試行の証拠を公開しています。',
                  'body': ['確かめて、見直して、迷ったら止まる。間違った配達より、止まる方がいい。',
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
    ap.add_argument('--deliver', required=True, help='run id: paraphrased instruction -> delivery')
    ap.add_argument('--recover', required=True, help='run id: swapped supplies -> search other station -> delivery')
    ap.add_argument('--empty', help='run id: both stations empty -> check both, stop')
    ap.add_argument('--fire', help='run id: large fire -> stop without searching')
    ap.add_argument('--hidden-fire', dest='hidden_fire', help='run id: small partly hidden fire -> v3.6 check stops')
    ap.add_argument('--memory', help='run id: verified memory (I-15) goes straight to the remembered station, still checks')
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
