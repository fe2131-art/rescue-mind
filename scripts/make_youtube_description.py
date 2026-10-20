#!/usr/bin/env python3
"""Regenerate the YouTube description and the video paragraph of the submission notes from the rendered video.

Single source of truth for the video structure: docs/video_chapters.json (written by scripts/make_demo_video.py).
Numbers come from experiments/results/*summary*.json and the campaign_E ledger; a study whose result file does
not exist is omitted (a public description never says "running").

  python3 scripts/make_youtube_description.py            # rewrite docs/YOUTUBE_DESCRIPTION.md and docs/SUBMISSION.md
  python3 scripts/make_youtube_description.py --check    # exit 1 if either file is out of date
  python3 scripts/make_youtube_description.py --snapshot # submission snapshot -> docs/snapshot/YOUTUBE_DESCRIPTION.md (tracked files untouched)

--snapshot (or SNAPSHOT=1): a closing line names the registered studies that were not run at submission ("登録済み・提出時点で未実施"),
so the text reads as finished; their numbers are still omitted.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
if '--snapshot' in sys.argv:      # submission snapshot (read before advice_numbers is imported)
    os.environ['SNAPSHOT'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parent))
import youtube_chapters  # noqa: E402  (YouTube-valid chapters: merge short segments, validate)
import advice_numbers  # noqa: E402  (study V wording: single source shared with the README and the report)

ROOT = Path(__file__).resolve().parents[1]
SAFE = ('ALLOW', 'DELIVER_AFTER_SEARCH')        # expected actions for which a delivery is correct
DELIVERED = ('ALLOW', 'ALLOW_AFTER_SEARCH', 'ALLOW_MEMORY')
V_START, V_END = '<!-- VIDEO:START -->', '<!-- VIDEO:END -->'
VIDEO_FILE = 'outputs/video/PAI最終課題_tetsutetsu.mp4'

# Longer wording for a demo, used only when the chapter title (without "デモN：") matches exactly.
GLOSS = {
    '取り違え → 別拠点を探索': '物資の取り違え → 別の拠点を探索して配達',
    '隠れた小さな火 → 停止': '物資の陰に隠れた小さな火 → 正面では見えないが、横から見て検知して停止',
}


# ------------------------------------------------------------------ video structure
def mmss(sec):
    s = int(sec)                                   # chapter marks: floor, like YouTube's own player
    return f'{s // 60}:{s % 60:02d}'


def strip_demo(title):
    return re.sub(r'^デモ\s*\d+\s*[：:]\s*', '', title).strip()


def circled(i):
    return chr(0x2460 + i) if i < 20 else f'({i + 1})'


def video_facts(chapters):
    if not chapters:
        raise ValueError('no chapters')
    chapters = youtube_chapters.merge_short(chapters)      # idempotent: a list that is already valid is returned unchanged
    total = chapters[-1]['end_s']
    missions = [c for c in chapters if c.get('kind') == 'mission']
    speeds = []
    for c in missions:
        if c.get('speed') and c['speed'] not in speeds:
            speeds.append(c['speed'])
    warn = []
    if not 60 <= total <= 180:
        warn.append(f'video length {total:.1f}s is outside the 1-3 minute requirement')
    warn += youtube_chapters.validate(chapters)
    return {'chapters': chapters, 'total_s': total, 'length_mmss': mmss(round(total)),
            'length_ja': f'{int(round(total)) // 60}分{int(round(total)) % 60}秒',
            'missions': missions, 'speeds': speeds,
            'n_tables': sum(c.get('kind') == 'table' for c in chapters), 'warnings': warn}


def demo_sentence(facts):
    ms = facts['missions']
    if not ms:
        return None
    items = []
    for i, c in enumerate(ms):
        t = strip_demo(youtube_chapters.demo_title(c))
        items.append(f'{circled(i)}{GLOSS.get(t, t)}')
    return f'デモは{len(ms)}場面：' + ' '.join(items) + '。'


def speed_sentence(facts, short=False):
    sp = facts['speeds']
    if not facts['missions']:
        return None
    if not sp:
        return None
    if len(sp) == 1:
        m = re.fullmatch(r'走行([\d.]+)倍速・確認動作([\d.]+)倍速・AI判断の瞬間は等速', sp[0])
        if m and not short:
            body = f'走行区間は{m[1]}倍速、確認動作は{m[2]}倍速、AI判断の瞬間（画像取得〜判断）は等速です'
        else:
            body = sp[0] + ('' if short else 'です')
    else:
        body = '、'.join(f"{circled(i)}{c['speed']}" for i, c in enumerate(facts['missions']) if c.get('speed'))
        body += ('' if short else 'です')
    return body if short else f'※ 倍速表示：{body}（速度は動画内の左上に常時表示）。'


# ------------------------------------------------------------------ pre-registered numbers
def jload(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf8'))
    except (OSError, ValueError):
        return None


def line_e(res):
    f = Path(res) / 'campaign_E_ledger.jsonl'
    if not f.is_file():
        return None
    rows = [json.loads(x) for x in f.read_text(encoding='utf8').splitlines() if x.strip()]
    rows = [r for r in rows if r.get('final', True)]
    if not rows:
        return None
    n = len(rows)
    ok = sum(bool(r['correct']) for r in rows)
    wrong = sum(r.get('observed_action') in DELIVERED and r['expected_action'] not in SAFE for r in rows)
    return f'・ランダムな世界での閉ループ{n}試行：期待どおりの行動 {ok}/{n}、誤った物資・火災のある拠点からの配達 {wrong}件'


def line_t1(res):
    t = jload(Path(res) / 't1_summary.json')
    try:
        m = t['models']['Qwen3.5-9B']
        fa, n = m['rules']['full']['false_approvals'], m['rules']['full']['n_deny']
        fa35 = m['rules']['v35_tau_h_0.05']['false_approvals']
        return (f"・未使用の画像{m['n_images']}枚（T1）：拒否すべき{n}枚のうち誤許可 {fa}枚（登録した規則 v3.4）、{fa35}枚（v3.5の規則）。"
                f'すべて「物資の陰に一部しか見えない火」の型で、これが残る弱点と判明')
    except (TypeError, KeyError):
        return None


def line_g(res):
    g = jload(Path(res) / 'g_summary.json')
    try:
        pr, c = g['primary'], g['per_config']['C']
        n = pr['n_world_pairs_fire_perceivable']
        return (f"・その対策（v3.6、横から見直す）の閉ループ評価G：3視点（正面・左右0.4 m）のどれかで火が見えた{n}世界で、"
                f"火があるのに配達した回数 {pr['wrong_deliveries_B']}/{n} → {pr['wrong_deliveries_C']}/{n}"
                f"（McNemar正確検定 p={pr['mcnemar_p']:.3f}）、火の無い世界での誤った停止 {c['false_hazard_stops']}/{c['fire_free_trials']}。"
                f'これらの火の多くは設計上、正面からは見えにくい（または見えない）ため、これは「横から見る効果」の測定である')
    except (TypeError, KeyError):
        return None


def line_t2(res):
    t = jload(Path(res) / 't2_summary.json')
    try:
        r = t['results']
        sel = r[t['selected']]
        ref = r[t['reference']]
        s = f"・未使用の画像600枚（T2）：誤許可 {sel['false_approvals']}/{sel['n_deny']}"
        if ref['false_approvals'] == sel['false_approvals'] == 0:
            s += '（v3.5でも同じで天井のため、改善は測れない）'
        clef = r.get('J2(Clef-task) tau_h=0.05')
        if clef:
            s += f"。Jev役のローカルAI Clef-Flash 単独でも {clef['false_approvals']}/{clef['n_deny']}"
        return s
    except (TypeError, KeyError):
        return None


def line_z(res):
    z = jload(Path(res) / 'z_summary.json')
    try:
        t = z['models']['siglip']['t2']
        o = t['ours']
        parts = [f"本方式 誤許可 {o['FA']}/{o['n_deny']}・正しい許可 {o['CA']}/{o['n_allow']}"]
        for key, name in (('siglip', 'SigLIP'), ('clip', 'CLIP')):
            b = z['models'][key]['t2']['baseline']
            parts.append(f"{name} {b['FA']}/{b['n_deny']}・{b['CA']}/{b['n_allow']}")
        return '・生成しないゼロショット基準（評価Z、未使用600枚T2、誤許可・正しい許可）：' + '、'.join(parts)
    except (TypeError, KeyError):
        return None


def line_r(res):
    r = jload(Path(res) / 'r_summary.json')
    try:
        p1 = r['P1_pooled']
        cas = [c['correct_approvals'] for c in r['conditions'].values()]
        s = (f"・画質の劣化{len(r['conditions'])}条件（ノイズ・ぼけ・露出・JPEG）での評価R：延べ{p1['n']}枚で誤許可 {p1['false_approvals']}件、"
             f"正しい許可は条件ごとに {min(cas)}〜{max(cas)}/{r['n_allow']}（劣化なし {r['clean']['correct_approvals']}/{r['n_allow']}）")
        return s
    except (TypeError, KeyError, ValueError):
        return None


def line_p(res):
    p = jload(Path(res) / 'p_summary.json')
    try:
        rc, fa = p['recall'], p['false_alarm']
        s = f"・実写（D-Fire {p['n']}枚）の評価P（閾値は凍結）：火・煙のある写真の検出 {rc['k']}/{rc['n']}、火の無い写真で誤警報 {fa['k']}/{fa['n']}"
        if fa['k'] / fa['n'] >= 0.2:
            s += ''
        p2 = jload(Path(res) / 'p2_summary.json')
        try:      # P2: threshold calibrated on site photographs, tested on unseen ones
            ct = p2['chosen_test']
            s += (f"。現場の写真で閾値を較正した評価P2：未使用の写真で検出 {ct['recall']['k']}/{ct['recall']['n']}、"
                  f"誤警報 {ct['false_alarm']['k']}/{ct['false_alarm']['n']}（基準{'成立' if p2['claim_supported'] else '不成立'}）")
        except (TypeError, KeyError):
            pass
        return s
    except (TypeError, KeyError, ZeroDivisionError):
        return None


def line_l(res):
    l = jload(Path(res) / 'l_summary.json')
    try:
        pl = l['primary']
        return (f"・未知の配置24通りでの閉ループ評価L：期待どおり {pl['expected_behaviour']}、危険な配達 {pl['unsafe_deliveries']}件"
                f"（基準{'成立' if pl['claim_supported'] else '不成立'}）")
    except (TypeError, KeyError):
        return None


def line_h(res):
    h = jload(Path(res) / 'h_summary.json')
    try:
        p1, p2 = h['P1_efficiency_relocation_persist'], h['P2_safety_naive_vs_verified']
        pa, p3 = h['per_arm'], h['P3_no_extra_risk_vs_v36']
        rc = {a: pa[a]['by_transition']['relocation_change']['time_median_s'] for a in ('M0', 'M2')}
        t = (f"所要時間の中央値は、物資が移されたままの{p1['n_pairs']}出動で 記憶なし {p1['time_M0_median_s']:.0f}秒・検証つき記憶 {p1['time_M2_median_s']:.0f}秒"
             f"（物資が元に戻った出動では {rc['M0']:.0f}秒 対 {rc['M2']:.0f}秒と遅い（遠回りの代償）。全体は {pa['M0']['time_median_s']:.0f}→{pa['M2']['time_median_s']:.0f}秒）。"
             if p1['n_pairs'] else '')
        return (f"・出動をまたぐ記憶の評価H：{t}"
                f"危険な配達は {p2['n_pairs']}出動のうち、確認を省く素朴な記憶 {p2['unsafe_M1']}件（省く設計の比較）、記憶なし {p3['unsafe_M0']}件、検証つき記憶 {p2['unsafe_M2']}件")
    except (TypeError, KeyError, ValueError):
        return None


def line_v(res):
    """Study V (random change): the failed memory claim is stated next to the supported model claim."""
    f = advice_numbers.v_facts()
    if not f:
        return None
    t = (f"・ランダムな変化での再検証V：時間差 {f['diff']:.0f}秒（登録した予測区間 {f['pred_lo']:.0f}〜{f['pred_hi']:.0f}秒の内側）でモデルの予測は{'成立' if f['model_claim'] else '不成立'}、"
         f"危険な配達は 記憶なし {f['unsafe']['M0']}・素朴な記憶 {f['unsafe']['M1']}・検証つき記憶 {f['unsafe']['M2']}件。")
    if not f['memory_claim']:
        t += (f"「記憶は安全」の主張は不成立（余裕の条件は成立、系列単位の検定 p={f['mcnemar_p']:.4f}、10系列では検出力不足。1件は確認の誤り）。失敗として記録")
    return t


def line_a(res):
    """Study A (hostile advice, closed loop): the headline and the steering cost, one line."""
    t = advice_numbers.a_short_ja()
    return f"・悪意のある助言の評価A（226試行）：{t}" if t else None


def line_if(res):
    """Study IF (request text switching the supply): a failed registered claim, stated with its countermeasure status."""
    t = advice_numbers.if_short_ja()
    return f"・{t}。依頼物資は保証の外なので、出発前に運用者が解析結果を読み返す運用を必須としている" if t else None


def line_w(res):
    """Study W (image level), short: bound claim, prior-art separation (failed), I-20 decision."""
    f = advice_numbers.w_facts()
    if not f:
        return None
    ok = lambda x: '成立' if x else '不成立'
    up = 100 * f['la']['ci95'][1]
    xd = advice_numbers.xd_facts()
    i20 = ('採用規則を満たしたが、倉庫の評価XDの撤回規則で既定にしない' if xd else '採用規則を満たす') if f['adopt'] else '採用しない'
    return (f"・画像評価W：見逃し 正面のみ{f['front']['k']}/{f['front']['n']}→見回し{f['la']['k']}/{f['la']['n']}（上限{up:.1f}%、{ok(f['claim_eps'])}）。"
            f"先行手法との区別は{ok(f['n_dist'] > 0)}（{f['n_dist']}/3）。I-20は{i20}")


def line_xd(res):
    """Studies XD (depot images) and Q (real photographs): failed registered claims stated with their numbers."""
    xd, q = advice_numbers.xd_ja(), advice_numbers.q_ja()
    return '\n'.join(('・' + t) for t in (xd, q) if t) or None


def line_gr(res):
    """Study GR (the look-around in closed loop on fresh worlds): numbers from the result file; empty until it exists."""
    g = jload(Path(res) / 'gr_summary.json')
    try:
        v, f, pool = g['arms']['v36']['fire'], g['arms']['front']['fire'], g['criteria']['pooled_with_G_v36']
        return (f"・見回しの閉ループ再現（評価GR、新しい{g['n_fire_worlds']}世界・{g['n_planned']}試行）：火へ配達 見回しあり {v['k']}/{v['n']}（95%上限 {v['upper95_exact'] * 100:.1f}%）、なし {f['k']}/{f['n']}。"
                f"画像評価Wの2%より高く、Gと合わせて {pool['k']}/{pool['n']}（上限 {pool['upper95_exact'] * 100:.1f}%）")
    except (TypeError, KeyError):
        return ''


def line_gc(res):
    """Study GC (a per-site calibrated hazard threshold in closed loop): numbers from the result file; empty until it exists."""
    g = jload(Path(res) / 'gc_summary.json')
    try:
        c, v = g['arms']['cal']['fire'], g['arms']['v36']['fire']
        return (f"・サイトで較正した閾値の閉ループ評価（評価GC、新しい{g['n_fire_worlds']}世界・{g['n_planned']}試行）：火へ配達 較正 {c['k']}/{c['n']}（95%上限 {c['upper95_exact'] * 100:.1f}%）、既定 {v['k']}/{v['n']}、"
                f"火のない世界の誤停止 {g['arms']['cal']['fire_free']['k']}/{g['arms']['cal']['fire_free']['n']}")
    except (TypeError, KeyError):
        return ''


def line_gd(res):
    """Study GD (the calibrated threshold at the depot, closed loop): numbers from the result file; empty until it exists."""
    g = jload(Path(res) / 'gd_summary.json')
    try:
        c, v = g['arms']['cal']['fire'], g['arms']['v36']['fire']
        return (f"・較正の手順を2か所目（倉庫）で検証（評価GD、新しい{g['n_fire_worlds']}世界・{g['n_planned']}試行）：火へ配達 較正 {c['k']}/{c['n']}（95%上限 {c['upper95_exact'] * 100:.1f}%）、既定 {v['k']}/{v['n']}、"
                f"火のない世界の誤停止 {g['arms']['cal']['fire_free']['k']}/{g['arms']['cal']['fire_free']['n']}")
    except (TypeError, KeyError):
        return ''


def line_y(res):
    """Studies Y (continue after a hazard refusal, opt-in flag), YE (its exposure price) and YF (Y on fresh worlds): numbers from the result files."""
    yj, yej, yfj = (jload(Path(res) / f) for f in ('y_summary.json', 'ye_summary.json', 'yf_summary.json'))
    try:
        lv = yj['Y-s']['lost_vs_control']['scrutiny_hc']
        t = (f"・拒否のあとも探索を続ける任意のフラグ（評価Y、{yj['n_planned']}試行）：助言が火の拠点を指しても、scrutiny＋フラグの失う配達は "
             f"{lv['fire_worlds']['lost'] + lv['clean_worlds']['lost']}/{lv['fire_worlds']['pairs'] + lv['clean_worlds']['pairs']}（Xでは配達を失った）。tighten-onlyは火へ配達する世界が残る（知覚の見逃し）")
        if yej:
            h = yej['arms']['hc']
            t += f"。代償は露出（評価YE）：2つ目の火が隠れていると、フラグ付きで火へ配達 {h['unsafe_deliveries']['k']}/{h['unsafe_deliveries']['n']}（フラグなし 0/{yej['arms']['v36']['n']}）"
        if yfj:
            yl = yfj['Y-s']['lost_vs_control']['scrutiny_hc']
            t += (f"。新しい世界での再現（評価YF、{yfj['n_planned']}試行）：可用性は再現したが、scrutiny は火のない現場で配達を失った {yl['fire_worlds']['lost'] + yl['clean_worlds']['lost']}/{yl['fire_worlds']['pairs'] + yl['clean_worlds']['pairs']}（主張YF4は不成立）")
        return t
    except (TypeError, KeyError):
        return None


def line_j(res):
    j = jload(Path(res) / 'j_summary.json')
    try:
        c = j['per_config']
        return (f"・2つのAI構成（Jev役＋Qwen）の閉ループ評価J：期待どおり {c['J']['correct']}/{c['J']['n']}"
                f"（v3.6単独 {c['A']['correct']}/{c['A']['n']}）、危険な配達 {c['J']['unsafe_deliveries']}件（v3.6単独 {c['A']['unsafe_deliveries']}件）")
    except (TypeError, KeyError):
        return None


def headline_block(res):
    """First-screen summary for a busy judge: problem, what is new, three numbers in plain words, what to watch."""
    res = Path(res)
    out = ['【問題】災害時の物資配達ロボットは、在庫表と現物の食い違い（水のはずが救急箱・空）や火災に出会う。指示どおり運ぶだけでは、誤った物資や危険な場所へ届けてしまう。',
           '【新しさ】自分で見ていない情報（記憶・他のロボット・依頼文・在庫表）は「助言」とし、順序を変えるか判断を厳しくするだけにする。どんな助言でも危険な配達は確認自身の誤差の予算内（命題2、z3 で機械検証）。嘘を毎回つく情報源の代償は信用枠で上限（合成モデルの記述、閉ループ未確認）。']
    nums = []
    f = res / 'campaign_E_ledger.jsonl'
    if f.is_file():
        rows = [json.loads(x) for x in f.read_text(encoding='utf8').splitlines() if x.strip()]
        rows = [r for r in rows if r.get('final', True)]
        if rows:
            n = len(rows)
            ok = sum(bool(r['correct']) for r in rows)
            wrong = sum(r.get('observed_action') in DELIVERED and r['expected_action'] not in SAFE for r in rows)
            nums.append(f'①ランダムに作った{n}個の世界で、期待どおりの行動 {ok}/{n}、誤った物資・火のある拠点からの配達 {wrong}件')
    g = jload(res / 'g_summary.json')
    try:
        pr, c = g['primary'], g['per_config']['C']
        n = pr['n_world_pairs_fire_perceivable']
        nums.append(f"②隠れた火のある{n}世界で、正面だけで判断すると火の拠点へ配達 {pr['wrong_deliveries_B']}回、横から撮り直すと {pr['wrong_deliveries_C']}回"
                    f"（火の無い世界での誤停止 {c['false_hazard_stops']}/{c['fire_free_trials']}、偶然とは考えにくい p={pr['mcnemar_p']:.3f}）。"
                    f'火は設計上、正面から見えにくく、測っているのは「横から見る効果」')
    except (TypeError, KeyError):
        pass
    h = jload(res / 'h_summary.json')
    try:
        p1, p3 = h['P1_efficiency_relocation_persist'], h['P3_no_extra_risk_vs_v36']
        nums.append(f"③記憶で先に向かう拠点を決めると、物資が移されたままの{p1['n_pairs']}出動で所要時間（中央値）{p1['time_M0_median_s']:.0f}秒→{p1['time_M2_median_s']:.0f}秒（全{p3['n_pairs']}出動 {h['per_arm']['M0']['time_median_s']:.0f}→{h['per_arm']['M2']['time_median_s']:.0f}秒）。"
                    f"確認は省かないので危険な配達は 記憶なし {p3['unsafe_M0']}/{p3['n_pairs']}・記憶つき {p3['unsafe_M2']}/{p3['n_pairs']}。元に戻った出動は遠回りで遅い。"
                    + (advice_numbers.pooled_memory_short_ja() if advice_numbers.pooled_memory() else ''))
    except (TypeError, KeyError):
        pass
    if nums:
        out.append('【3つの数字】（すべてシミュレーション。条件は結果を見る前に固定）\n' + '\n'.join(nums))
    return out


def line_pending(res):
    """Snapshot only: the registered studies without results, in one line (the description otherwise omits them)."""
    if not advice_numbers.snapshot_mode():
        return ''
    ks = advice_numbers.pending_list()
    return (f"・{advice_numbers.PENDING_JA}：{'・'.join(ks)}（数値なし）" if ks else '')


def number_lines(res):
    fns = (line_t1, line_t2, line_z, line_r, line_p, line_l, line_h, line_v, line_w, line_xd, line_a, line_y, line_gr, line_gc, line_gd, line_if, line_j, line_pending)
    return [x for x in (f(res) for f in fns) if x]


# ------------------------------------------------------------------ documents
DROP_ORDER = ('（T2）', 'ゼロショット', '劣化', '評価J', '評価P', '（T1）')     # detail lines dropped first when over YouTube's 5000 characters
DROP_ORDER_SNAP = ('閉ループ評価L',)      # snapshot only: the extra "not run at submission" line needs the room
LIMIT = 4900      # YouTube's limit is 5000 CHARACTERS (not bytes); a margin of 100 characters


def watch_sentence(facts):
    """What to watch, from the demos actually in the video (never a demo that is not there)."""
    titles = ' '.join(c['title'] for c in facts['chapters'])
    parts = []
    if '隠れた' in titles:
        parts.append('「隠れた小さな火」のデモ（正面では見えない火を、横へ動いて撮り直して見つけて止まる）')
    if '記憶' in titles:
        parts.append('「記憶」のデモ（前回見た拠点へ直行し、着いたら必ず確かめる）')
    if '確認不要' in titles:
        parts.append('「確認不要」と言われても確認するデモ（言われたまま信じず、横から見て火を見つけて止まる）')
    if '取り違え' in titles:
        parts.append('「取り違え」のデモ（違う物資なら別の拠点を探す）')
    if '欠品' in titles:
        parts.append('「欠品」のデモ（どこにも無ければ止まって報告する）')
    return '【動画で見てほしい点】' + '、'.join(parts) + '。' if parts else ''


def build_description(chapters, res, _nums=None):
    facts = video_facts(chapters)
    head = (f"**ファイル**：`{VIDEO_FILE}`（1920×1080, 30fps, 約{facts['length_ja']}"
            f"（`docs/video_chapters.json` の終端 {facts['total_s']:g} 秒）、日本語ナレーション付き）")
    paras = [
        '# YouTube 投稿用テキスト（コピーして使用）', head,
        '## タイトル\nPAI最終課題_tetsutetsu',
        '## 概要欄\n'
        'RescueMind：現地で「目で確かめてから」届ける災害物資ロボット（Physical AI 応用1講座 最終課題）\n\n'
        '自然な言い回しの依頼をローカルLLMが解釈し、ロボットが拠点へ自律移動。その場でカメラ画像をローカルVLM（Qwen3.5-9B / V100）で確認し、'
        '依頼どおりで火も見えないときだけ避難所Bへ向かいます。ROS 2 Jazzy × Gazebo Harmonic、映像はすべて Gazebo の実レンダリング。\n'
        '※ 「届ける」は、現物確認して避難所Bへ向かう（接近する）ところまで。物資の把持・荷降ろしはシミュレーションしていません。']
    paras[-1] = paras[-1].replace('\n\n自然な言い回し', '\n\n' + '\n'.join(headline_block(res)) + '\n\n' + watch_sentence(facts) + '\n\n自然な言い回し', 1)
    blocks = [x for x in (demo_sentence(facts), speed_sentence(facts)) if x]
    nums = number_lines(res) if _nums is None else _nums
    if nums:
        blocks.append('詳しい結果（事前登録＝結果を見る前に条件を固定。v3.4〜v3.6＝システムの版名（v3.6が提出版）。誤許可＝届けてはいけない場面で「よい」と判断すること）：\n' + '\n'.join(nums))
    blocks.append('コード：https://github.com/fe2131-art/rescue-mind\nナレーション：VOICEVOX:四国めたん')
    blocks.append('\n'.join(f"{mmss(c['start_s'])} {c['title']}" for c in facts['chapters']))
    paras[-1] += '\n\n' + '\n\n'.join(blocks)
    paras.append('## 公開設定チェック（課題の指定）\n'
                 '- 公開（推奨）または限定公開（最低条件）\n'
                 '- 「子ども向け」→ いいえ／年齢制限 → いいえ\n'
                 '- 「インスタントプレミアム公開」→ チェックしない\n'
                 '- 予約公開の場合は締切（2026-11-02 10:00）までの日時を設定\n'
                 '- 採点完了まで削除・非公開にしない')
    out = '\n\n'.join(paras) + '\n'
    body = out.split('## 概要欄\n', 1)[1].split('\n\n## 公開設定', 1)[0]
    if len(body) > LIMIT and nums:
        snap = advice_numbers.snapshot_mode()
        for key in DROP_ORDER + (DROP_ORDER_SNAP if snap else ()):
            keep = [x for x in nums if key not in x]
            if len(keep) < len(nums):
                if not any('README' in x for x in keep):
                    keep.append('・ほかの結果（画像テスト・画質の変化・比較手法' + ('・未知の配置' if snap else '') + 'など）は README と説明資料に掲載')
                return build_description(chapters, res, keep)
    return out, facts


def build_submission_block(facts):
    lines = []
    d = demo_sentence(facts)
    if d:
        lines.append(f"* **動画の{len(facts['missions'])}デモ**：" + d.split('：', 1)[1].rstrip('。') + '。')
    s = speed_sentence(facts, short=True)
    if s:
        lines.append(f'* **倍速の明記**：{s}（画面左上に常時表示。YouTube概要欄にも記載）。')
    tables = f"、評価の表{facts['n_tables']}枚" if facts['n_tables'] else ''
    lines.append(f"* **動画の長さと章立て**：約{facts['length_ja']}（1〜3分の枠内）、章{len(facts['chapters'])}個{tables}。"
                 f"章立ては `docs/video_chapters.json`（`scripts/make_demo_video.py` が出力）、概要欄は `scripts/make_youtube_description.py` が再生成。")
    return '\n'.join(lines)


def splice(text, block):
    pat = re.compile(re.escape(V_START) + r'.*?' + re.escape(V_END), re.S)
    if not pat.search(text):
        raise ValueError(f'{V_START} / {V_END} markers not found')
    return pat.sub(lambda _: f'{V_START}\n{block}\n{V_END}', text, count=1)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--chapters', default=str(ROOT / 'docs/video_chapters.json'))
    ap.add_argument('--results', default=str(ROOT / 'experiments/results'))
    ap.add_argument('--out', default=str(ROOT / 'docs/YOUTUBE_DESCRIPTION.md'))
    ap.add_argument('--submission', default=str(ROOT / 'docs/SUBMISSION.md'))
    ap.add_argument('--check', action='store_true', help='do not write; exit 1 if a file is out of date')
    ap.add_argument('--snapshot', action='store_true', help='submission snapshot: write docs/snapshot/YOUTUBE_DESCRIPTION.md, name the studies not run at submission')
    a = ap.parse_args(argv)
    if a.snapshot:
        os.environ['SNAPSHOT'] = '1'
        if a.out == str(ROOT / 'docs/YOUTUBE_DESCRIPTION.md'):
            a.out = str(advice_numbers.snapshot_dir() / 'YOUTUBE_DESCRIPTION.md')
        a.submission = ''     # docs/SUBMISSION.md is a tracked document: the snapshot does not rewrite it
    chapters = json.loads(Path(a.chapters).read_text(encoding='utf8'))
    desc, facts = build_description(chapters, a.results)
    sub_path = Path(a.submission)
    sub_new = splice(sub_path.read_text(encoding='utf8'), build_submission_block(facts)) if a.submission and sub_path.is_file() else None
    for w in facts['warnings']:
        print('WARNING:', w, file=sys.stderr)
    body = desc.split('## 概要欄\n', 1)[1].split('\n\n## 公開設定', 1)[0]
    if len(body) > LIMIT:
        print(f"WARNING: description is {len(body)} characters (YouTube limit 5000, ours {LIMIT})", file=sys.stderr)
    out = Path(a.out)
    stale = []
    if not out.is_file() or out.read_text(encoding='utf8') != desc:
        stale.append(str(out))
    if sub_new is not None and sub_new != sub_path.read_text(encoding='utf8'):
        stale.append(str(sub_path))
    if a.check:
        print('up to date' if not stale else 'STALE: ' + ', '.join(stale))
        return 1 if stale else 0
    if str(out) in stale:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(desc, encoding='utf8')
    if str(sub_path) in stale:
        sub_path.write_text(sub_new, encoding='utf8')
    print(f"{facts['length_mmss']}  demos={len(facts['missions'])}  tables={facts['n_tables']}  chapters={len(facts['chapters'])}  "
          f"updated: {', '.join(stale) or 'nothing'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
