#!/usr/bin/env python3
"""Regenerate the YouTube description and the video paragraph of the submission notes from the rendered video.

Single source of truth for the video structure: docs/video_chapters.json (written by scripts/make_demo_video.py).
Numbers come from experiments/results/*summary*.json and the campaign_E ledger; a study whose result file does
not exist is omitted (a public description never says "running").

  python3 scripts/make_youtube_description.py            # rewrite docs/YOUTUBE_DESCRIPTION.md and docs/SUBMISSION.md
  python3 scripts/make_youtube_description.py --check    # exit 1 if either file is out of date
"""
import argparse
import json
import re
import sys
from pathlib import Path

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
    chapters = sorted(chapters, key=lambda c: c['start_s'])
    total = chapters[-1]['end_s']
    missions = [c for c in chapters if c.get('kind') == 'mission']
    speeds = []
    for c in missions:
        if c.get('speed') and c['speed'] not in speeds:
            speeds.append(c['speed'])
    warn = []
    if not 60 <= total <= 180:
        warn.append(f'video length {total:.1f}s is outside the 1-3 minute requirement')
    for c in chapters:
        if c['end_s'] - c['start_s'] < 10:
            warn.append(f"chapter '{c['title']}' ({mmss(c['start_s'])}) is shorter than 10 s (YouTube may ignore the chapter list)")
    if mmss(chapters[0]['start_s']) != '0:00':
        warn.append('first chapter does not start at 0:00')
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
        t = strip_demo(c['title'])
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
        return (f"・未使用の画像{m['n_images']}枚（T1）：拒否すべき{n}枚のうち誤許可{fa}枚（v3.4の規則）。"
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
        s = f"・実写（D-Fire {p['n']}枚）の評価P：火・煙のある写真の検出 {rc['k']}/{rc['n']}、火の無い写真で誤警報 {fa['k']}/{fa['n']}"
        if fa['k'] / fa['n'] >= 0.2:
            s += '（誤警報が多く、現場ごとの調整が必要）'
        return s
    except (TypeError, KeyError, ZeroDivisionError):
        return None


def line_h(res):
    h = jload(Path(res) / 'h_summary.json')
    try:
        p1, p2 = h['P1_efficiency_relocation_persist'], h['P2_safety_naive_vs_verified']
        t = (f"物資の入れ替わりが続く出動の所要時間の中央値 記憶なし {p1['time_M0_median_s']:.0f}秒・検証つき記憶 {p1['time_M2_median_s']:.0f}秒、"
             if p1['n_pairs'] else '')
        return (f"・出動をまたぐ記憶の評価H：{t}"
                f"危険な配達は 素朴な記憶 {p2['unsafe_M1']}件 対 検証つき記憶 {p2['unsafe_M2']}件")
    except (TypeError, KeyError, ValueError):
        return None


def line_j(res):
    j = jload(Path(res) / 'j_summary.json')
    try:
        c = j['per_config']
        return (f"・2つのAI構成（Jev役＋Qwen）の閉ループ評価J：期待どおり {c['J']['correct']}/{c['J']['n']}"
                f"（v3.6単独 {c['A']['correct']}/{c['A']['n']}）、危険な配達 {c['J']['unsafe_deliveries']}件（v3.6単独 {c['A']['unsafe_deliveries']}件）")
    except (TypeError, KeyError):
        return None


def number_lines(res):
    fns = (line_e, line_t1, line_g, line_t2, line_z, line_r, line_p, line_h, line_j)
    return [x for x in (f(res) for f in fns) if x]


# ------------------------------------------------------------------ documents
def build_description(chapters, res):
    facts = video_facts(chapters)
    head = (f"**ファイル**：`{VIDEO_FILE}`（1920×1080, 30fps, 約{facts['length_ja']}"
            f"（`docs/video_chapters.json` の終端 {facts['total_s']:g} 秒）、日本語ナレーション付き）")
    paras = [
        '# YouTube 投稿用テキスト（コピーして使用）', head,
        '## タイトル\nPAI最終課題_tetsutetsu',
        '## 概要欄\n'
        'RescueMind：現地で「目で確かめてから」届ける災害物資ロボット（Physical AI 応用1講座 最終課題）\n\n'
        '自然な言い回しの依頼をローカルLLMが解釈し、差動二輪ロボットが物資拠点へ自律移動。拠点で静止して搭載カメラの画像を最新のローカルVLM'
        '（Qwen3.5-9B / Tesla V100）で確認し、依頼どおりと高い確信で一致したときだけ、拠点の左右からも火が無いか見直して（v3.6）避難所Bへ向かいます。'
        '物資が違えば別の拠点を探して届け、どちらにも無ければ停止して報告し、火災を見たら探索せずに停止して日本語で状況を報告します。\n'
        'ROS 2 Jazzy × Gazebo Harmonic。映像はすべて Gazebo の実レンダリングです。\n'
        '※ 「届ける」は、物資を現物確認して避難所Bへ向かう（接近する）ところまでです。物資の把持・荷降ろし・受け渡しはシミュレーションしていません。']
    blocks = [x for x in (demo_sentence(facts), speed_sentence(facts)) if x]
    nums = number_lines(res)
    if nums:
        blocks.append('事前登録した評価（結果を見る前に条件を固定）：\n' + '\n'.join(nums))
    blocks.append('コード：https://github.com/fe2131-art/rescue-mind\nナレーション：VOICEVOX:四国めたん')
    blocks.append('\n'.join(f"{mmss(c['start_s'])} {c['title']}" for c in facts['chapters']))
    paras[-1] += '\n\n' + '\n\n'.join(blocks)
    paras.append('## 公開設定チェック（課題の指定）\n'
                 '- 公開（推奨）または限定公開（最低条件）\n'
                 '- 「子ども向け」→ いいえ／年齢制限 → いいえ\n'
                 '- 「インスタントプレミアム公開」→ チェックしない\n'
                 '- 予約公開の場合は締切（2026-11-02 10:00）までの日時を設定\n'
                 '- 採点完了まで削除・非公開にしない')
    return '\n\n'.join(paras) + '\n', facts


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
    a = ap.parse_args(argv)
    chapters = json.loads(Path(a.chapters).read_text(encoding='utf8'))
    desc, facts = build_description(chapters, a.results)
    sub_path = Path(a.submission)
    sub_new = splice(sub_path.read_text(encoding='utf8'), build_submission_block(facts)) if sub_path.is_file() else None
    for w in facts['warnings']:
        print('WARNING:', w, file=sys.stderr)
    body = desc.split('## 概要欄\n', 1)[1].split('\n\n## 公開設定', 1)[0]
    if len(body.encode('utf8')) > 5000:
        print(f"WARNING: description is {len(body.encode('utf8'))} bytes (YouTube limit 5000)", file=sys.stderr)
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
        out.write_text(desc, encoding='utf8')
    if str(sub_path) in stale:
        sub_path.write_text(sub_new, encoding='utf8')
    print(f"{facts['length_mmss']}  demos={len(facts['missions'])}  tables={facts['n_tables']}  chapters={len(facts['chapters'])}  "
          f"updated: {', '.join(stale) or 'nothing'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
