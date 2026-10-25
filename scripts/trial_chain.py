#!/usr/bin/env python3
"""Trial and error as a story (I-149): each failed registered claim -> what it taught -> the next study -> how that study came out.

  python3 scripts/trial_chain.py [--write]   # prints the Markdown table (README); --write also updates docs/TRIAL_AND_ERROR.md; exit 1 if a failed claim is not placed

The steps are written by hand (they are the story); the status of every claim and every next study is read from the result files
(advice_numbers.failed_claims and the summaries), so a later result changes the table without editing it.  A failed claim that no step
names is listed in a last row ("not yet placed"), so the table can never hide a failure.  Used by scripts/make_report.py and
scripts/update_readme_results.py.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
sys.path.insert(0, str(ROOT / 'scripts'))
import advice_numbers  # noqa: E402

# study-subset: the story steps (failed claim keys, what it taught, next studies [(study, summary file)], what the next step was); unplaced failures are listed by rows()
STEPS = [
    (('T1', 'F', 'T2'), 'AIの誤りの大半は「物資の陰に隠れた小さな火」。問い方や拡大では区別できない',
     [('G', 'g_summary.json'), ('GR', 'gr_summary.json')], 'AIを賢くせず、横へ動いて撮り直す（見回し）'),
    (('J', 'JH1', 'JC1'), '別のAIを足しても誤りが同じ場所に重なり、見逃しは減らない',
     [('JI', 'ji_summary.json'), ('JK', 'jk_summary.json'), ('JL', 'jl_summary.json')], 'AIではなく視点を増やす。疑わしいときだけ追加で撮る'),
    (('XD-eps', 'XD-rel', 'XD-cal'), '雑多な倉庫では見逃しが残り、閾値の較正だけでは減らない',
     [('GL', 'gl_summary.json'), ('GM', 'gm_summary.json'), ('JM', 'jm_summary.json')], '倉庫用に視点を広げ、描画や煙を1つずつ変えて原因を切り分ける'),
    (('Q', 'QI1', 'QI2', 'QI3c'), '実写・写実化した画像では、止まりすぎるか見逃しが増える（シミュレーションの限界）',
     [('P2', 'p2_summary.json')], '現場の写真で閾値を較正する手順を必須にし、限界として報告'),
    (('IF1',), '依頼文に偽の通知を足すと、頼まれた物資がすり替わる',
     [('IF2', 'if2_summary.json')], '物資が食い違えば聞き返す規則'),
    (('IG1', 'IH1'), 'リストにない届け先を避難所Bと読み、規則を足しても残る',
     [('IJ', 'ij_summary.json')], 'モデルの内部状態から「知らない行き先」を見分ける。出発前の読み返しは必須'),
    (('IJ2',), 'モデルの内部状態は知らない届け先を分ける（AUROC 0.98）が、開発データで決めた閾値は未見の地名の系統に移らず、9割が素通りした',
     [], 'この判定器は組み込まず、出発前の読み返しを必須のままにする（実験はここで終了）'),
    (('V4',), 'ランダムに変わる世界では、確認つきの記憶の安全を統計的に示せなかった',
     [('H', 'h_summary.json'), ('A', 'a_summary.json')], '記憶も他の入力も「助言」に限り、判断は必ずその場の目で'),
    (('YE2', 'YF4', 'W-b', 'S-perm'), '登録した文言や予測そのものが外れた（主張の書き方の誤り）',
     [], '登録の文言を厳密にし、外れた予測もそのまま残す'),
    # I-163: placed before JM's result, worded for any failure of JM (the step appears only if a JM claim fails)
    (('JM1', 'JM2', 'JM3'), '煙の有無だけを変えた双子の世界で、登録した予測（煙が見逃しを増やす・追加視点が煙の中でも効く）の一部が外れた',
     [], '煙の影響は数値のまま限界として報告し、実験は増やさない（実験はここで終了）'),
]


def failed_keys() -> list:
    return [c['key'] for c in advice_numbers.failed_claims()]


def study_status(study: str, summary: str, failed: list) -> str:
    """成立 / 一部不成立 / 実行中・実行待ち, from the summary file and the failed-claim list."""
    if not (RES / summary).is_file():
        return '実行中・実行待ち'
    pat = re.compile(rf'^{re.escape(study)}(\d|-|$)')
    return '一部不成立' if any(pat.match(k) for k in failed) else '成立'


def rows() -> list:
    failed = failed_keys()
    out, placed = [], set()
    for keys, taught, nxt, step in STEPS:
        present = [k for k in keys if k in failed]
        placed.update(present)
        if not present:
            continue
        res = '、'.join(f'{s}：{study_status(s, f, failed)}' for s, f in nxt) if nxt else '—'
        out.append(('・'.join(present), taught, step, res))
    rest = [k for k in failed if k not in placed]
    if rest:
        out.append(('・'.join(rest), '（まだ物語に位置づけていない失敗）', '—', '—'))
    return out


def markdown() -> str:
    head = ['| 成立しなかった主張 | わかったこと | 次の一手 | 次の一手の結果 |', '|---|---|---|---|']
    return '\n'.join(head + [f'| {a} | {b} | {c} | {d} |' for a, b, c, d in rows()])


def unplaced() -> list:
    placed = {k for keys, *_ in STEPS for k in keys}
    return [k for k in failed_keys() if k not in placed]


def write_doc() -> bool:
    """Replace the block between <!-- TRIALS:START --> and <!-- TRIALS:END --> in docs/TRIAL_AND_ERROR.md; True when the file changed."""
    f = ROOT / 'docs/TRIAL_AND_ERROR.md'
    t = f.read_text(encoding='utf8')
    a_, b_ = t.index('<!-- TRIALS:START -->'), t.index('<!-- TRIALS:END -->') + len('<!-- TRIALS:END -->')
    new = t[:a_] + '<!-- TRIALS:START -->\n' + markdown() + '\n<!-- TRIALS:END -->' + t[b_:]
    if new != t:
        f.write_text(new, encoding='utf8')
    return new != t


if __name__ == '__main__':
    if '--write' in sys.argv:
        print('docs/TRIAL_AND_ERROR.md', 'updated' if write_doc() else 'unchanged')
    print(markdown())
    u = unplaced()
    print(f'\n{len(failed_keys())} failed claims, {len(u)} not placed in a step' + (f': {u}' if u else ''))
    sys.exit(1 if u else 0)
