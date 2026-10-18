#!/usr/bin/env python3
"""Cross-document consistency check: the key numbers printed in README.md, docs/YOUTUBE_DESCRIPTION.md,
docs/paper/numbers.tex (macros) and the explanation report (docs/report/*.pdf) must agree with the result files.

  python3 scripts/check_consistency.py                # table; exit 1 on any MISMATCH
  python3 scripts/check_consistency.py --no-report    # skip the report (no docker / pdftotext)
  python3 scripts/check_consistency.py --report-text FILE   # use already extracted report text
  python3 scripts/check_consistency.py --snapshot     # the SUBMISSION SNAPSHOT (docs/snapshot/: README, YouTube text, paper, report; `make snapshot`)

--snapshot: a registered study without results reads "registered, not yet run at submission" (登録済み・提出時点で未実施) in every document; that is
accepted (no TBD, no "pending"), while a TBD, a "pending", a "running" / "結果待ち" for such a study, a result number that disagrees with the
result files, or a number of a pending study that no sentence wraps is still a MISMATCH.

Expected values are read from experiments/results/*.json (and the ledgers), never from the documents.
Each fact has up to four cells: README, YouTube text, paper macro, report.  Cells: ok / MISMATCH (the document
does not contain the expected string, or contains a forbidden stale one) / -- (the document does not print it).
The paper macros are also compared with a fresh scripts/paper_numbers.py run (a stale numbers.tex is a mismatch),
the video facts with docs/video_chapters.json, the test count with a fresh static count, and the abstract of
main.pdf must not show a pending marker.  Needs only python3 and (for the report/PDF text) docker + rescuemind:latex.
"""
from __future__ import annotations
import argparse
import json
import re
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SNAP = '--snapshot' in sys.argv
if SNAP:
    os.environ['SNAPSHOT'] = '1'          # before paper_numbers / advice_numbers are imported
ROOT = Path(__file__).resolve().parents[1]
SD = os.environ.get('SNAPSHOT_DIR') or 'docs/snapshot'      # where `make snapshot` writes (untracked); SNAPSHOT_DIR overrides (tests)
sys.path.insert(0, str(ROOT / 'scripts'))
RES = ROOT / 'experiments/results'
LATEX_IMG = 'rescuemind:latex'


def jload(name):
    f = RES / name
    return json.loads(f.read_text(encoding='utf8')) if f.is_file() else None


def ledger(name):
    f = RES / name
    if not f.is_file():
        return None
    return [r for r in (json.loads(x) for x in f.read_text(encoding='utf8').splitlines() if x.strip()) if r.get('final', True)]


def norm(t):
    return re.sub(r'\s+', '', t)


# --------------------------------------------------------------------------------------------- documents
def read(p):
    f = ROOT / p
    return f.read_text(encoding='utf8') if f.is_file() else ''


