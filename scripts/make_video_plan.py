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
    notes = ['対策：危険の質問に「小さい・隠れた・端で切れた火や煙」を明記し、3つの拡大切り出しでも尋ねる（開発データのみで選定）。']
    j = sel.get('selected') or {}
    if j.get('config', '').startswith('J2(') or 'Clef' in j.get('config', ''):
        notes.append(f"評価した：Cloudflare Clef-Flash を当初計画の「Jev」の役割（2つ目のAI）で組み合わせ（見逃し {j['n_dh_fire'] - j['dh_fire_refused']}/{nf}）。"
                     f"ただし{j['vram_gb']:.0f} GB で V100 に同時搭載できず、搭載はしていない。")
        say.append('二つ目のAI、クレフフラッシュも評価しました。')
    return {'kind': 'table', 'seconds': seconds, 'title': '残る弱点への対策（v3.6）',
            'sub': '開発データだけで選定 → 未使用データと閉ループで確認', 'narration': ''.join(say),
            'header': ['指標', '従来 v3.5', 'v3.6（問い方＋切り出し）'], 'rows': rows, 'notes': notes}


# ------------------------------------------------------------------ duration estimate
def mission_seconds(spec):
    """Mission segment length, computed the way make_demo_video.mission_segment builds its speed plan
    (falls back to the ground-truth log when the run has no film frames, e.g. stand-in runs)."""
    try:
        sys.path.insert(0, str(ROOT / 'scripts'))
        sys.path.insert(0, str(ROOT))
        import make_demo_video as mdv
        run = mdv.load_run(ROOT / spec['run_dir'])
        ev, eps = run['events'], mdv.checkpoint_episodes(run)
        f0 = run['film'][0][0] if run['film'] else run['mission']['mission_start_unix_ns']
        f1 = run['film'][-1][0] if run['film'] else run['truth'][-1][0]
        t0 = f0 + int(spec.get('skip_s', 0.5) * 1e9)
        t1 = min(f1, (ev.get('shelter_approach') or (eps[-1]['end'] if eps else f1)) + int(spec.get('tail_s', 2.0) * 1e9))
        fast, slow, cur, segs = spec.get('fast', 3.0), spec.get('check_speed', 2.0), t0, []
        for e in eps:
            a = (e['arrive'] or e['frame']) - int(1.0e9)
            fr = e['frame'] or a
            d1, b = e['decision_t'] + int(1.5e9), e['end'] + int(0.8e9)
            segs += [(cur, a, fast), (a, fr, slow), (fr, d1, 1.0), (d1, b, slow)]
            cur = b
        segs.append((cur, t1, fast if 'shelter_approach' in ev else 1.0))
        video = sum(max(0.0, (sb - sa) / 1e9 / sp) for sa, sb, sp in segs)
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
    return {'kind': 'mission', 'scene': scene, 'title': title, 'run_dir': f'outputs/runs/{run_id}', 'fast': 4.0,
            'narration': narration, 'captions': cap, **extra}