def macros(path=None):
    path = path or (f'{SD}/paper/numbers.tex' if SNAP else 'docs/paper/numbers.tex')
    out = {}
    for ln in read(path).splitlines():
        m = re.match(r'\\newcommand\{\\([A-Za-z]+)\}\{(.*)\}$', ln)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def pdf_text(pdf: Path):
    """Text of a PDF via pdftotext (host) or the latex container; None when neither is usable."""
    try:
        r = subprocess.run(['pdftotext', '-layout', str(pdf), '-'], capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout
    except FileNotFoundError:
        pass
    try:
        r = subprocess.run(['docker', 'run', '--rm', '-v', f'{pdf.parent}:/w:ro', LATEX_IMG, 'pdftotext', '-layout', f'/w/{pdf.name}', '-'],
                           capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else None
    except FileNotFoundError:
        return None


# --------------------------------------------------------------------------------------------- expected values
def facts():
    """List of dicts: name, expected (display), readme/yt/report: [needles], forbid: {doc: [regex]}, macro: {name: value}."""
    F = []

    def add(name, expected, readme=(), yt=(), report=(), macro=None, yt_key=None):
        # yt_key: marker of a YouTube detail line that make_youtube_description.py may drop by design when the text exceeds 5000 bytes
        F.append(dict(name=name, expected=expected, readme=list(readme), yt=list(yt), report=list(report), macro=macro or {}, yt_key=yt_key))

    e = ledger('campaign_E_ledger.jsonl')
    if e:
        ok = sum(bool(r['correct']) for r in e)
        add('E expected behaviour', f'{ok}/{len(e)}', [f'**{ok}/{len(e)}**'], [f'期待どおりの行動 {ok}/{len(e)}'], [],
            {'ECorrect': str(ok), 'EN': str(len(e))})
    g = jload('g_summary.json')
    if g:
        pr = g['primary']
        b, c, n = pr['wrong_deliveries_B'], pr['wrong_deliveries_C'], pr['n_world_pairs_fire_perceivable']
        add('G deliveries despite fire', f'{b}/{n} -> {c}/{n}', [f'**{b}/{n} → {c}/{n}**'], [f'{b}回、横から撮り直すと {c}回'], [],
            {'GWrongB': str(b), 'GWrongC': str(c), 'GPairs': str(n)})
    h = jload('h_summary.json')
    if h:
        p1, p2, p3 = h['P1_efficiency_relocation_persist'], h['P2_safety_naive_vs_verified'], h['P3_no_extra_risk_vs_v36']
        t0, t2 = round(p1['time_M0_median_s']), round(p1['time_M2_median_s'])
        add('H median time M0 -> M2', f'{t0} -> {t2} s', [f'{t0}秒 → {t2}秒'], [f'記憶なし {t0}秒・検証つき記憶 {t2}秒'], [f'{t0}→{t2}秒'],
            {'HTimeMzero': str(t0), 'HTimeMtwo': str(t2)})
        add('H unsafe M0 / M1 / M2', f"{p3['unsafe_M0']} / {p2['unsafe_M1']} / {p2['unsafe_M2']} of {p2['n_pairs']}",
            [f"記憶なし {p3['unsafe_M0']}/{p3['n_pairs']}"], [f"素朴な記憶 {p2['unsafe_M1']}件"], [],
            {'HUnsafeMzero': str(p3['unsafe_M0']), 'HUnsafeMone': str(p2['unsafe_M1']), 'HUnsafeMtwo': str(p2['unsafe_M2']), 'HPTwoN': str(p2['n_pairs'])})
    lj = jload('l_summary.json')
    if lj and lj.get('complete'):
        pl = lj['primary']
        add('L expected behaviour (unseen layouts)', f"{pl['expected_behaviour']}, unsafe {pl['unsafe_deliveries']}",
            [f"期待どおり {pl['expected_behaviour']}、危険な配達 {pl['unsafe_deliveries']}件"], [f"期待どおり {pl['expected_behaviour']}、危険な配達 {pl['unsafe_deliveries']}件"],
            [f"期待どおり{pl['expected_behaviour']}"], {'LCorrect': pl['expected_behaviour'], 'LUnsafe': str(pl['unsafe_deliveries']),
                                                       'LClaim': 'supported' if pl['claim_supported'] else 'not supported'}, yt_key='閉ループ評価L')   # dropped from the YouTube text by design in the snapshot (5000 bytes)
    import advice_numbers
    pf_ = advice_numbers.a_pilot_facts()
    if pf_:
        add('A mechanics pilot (i35) and Amendment 1 (i38)', f"{pf_['op_exact']}/{pf_['op_n']} operator runs extracted, {pf_['op_refused']} refused at intent; i38 held-out {pf_['held38']}/{pf_['held_n']}, injection {pf_['inj35']}->{pf_['inj38']}/{pf_['inj_n']}",
            [f"{pf_['op_exact']} of {pf_['op_n']} runs", f"{pf_['inj35']} to {pf_['inj38']} of {pf_['inj_n']}"],
            [], [],
            {'APilotRuns': str(pf_['runs']), 'APilotOpN': str(pf_['op_n']), 'APilotOpExact': str(pf_['op_exact']), 'APilotOpRefused': str(pf_['op_refused']),
             'AIntHeldOut': str(pf_['held38']), 'AIntHeldN': str(pf_['held_n']), 'AIntInjOld': str(pf_['inj35']), 'AIntInjNew': str(pf_['inj38']), 'AIntInjN': str(pf_['inj_n']),
             'AIntWrong': str(pf_['wrong38'])})
    xr_ = advice_numbers.xdr_facts()
    if xr_:
        add('XD-R frozen photographs (kept / candidates)', f"{xr_['kept']}/{xr_['cand']}", [], [], [],
            {'XDRKept': str(xr_['kept']), 'XDRCand': str(xr_['cand']), 'XDRExcl': str(xr_['excl'])})
    vf = advice_numbers.v_facts()
    if vf:
        d, u, ok = vf['diff'], vf['unsafe'], lambda x: '成立' if x else '不成立'
        mp = f"{vf['mcnemar_p']:.4f}"
        add('V paired time saving M0-M2 (s)', f"{d:.0f} (registered {vf['pred_lo']:.0f}-{vf['pred_hi']:.0f})",
            [f"実測 {d:.0f} 秒", f"{vf['pred_lo']:.0f}〜{vf['pred_hi']:.0f} 秒"], [f"時間差 {d:.0f}秒", f"{vf['pred_lo']:.0f}〜{vf['pred_hi']:.0f}秒"],
            [f"実測 {d:.0f} 秒", f"{vf['pred_lo']:.0f}〜{vf['pred_hi']:.0f} 秒"], {'VObsDiff': f'{d:.0f}'})
        add('V unsafe deliveries M0 / M1 / M2', f"{u['M0']} / {u['M1']} / {u['M2']} of {vf['n_per_arm']}",
            [f"記憶なし {u['M0']}・素朴な記憶 {u['M1']}・検証つき記憶 {u['M2']}件"], [f"記憶なし {u['M0']}・素朴な記憶 {u['M1']}・検証つき記憶 {u['M2']}件"],
            [f"記憶なし {u['M0']}・素朴な記憶 {u['M1']}・本方式 {u['M2']}件"],
            {'VUnsafeMzero': str(u['M0']), 'VUnsafeMone': str(u['M1']), 'VUnsafeMtwo': str(u['M2'])})
        add('V claims (model / memory under random change) and the sequence McNemar p', f"{ok(vf['model_claim'])} / {ok(vf['memory_claim'])}, p={mp}",
            [f"モデルの予測：{ok(vf['model_claim'])}", f"記憶はランダムな変化でも安全：{ok(vf['memory_claim'])}", f"p={mp}"],
            [f"モデルの予測は{ok(vf['model_claim'])}", f"の主張は{ok(vf['memory_claim'])}", f"p={mp}"],
            [f"モデルの予測：{ok(vf['model_claim'])}", f"記憶はランダムな変化でも安全（V4）：{ok(vf['memory_claim'])}", f"p={mp}"],
            {'VClaimModel': 'supported' if vf['model_claim'] else 'not supported', 'VClaimMemory': 'supported' if vf['memory_claim'] else 'not supported', 'VSeqP': mp})
    p = jload('p_summary.json')
    if p:
        rc, fa = p['recall'], p['false_alarm']
        add('P recall / false alarms (real photos)', f"{rc['k']}/{rc['n']} / {fa['k']}/{fa['n']}",
            [f"{rc['k']}/{rc['n']}", f"{fa['k']}/{fa['n']}"], [f"検出 {rc['k']}/{rc['n']}、火の無い写真で誤警報 {fa['k']}/{fa['n']}"], [f"{fa['k']}/{fa['n']}"],
            {'PRecall': f"{rc['k']}/{rc['n']}", 'PFalseAlarm': f"{fa['k']}/{fa['n']}"}, yt_key='評価P')
    p2 = jload('p2_summary.json')
    if p2 and p2.get('chosen_test'):
        ct = p2['chosen_test']
        rk, fk = f"{ct['recall']['k']}/{ct['recall']['n']}", f"{ct['false_alarm']['k']}/{ct['false_alarm']['n']}"
        add('P2 calibrated recall / false alarms', f'{rk} / {fk}', [rk, fk], [f'検出 {rk}、誤警報 {fk}'], [f'検出{rk}・誤警報{fk}'],
            {'PTwoRecall': rk, 'PTwoFA': fk, 'PTwoClaim': 'supported' if p2['claim_supported'] else 'not supported'}, yt_key='評価P')
    t1 = jload('t1_summary.json')
    if t1:
        f = t1['models']['Qwen3.5-9B']['rules']['full']
        add('T1 false approvals (registered rule)', f"{f['false_approvals']}/{f['n_deny']}", [f"{f['false_approvals']}/{f['n_deny']}"],
            [f"誤許可 {f['false_approvals']}枚"], [], {'TFA': str(f['false_approvals']), 'TNdeny': str(f['n_deny'])}, yt_key='（T1）')
    r = jload('r_summary.json')
    if r:
        p1 = r['P1_pooled']
        add('R pooled false approvals', f"{p1['false_approvals']}/{p1['n']}", [], [], [],
            {'RPoolFA': f"{p1['false_approvals']}/{p1['n']}"})
    j = jload('j_summary.json')
    if j:
        c = j['per_config']
        add('J expected behaviour (two-model check)', f"{c['J']['correct']}/{c['J']['n']}", [f"{c['J']['correct']}/{c['J']['n']}"],
            [f"期待どおり {c['J']['correct']}/{c['J']['n']}"], [f"{c['J']['correct']}/{c['J']['n']}"], {'JCorrectJ': f"{c['J']['correct']}/{c['J']['n']}"}, yt_key='評価J')
        vr = j['P1_runs_on_one_v100'].get('peak_vram_mib')
        if vr:
            add('J peak GPU memory (GiB, not GB)', f'{vr / 1024:.1f} GiB', [], [], [f'{vr / 1024:.1f}GiB'], {'JPeakVram': f'{vr / 1024:.1f}'})
    t2 = jload('t2_summary.json')
    if t2:
        ref = t2['results'][t2['reference']]
        add('T2 false approvals (reference)', f"{ref['false_approvals']}/{ref['n_deny']}", [f"{ref['false_approvals']}/{ref['n_deny']}"], [], [],
            {'TTRefFA': f"{ref['false_approvals']}/{ref['n_deny']}"})
    # I-23 / I-24: machine-checked Proposition 2 and the advice-credit model (single source: scripts/advice_numbers.py -> README, report, paper macros)
    import advice_numbers
    sf, cf = advice_numbers.smt_facts(), advice_numbers.credit_facts()
    if sf:
        add('I-23 z3 unsat queries / differential cases / injected bugs caught',
            f"{sf['unsat']} unsat of {sf['queries']}; {sf['cases']:,} cases, {sf['disagreements']} disagreements; {sf['caught']}/{sf['mutants']} caught",
            [f"{sf['unsat']}件が反例なし", f"{sf['cases']:,}件で不一致 {sf['disagreements']}", f"{sf['caught']}/{sf['mutants']} を検出"], [],
            [f"{sf['unsat']}件", f"{sf['cases']:,}件で不一致{sf['disagreements']}", f"{sf['mutants']}個を{sf['caught']}個とも"], {})
    if cf:
        add('I-24 advice credit (descriptive model, k=4): liar / flooding', f"{cf['liar_no']:.0f} -> {cf['liar_yes']:.0f} s; {cf['flood_no']} -> {cf['flood_yes']}",
            [f"+{cf['liar_no']:.0f}秒 → +{cf['liar_yes']:.0f}秒", f"{cf['flood_no']}回 → {cf['flood_yes']}回"], [],
            [f"+{cf['liar_no']:.0f} → +{cf['liar_yes']:.0f}秒", f"{cf['flood_no']} → {cf['flood_yes']}回"],
            {'CrLiarNo': f"{cf['liar_no']:.0f}", 'CrLiarYes': f"{cf['liar_yes']:.0f}", 'CrFarmYes': f"{cf['adaptive_yes']:.0f}",
             'CrHonest': f"{cf['honest_no']:.0f}", 'CrFloodNo': str(cf['flood_no']), 'CrFloodYes': str(cf['flood_yes']),
             'CrFloodDelta': f"{cf['flood_delta']:.2f}", 'CrNoisyKeep': f"{cf['noisy_keep']:.0f}\\%", 'CrMissions': str(cf['missions'])})
    # run counts and study counts
    a_n = len(json.loads((ROOT / 'experiments/campaign_a_protocol.json').read_text())['trials'])
    add('A closed-loop runs (protocol file)', str(a_n), [f'({a_n} closed-loop runs)', f'（{a_n}試行）'], [], [f'閉ループ{a_n}試行'], {})
    sc = advice_numbers.study_counts()
    if sc:
        n_stud = sc['n']
        add('studies (Table S9 rows, without C; same definition everywhere)', str(n_stud),
            [f'論文の{n_stud}研究'], [], [f'研究 {n_stud} 本'],
            {'NStudies': str(n_stud), 'NStudiesChecked': str(sc['ok']), 'NStudiesPending': str(sc['pending'])})
    # test functions: fresh static count against the generated file and every document
    import count_tests
    n_fresh = count_tests.static_count()
    stored = count_tests.n_tests()
    add('test functions (static count)', f'{n_fresh}' + ('' if stored == n_fresh else f' (test_count.json says {stored}: STALE)'),
        [f'テスト関数 {n_fresh} 件'], [], [f'テスト関数も現在は{n_fresh}件'], {'NTests': str(n_fresh)})
    if stored != n_fresh:
        F[-1]['stale'] = True
    return F


def forbidden():
    """Stale statements that must not survive in a document: (doc, regex, why)."""
    return [('readme', r'114 closed-loop|114試行|\(114 runs', 'study A has 226 runs'),
            ('report', r'114試行', 'study A has 226 runs'),
            ('readme', r'全19研究|論文の21研究', 'the audit covers the 23 studies of the paper (B and IF included)'),
            ('readme', r'612件', 'test count is generated (test functions)'),
            ('report', r'単体テストも現在は', 'say "test functions" (static count)')]


# --------------------------------------------------------------------------------------------- checks
def check_docs(F, docs, mac):
    rows, bad = [], 0
    for f in F:
        cells = {}
        for doc in ('readme', 'yt', 'report'):
            needles = f[doc]
            if not needles:
                cells[doc] = '--'
                continue
            text = docs.get(doc)
            if text is None:
                cells[doc] = 'skip'
                continue
            miss = [n for n in needles if norm(n) not in norm(text)]
            if doc == 'yt' and miss and f.get('yt_key') and f['yt_key'] not in text and 'ほかの結果' in text:
                cells[doc] = 'dropped'      # the whole detail line was dropped by design (5000-byte limit; README and report carry it)
                continue
            cells[doc] = 'ok' if not miss else 'MISMATCH'
            if miss:
                f.setdefault('detail', []).append(f'{doc}: missing {miss}')
        if f['macro']:
            wrong = {k: (mac.get(k), v) for k, v in f['macro'].items() if mac.get(k) != v}
            cells['macro'] = 'ok' if not wrong else 'MISMATCH'
            if wrong:
                f.setdefault('detail', []).append('macro: ' + ', '.join(f'\\{k}={a!r} expected {b!r}' for k, (a, b) in wrong.items()))
        else:
            cells['macro'] = '--'
        if f.get('extra'):
            nm, got, want = f['extra']
            if got != want:
                cells['macro'] = 'MISMATCH'
                f.setdefault('detail', []).append(f'{nm}={got!r} expected {want!r}')
        if f.get('stale'):
            cells['macro'] = 'MISMATCH'
            f.setdefault('detail', []).append('experiments/results/test_count.json is stale (run scripts/count_tests.py)')
        bad += sum(v == 'MISMATCH' for v in cells.values())
        rows.append((f['name'], f['expected'], cells))
    return rows, bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--no-report', action='store_true', help='do not read the report / paper PDFs')
    ap.add_argument('--report-text', help='text file with the already extracted report text')
    ap.add_argument('--strict', action='store_true', help='treat skipped documents as failures')
    ap.add_argument('--snapshot', action='store_true', help='check the submission snapshot in docs/snapshot/ (pending studies read "registered, not yet run at submission")')
    a = ap.parse_args()
    F = facts()
    mac = macros()
    docs = {'readme': read(f'{SD}/README.md' if SNAP else 'README.md'), 'yt': read(f'{SD}/YOUTUBE_DESCRIPTION.md' if SNAP else 'docs/YOUTUBE_DESCRIPTION.md'), 'report': None}
    pdfs = sorted((ROOT / (f'{SD}/report' if SNAP else 'docs/report')).glob('*.pdf'))
    if a.report_text:
        docs['report'] = Path(a.report_text).read_text(encoding='utf8')
    elif not a.no_report and pdfs:
        docs['report'] = pdf_text(pdfs[0])
    rows, bad = check_docs(F, docs, mac)
    extra = []          # (name, status, detail)

    for doc, rx, why in forbidden():
        t = docs.get(doc)
        if t is None:
            continue
        hit = re.search(rx, t)
        extra.append((f'no stale text in {doc} ({why})', 'MISMATCH' if hit else 'ok', f'matches {rx!r}' if hit else ''))

    # README as GitHub renders it: no broken relative link / image / anchor (tracked files only); the first screen keeps its parts
    if not SNAP:
        import check_readme_links
        _n, _bad, _ = check_readme_links.check(ROOT / 'README.md')
        extra.append((f'README relative links ({_n} checked)', 'MISMATCH' if _bad else 'ok', '; '.join(_bad[:3])))
    first = '\n'.join(docs['readme'].splitlines()[:32])
    _miss = [k for k in ('hero_lookaround.gif', '<!-- KEY:START -->', 'YouTube（提出時にURLを記載）', 'main.pdf', 'REPRODUCE.md', '説明資料') if k not in first]
    extra.append(('README first screen (hero, key table, video placeholder, report, paper, REPRODUCE)', 'MISMATCH' if _miss else 'ok', ', '.join(_miss)))
    # video facts: chapters vs YouTube text vs README "what to watch" (no demo that is not in the video)
    ch = json.loads(read('docs/video_chapters.json') or '[]')
    if ch:
        total = ch[-1]['end_s']
        ytxt = docs['yt']
        want = f'約{int(total // 60)}分{int(round(total % 60)):02d}秒'
        extra.append(('video length vs YouTube text', 'ok' if want in ytxt else 'MISMATCH', f'{want} from docs/video_chapters.json'))
        titles = ' '.join(c['title'] for c in ch)
        line = next((ln for ln in docs['readme'].splitlines() if ln.startswith('**動画で見てほしい点**')), '')
        bad_demo = [w for w in ('欠品', '助言', '倉庫') if w in line.split('。')[0] and w not in titles]
        extra.append(('README "what to watch" vs video chapters', 'MISMATCH' if (bad_demo or not line) else 'ok',
                      f'names {bad_demo} which is not in the video' if bad_demo else ('paragraph not found' if not line else '')))

    # status words: only V may say "running" while it has no summary
    for k, fn in (('A', 'a_summary.json'), ('S', 's_summary.json'), ('W', 'w_summary.json'), ('X', 'x_summary.json')):
        if (RES / fn).is_file():
            continue
        rx = re.compile(rf'評価{k}[^\n|]*\|[^\n]*実行中（事前登録済み）')
        hit = rx.search(docs['readme'])
        extra.append((f'README row of study {k} says "running" without results', 'MISMATCH' if hit else 'ok', ''))

    # study V has results: no document may still call it running / pending
    import advice_numbers
    if (RES / 'v_summary.json').is_file():
        hit = re.search(r'評価V[^\n|]*\|[^\n]*実行中（事前登録済み）', docs['readme']) or re.search(r'V: model vs\. closed loop[^\n]*pre-registered, running', docs['readme'])
        extra.append(('README row of study V still says "running"', 'MISMATCH' if hit else 'ok', ''))
        rt = docs.get('report')
        if rt is not None:
            hit = re.search(r'評価V[^\n]{0,40}実行中|V[^\n]{0,10}実行中', rt)
            extra.append(('report still says study V is running', 'MISMATCH' if hit else 'ok', f'matches {hit.group(0)!r}' if hit else ''))
        yt_hit = re.search(r'再検証V[^\n]*実行中', docs['yt'])
        extra.append(('YouTube text still says study V is running', 'MISMATCH' if yt_hit else 'ok', ''))
        # the failed registered claim must stay visible in every document (not only in the paper)
        if not advice_numbers.v_facts()['memory_claim']:
            for doc, needle in (('readme', '不成立'), ('yt', '不成立'), ('report', '不成立')):
                t = docs.get(doc)
                if t is None:
                    continue
                seg = [m.start() for m in re.finditer('評価V|再検証V|ランダムな変化', t)]
                ok_ = any('不成立' in t[i:i + 900] for i in seg)
                extra.append((f'{doc}: the failed memory claim of study V is stated', 'ok' if ok_ else 'MISMATCH', ''))

    # study W has results: no document may still call it pending; the failed prior-art claim and the I-20 decision stay visible in every document
    wf_ = advice_numbers.w_facts() if (RES / 'w_summary.json').is_file() else None
    if wf_:
        for doc, rx in (('readme', r'W: small hidden fires[^\n]*(pre-registered, not yet run)'), ('report', r'評価W[^\n]{0,60}結果待ち'), ('yt', r'画像評価W[^\n]*結果待ち')):
            t = docs.get(doc)
            if t is not None:
                extra.append((f'{doc}: study W is not called pending', 'MISMATCH' if re.search(rx, t) else 'ok', ''))
        for doc, needle_ja, needle_en in (('readme', '不成立', 'not supported'), ('yt', '不成立', 'not supported'), ('report', '不成立', 'not supported')):
            t = docs.get(doc)
            if t is None:
                continue
            seg = [m.start() for m in re.finditer('評価W|W: small hidden fires|画像評価W', t)]
            ok_ = (wf_['n_dist'] > 0) or any(needle_ja in t[i:i + 1200] or needle_en in t[i:i + 1200] for i in seg)
            extra.append((f'{doc}: the failed prior-art claim of study W is stated', 'ok' if ok_ else 'MISMATCH', ''))
            adopt_ok = any(('v3.7' in t[i:i + 1400] or 'I-20' in t[i:i + 1400]) for i in seg)
            extra.append((f'{doc}: the I-20 decision after study W is stated', 'ok' if adopt_ok else 'MISMATCH', ''))

    # R8 claim hygiene: one list of failed registered claims, one memory pooling, no stale interlock / implementation / "(none)" wording
    mac_ = macros()
    nf_ = advice_numbers.n_failed_word()
    extra.append(('paper: \\Nfailed equals the length of the generated failure list', 'ok' if mac_.get('Nfailed') == nf_ else 'MISMATCH', f"{mac_.get('Nfailed')} vs {nf_}"))
    main_tex = read('docs/paper/main.tex')
    extra.append(('main.tex: Nfailed is not hand-defined and the Discussion prints \\FailedList',
                  'ok' if (r'\newcommand{\Nfailed}' not in main_tex and r'\FailedList' in main_tex) else 'MISMATCH', ''))
    pm_ = advice_numbers.pooled_memory()
    if pm_:
        okp = (mac_.get('MemPoolzero') == str(pm_['unsafe']['M0']) and mac_.get('MemPooltwo') == str(pm_['unsafe']['M2'])
               and mac_.get('MemPoolone') == str(pm_['unsafe']['M1']) and mac_.get('MemPoolN') == str(pm_['n']))
        extra.append(('paper: pooled H+V unsafe deliveries (macros) equal the result files', 'ok' if okp else 'MISMATCH', str(pm_['unsafe'])))
        ab_ = main_tex.split(r'\begin{abstract}')[-1].split(r'\end{abstract}')[0]
        extra.append(('main.tex: abstract reports the pooled memory result (H and V)', 'ok' if r'\MemPoolN' in ab_ else 'MISMATCH', ''))
        concl_ = main_tex.split(r'\section{Conclusion}')[-1]
        extra.append(('main.tex: conclusion reports V next to H', 'ok' if (r'\StatV' in concl_ and r'\MemPooltwo' in concl_) else 'MISMATCH', ''))
        yt_, rd_ = docs['yt'], docs['readme']
        for doc, t in (('readme', rd_), ('yt', yt_)):
            extra.append((f'{doc}: pooled memory safety (H and V) is stated', 'ok' if (advice_numbers.pooled_memory_ja() in t or advice_numbers.pooled_memory_en() in t or advice_numbers.pooled_memory_short_ja() in t) else 'MISMATCH', ''))
    stale_ = {'README.md': ['independent reference implementation', 'Gazebo check is pending', 'Gazebo での確認は未了', '独立に書き直した参照実装', 'are pending. (3)'],
              'docs/paper/main.tex': ['Gazebo check is pending', 'machine-checked on the implementation', 'Moving beats thinking harder', r'(\PreregDrafts', 'dominated by fires hidden from the front view'],
              'docs/paper/supplement.tex': ['Gazebo check is still pending', 'check is still pending']}
    for fn_, needles in stale_.items():
        t_ = read(fn_)
        bad_ = [n_ for n_ in needles if n_ in t_]
        extra.append((f'{fn_}: no stale wording ({len(needles)} phrases)', 'MISMATCH' if bad_ else 'ok', ', '.join(bad_)))
    if (RES / 'i22_gazebo_check.log').is_file() and advice_numbers.interlock_check():
        extra.append(('paper macro IlcheckN equals the number of missions in i22_gazebo_check.log',
                      'ok' if mac_.get('IlcheckN') == str(advice_numbers.interlock_check()['missions']) else 'MISMATCH', ''))
    wf2_ = advice_numbers.w_facts() if (RES / 'w_summary.json').is_file() else None
    if wf2_:
        up4_ = float(mac_.get('WEpsAnyFourUpper', '0').rstrip('\\%'))
        stated_ = r'WEpsAnyFourUpper' in main_tex and 'registered for one station' in main_tex
        extra.append(('main.tex: eps_any(4) upper limit is stated against the registered 15% line when it exceeds it', 'ok' if (up4_ <= 15 or stated_) else 'MISMATCH', f'upper {up4_}%'))
        extra.append(('main.tex: the side-only subclass of W is printed next to the headline miss rate', 'ok' if (r'\WMissLASide' in main_tex and r'\WMissLASideCI' in main_tex) else 'MISMATCH', ''))

    # numbers.tex is what scripts/paper_numbers.py generates now
    try:
        import paper_numbers as pn
        with tempfile.TemporaryDirectory() as td:
            old_out, old_pend = pn.OUT, pn.PENDING_TEXT
            pn.OUT = Path(td)
            pn.OUT.mkdir(exist_ok=True)
            import io
            import contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                pn.main()
            pn.OUT, pn.PENDING_TEXT = old_out, old_pend
            ref_ = ROOT / (f'{SD}/paper' if SNAP else 'docs/paper')
            stale = [f.name for f in sorted(Path(td).glob('*.tex'))
                     if not (ref_ / f.name).is_file() or (ref_ / f.name).read_text(encoding='utf8') != f.read_text(encoding='utf8')]
        extra.append((f'{"docs/snapshot/paper" if SNAP else "docs/paper"}/numbers.tex and tab_*.tex up to date', 'MISMATCH' if stale else 'ok', f'stale: {stale}' if stale else ''))
    except Exception as exc:       # noqa: BLE001
        extra.append(('docs/paper/numbers.tex up to date', 'skip', f'cannot regenerate: {exc}'))

    # the registration ledger is generated from git (scripts/make_registrations.py)
    try:
        r_ = subprocess.run([sys.executable, str(ROOT / 'scripts/make_registrations.py'), '--check'], capture_output=True, text=True, cwd=ROOT)
        extra.append(('docs/REGISTRATIONS.md up to date (scripts/make_registrations.py)', 'ok' if r_.returncode == 0 else 'MISMATCH', r_.stdout.strip() if r_.returncode else ''))
    except Exception as exc:       # noqa: BLE001
        extra.append(('docs/REGISTRATIONS.md up to date', 'skip', str(exc)))
    # the FINDINGS count (rows of docs/FINDINGS.md) is the one stated in the prose of the other documents
    import count_tests
    nf_ = count_tests.n_findings()
    for fn_, pats_ in (('README.md', [r'初めて分かった(\d+)件']), ('docs/FINDINGS.md', [r'以下の(\d+)件']), ('docs/HANDOFF.md', [r'FINDINGS は (\d+) 件', r'実行で見つけた(\d+)件'])):
        for pat_ in pats_:
            got_ = re.findall(pat_, read(fn_))
            extra.append((f'{fn_}: FINDINGS count {nf_} ({pat_})', 'ok' if got_ and all(g_ == str(nf_) for g_ in got_) else 'MISMATCH', f'found {got_}' if not (got_ and all(g_ == str(nf_) for g_ in got_)) else ''))

    # the paper PDF: no red TBD, and no pending marker in the abstract
    mp = ROOT / (f'{SD}/paper/main.pdf' if SNAP else 'docs/paper/main.pdf')
    if mp.is_file() and not a.no_report:
        pt = pdf_text(mp)
        if pt is None:
            extra.append(('main.pdf text', 'skip', 'no pdftotext/docker'))
        else:
            abstract = re.split(r'(?i)introduction', pt, maxsplit=1)[0][:6000]
            extra.append(('main.pdf: abstract without pending marker', 'MISMATCH' if re.search(r'TBD|\(pending\)', abstract) else 'ok', ''))
            extra.append(('main.pdf: no red "TBD" text', 'MISMATCH' if 'TBD' in pt else 'ok', ''))
            try:   # page 1 in reading order (not -layout: that interleaves the two columns)
                p1_ = subprocess.run(['docker', 'run', '--rm', '-v', f'{mp.parent}:/w:ro', LATEX_IMG, 'pdftotext', '-f', '1', '-l', '1', f'/w/{mp.name}', '-'],
                                     capture_output=True, text=True).stdout
            except FileNotFoundError:
                p1_ = ''
            m_a, m_i = re.search(r'Abstract\s*[\u2014-]*', p1_), re.search(r'I\.\s*I\s*NTRODUCTION|INTRODUCTION', p1_)
            ab_txt = p1_[m_a.end():m_i.start()] if (m_a and m_i and m_i.start() > m_a.end()) else ''
            nw_ = len(ab_txt.split())
            extra.append((f'main.pdf: abstract length ({nw_} words; target <= 200)', 'ok' if nw_ <= 200 else 'warn', ''))
            if (ROOT / (f'{SD}/paper/numbers.tex' if SNAP else 'docs/paper/numbers.tex')).stat().st_mtime > mp.stat().st_mtime + 1:
                extra.append(('main.pdf newer than numbers.tex', 'warn', 'rebuild the paper (make paper)'))

    # ------------------------------------------------------------------ submission snapshot: pending = registered-not-run wording, never a TBD
    if SNAP:
        import advice_numbers
        import paper_numbers as pn_
        pend = advice_numbers.pending_list()
        extra.append((f'snapshot: studies without results = {", ".join(pend) or "none"}', 'ok', 'wording: ' + advice_numbers.PENDING_EN))
        word_rx = re.compile(r'TBD|\(pending\)|\bpending\b|\brunning\b|\bawaiting\b|実行中|結果待ち|実行待ち|評価中|not yet run(?! at submission)')
        pdf_rx = re.compile(r'TBD|\(pending\)|\bpending\b|registered at merge')      # the paper's own prose may say "running the stack" / "not yet run" (adaptive views)
        texts = {'README': docs['readme'], 'YouTube text': docs['yt'], 'report': docs.get('report')}
        mp_ = ROOT / SD / 'paper/main.pdf'
        if mp_.is_file() and not a.no_report:
            texts['main.pdf'] = pdf_text(mp_)
            sp_ = ROOT / SD / 'paper/supplement.pdf'
            if sp_.is_file():
                texts['supplement.pdf'] = pdf_text(sp_)
        for nm_, t_ in texts.items():
            if t_ is None:
                if nm_ != 'report' and nm_ not in ('main.pdf', 'supplement.pdf'):
                    extra.append((f'snapshot {nm_} exists', 'MISMATCH', 'not found: run make snapshot'))
                continue
            if not t_.strip():
                extra.append((f'snapshot {nm_} exists', 'MISMATCH', 'empty: run make snapshot'))
                continue
            hits = sorted({m_.group(0) for m_ in (pdf_rx if nm_.endswith('.pdf') else word_rx).finditer(t_)})
            extra.append((f'snapshot {nm_}: no TBD / pending / running / waiting marker', 'MISMATCH' if hits else 'ok', f'found {hits}' if hits else ''))
            if pend and nm_ in ('README', 'report', 'YouTube text'):
                has_ = advice_numbers.PENDING_JA in t_ or advice_numbers.PENDING_EN in t_
                extra.append((f'snapshot {nm_}: says that {", ".join(pend)} are registered, not yet run at submission', 'ok' if has_ else 'MISMATCH', ''))
        probs = pn_.snapshot_problems([ROOT / f'docs/paper/{f_}.tex' for f_ in ('main', 'supplement', 'sec_formal')], read(f'{SD}/paper/numbers.tex'), set(pend))
        extra.append(('snapshot paper sources: every number of a pending study is wrapped in its pending form (\\IfPend<study>)', 'MISMATCH' if probs else 'ok', '; '.join(probs[:3])))
        ex_ = pn_.snapshot_expand(read('docs/paper/main.tex'), set(pend))
        ab_ = ex_.split(r'\begin{abstract}')[-1].split(r'\end{abstract}')[0]
        if pend:
            extra.append(('snapshot abstract says that the pending studies were not run', 'ok' if 'not run at submission' in ab_.lower() else 'MISMATCH', ''))
            body_ = ex_.split(r'\section{Conclusion}')[-1]
            extra.append(('snapshot conclusion words the claim on pending study A conditionally' if 'A' in pend else 'snapshot conclusion',
                          'ok' if ('A' not in pend or 'not run at submission' in body_) else 'MISMATCH', ''))
        sc_ = advice_numbers.study_counts()
        if sc_:
            extra.append(('snapshot Table S9: studies without results = registered, not run', 'ok' if sc_['pending'] == len(pend) else 'MISMATCH', f"table says {sc_['pending']}, result files say {len(pend)}"))

    # ------------------------------------------------------------------ print
    w0 = max(len(r[0]) for r in rows) + 2 if rows else 10
    print(f"{'fact':<{w0}}{'expected':<28}{'README':<10}{'YouTube':<10}{'macro':<10}{'report':<10}")
    print('-' * (w0 + 68))
    skipped = 0
    for name, exp, c in rows:
        skipped += sum(v == 'skip' for v in c.values())
        print(f"{name:<{w0}}{exp[:26]:<28}{c['readme']:<10}{c['yt']:<10}{c['macro']:<10}{c['report']:<10}")
    print()
    for name, st, detail in extra:
        bad += st == 'MISMATCH'
        skipped += st == 'skip'
        print(f'{st:<9}{name}' + (f'  [{detail}]' if detail else ''))
    for f in F:
        for d in f.get('detail', []):
            print(f"  detail {f['name']}: {d}")
    print()
    print(f'{bad} mismatch(es), {skipped} skipped' + ('' if bad else ' -- consistent'))
    return 1 if bad or (a.strict and skipped) else 0


if __name__ == '__main__':
    sys.exit(main())