def build(a, drop_arch=False, drop_fire=False, shrink=False):
    cs = 0 if shrink else None      # shrink: result cards last exactly as long as their narration
    parts = [
        {'kind': 'card', 'seconds': 6, 'title': 'RescueMind', 'image': 'docs/figures/hero_gazebo.png',
         'sub': '現地で「目で確かめてから」届ける災害物資ロボット',
         'narration': 'レスキューマインド。届ける前に、現地で目で確かめる災害物資ロボットです。',
         'body': ['拠点で止まり、現物をローカルVLM（Qwen3.5-9B）で確認。違えば別の拠点を探し、危険なら止まって報告。',
                  'ROS 2 × Gazebo の実レンダリング映像（俯瞰カメラ＋ロボット搭載カメラ）。',
                  '※ 走行は4倍速、確認動作は2倍速、AI判断の瞬間は等速。速度は常に画面左上に表示します。']}]
    if not drop_arch:
        parts.append({'kind': 'card', 'seconds': 6, 'title': 'システム構成', 'sub': 'すべてローカルGPUで完結（クラウドAPI不使用）',
                      'image': 'docs/figures/architecture.png', 'layout': 'image',
                      'narration': '推論はローカルのGPUだけ。車輪への指令は、独立した安全ガードだけが出せます。',
                      'body': ['VLMは選択式2問（選択肢の順序を入替）の回答文字の確率で判断 ／ 独立した速度ガードが車輪指令を常時監視']})
    demos = []
    if a.deliver:
        demos.append(mission_part(
            a.deliver, 'nominal', '言い換えた指示でも配達',
            {'go': '物資の名前が無い依頼も、言語モデルが解釈して出発します。', 'check': '拠点で止まり、カメラ画像をAIが確認します。',
             'after': '確信できたので、避難所へ向かいます。'},
            {'go': '「{instr}」——物資名の無い指示も、ローカルLLMが依頼内容を解釈して出発。',
             'check': '拠点で静止し、新しいカメラ画像をVLMに2つの選択式質問で確認させます。',
             'after': '2問とも依頼物資を高確信で確認 → 許可。避難所Bへ（オレンジ線＝Gazebo真値の軌跡）。'}))
    if a.recover:
        demos.append(mission_part(
            a.recover, 'swapped', '取り違え → 別拠点を探索',
            {'go': '次は、水と救急箱が入れ替わっているケースです。', 'search': '依頼の物資ではありません。もう一方の拠点を確認しに行きます。',
             'after': '正しい物資を見つけたので、避難所へ届けます。'},
            {'go': '在庫情報と現物が食い違うケース。「{instr}」', 'check': '拠点で現物を確認中……',
             'search': '依頼の物資ではない → 止まらずに、もう一方の拠点を確認しに行きます。',
             'after': '別拠点で依頼物資を確認 → 許可して避難所Bへ。判断の経緯はすべて記録・監査されます。'}))
    if a.empty:
        demos.append(mission_part(
            a.empty, 'empty', '欠品 → 両拠点を確認して停止',
            {'go': 'つぎは、両方の拠点が空のケースです。', 'search': 'ここには有りません。もう一方も確認します。',
             'after': 'どちらにも無いので、配達せず停止して報告します。'},
            {'go': '在庫表では有るはずの物資が、どの拠点にも無いケース。「{instr}」', 'check': '拠点で現物を確認中……',
             'search': '依頼の物資が無い → もう一方の拠点も確認しに行きます。',
             'after': '両拠点とも依頼物資なし → 誤った物資は運ばず、その場で停止して状況を報告します。'}))
    if a.fire and not drop_fire:
        demos.append(mission_part(
            a.fire, 'nominal', '大きな火災 → 探索せず停止',
            {'go': '続いて、拠点の裏で火災が起きているケースです。', 'after': '火と煙を検知しました。探し回らずに停止して報告します。'},
            {'go': '拠点の裏で火災が起きているケース。「{instr}」', 'check': '物資は正しいが、画像の中に火や煙は無いか？',
             'after': '火災・煙を検知 → 拒否。危険な場所を探し回らず停止し、状況を報告します。'}, hazard_at='medicine'))
    if a.hidden_fire:
        demos.append(mission_part(
            a.hidden_fire, 'nominal', '隠れた小さな火 → 停止',
            {'go': '最後は、物資の陰に小さな火が隠れているケースです。', 'after': '小さな火も見逃さず、配達せずに停止します。'},
            {'go': '物資の陰に小さな火が隠れているケース。「{instr}」',
             'check': '物資は正しい。だが物資の陰や画面の端に、小さな火や煙は無いか？',
             'after': '危険の質問文＋拡大切り出し（v3.6）で火・煙を検知 → 拒否。配達せず停止して報告します。'}))
    for i, d in enumerate(demos, 1):
        d['index'], d['total'] = i, len(demos)
    parts += demos
    for card_fn, sec in ((campaign_e_table, 9), (t1_card, 8), (fix_card, 11)):
        c = card_fn(sec if cs is None else cs)
        if c:
            parts.append(c)
    parts.append({'kind': 'card', 'seconds': 5, 'title': 'RescueMind', 'sub': a.repo_url, 'image': 'docs/figures/hero_gazebo.png',
                  'narration': 'AIが間違えるとき、ロボットは動かない。コードと全試行の証拠を公開しています。',
                  'body': ['AIが間違えるとき、ロボットは動かない。無ければ探し、危険なら止まる。',
                           'コード・事前登録・全試行の証拠・再現用Dockerを公開しています。',
                           'ナレーション：VOICEVOX:四国めたん']})
    return parts


def fit_budget(a):
    """Apply the shortening steps in order until the estimate is within TARGET_S."""
    df = bool(a.fire and a.hidden_fire)    # --fire is dropped only when --hidden-fire replaces it
    steps = [dict(), dict(drop_arch=True), dict(drop_arch=True, drop_fire=df), dict(drop_arch=True, drop_fire=df, shrink=True)]
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
