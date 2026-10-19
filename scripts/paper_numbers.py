#!/usr/bin/env python3
"""Generate every number and results table used by the paper (docs/paper/numbers.tex, tab_*.tex).

  python3 scripts/paper_numbers.py

No number in docs/paper/main.tex is typed by hand: each one is a macro defined here from the result
files in experiments/results/.  Missing results are the macro \\TBD, which prints

  * a neutral grey "(pending)" in a normal build (PENDING_TEXT=1, the default unless FINAL=1), so that a safe,
    presentable PDF exists at any time;
  * the red "TBD" with PENDING_TEXT=0 (debugging);
  * FINAL=1 (or --final) refuses to build while any macro or table is still pending.
  * SNAPSHOT=1 (or --snapshot; `make snapshot`) is the submission snapshot: the studies without results (advice_numbers.snapshot_pending())
    print the pending form of every sentence that needs their numbers ("registered, not yet run at submission"), chosen in main.tex /
    supplement.tex by the generated switches \\IfPendA{pending}{normal} ... \\IfPendIF; no \\TBD survives (it prints "not run").  Studies
    with results keep their normal sentences.  FINAL and SNAPSHOT exclude each other.  `--out DIR` writes the macros and tables to DIR
    instead of docs/paper (the snapshot build never touches the tracked files).
"""
from __future__ import annotations
import json
import math
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_paths import FULL as FULL_RUNS  # noqa: E402
import advice_numbers  # noqa: E402
RES = ROOT / 'experiments/results'
OUT = ROOT / 'docs/paper'
if '--out' in sys.argv:
    OUT = Path(sys.argv[sys.argv.index('--out') + 1]).resolve()


def _num(x, nd=0):
    """Format a possibly missing number (e.g. no paired missions); \\TBD when absent."""
    return r'\TBD' if x is None else f'{x:.{nd}f}'


def wilson(k, n, z=1.959964):
    if not n:
        return (float('nan'), float('nan'))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def pct(x, nd=1):
    return f'{100 * x:.{nd}f}\\%'


def ci(k, n, nd=1):
    lo, hi = wilson(k, n)
    return f'[{100 * lo:.{nd}f}, {100 * hi:.{nd}f}]\\%'


def ledger(name):
    f = RES / name
    if not f.is_file():
        return None
    return [r for r in (json.loads(x) for x in f.read_text(encoding='utf8').splitlines()) if r.get('final', True)]


def all_attempts(name):
    f = RES / name
    return [json.loads(x) for x in f.read_text(encoding='utf8').splitlines()] if f.is_file() else []


FINAL = '--final' in sys.argv or os.environ.get('FINAL', '') not in ('', '0')
SNAPSHOT = '--snapshot' in sys.argv or advice_numbers.snapshot_mode()
if SNAPSHOT:
    os.environ['SNAPSHOT'] = '1'          # the other generators (advice_numbers) read the same switch
    if FINAL:
        raise SystemExit('FINAL=1 and SNAPSHOT=1 exclude each other: FINAL refuses any pending result, SNAPSHOT prints it as "registered, not yet run at submission"')
PENDING_TEXT = (not FINAL) and os.environ.get('PENDING_TEXT', '1') != '0'
# FINAL: a \TBD that survives anywhere (a literal one in main.tex/supplement.tex, a missing figure) is a LaTeX error, so the build fails
TBD_DEF = (r'\providecommand{\TBD}{\PackageError{rescuemind}{FINAL build: a pending (TBD) result remains}{Fill it or remove the sentence.}}' if FINAL
           else r'\providecommand{\TBD}{\SnapNA{}}' if SNAPSHOT
           else r'\providecommand{\TBD}{\textcolor{gray}{\textit{(pending)}}}' if PENDING_TEXT
           else r'\providecommand{\TBD}{\textbf{\textcolor{red}{TBD}}}')


def snapshot_head():
    """LaTeX switches of the submission snapshot: \\IfPendX{pending form}{normal form} for every study that may lack results."""
    pend = advice_numbers.snapshot_pending() if SNAPSHOT else set()
    h = [r'\newcommand{\SnapNA}{not run}',
         r'\newcommand{\IfSnapshot}[2]{%s}' % ('#1' if SNAPSHOT else '#2'),
         r'\newcommand{\IfAnyPend}[2]{%s}' % ('#1' if pend else '#2')]
    h += [r'\newcommand{\IfPend%s}[2]{%s}' % (advice_numbers.mkey(k), '#1' if k in pend else '#2') for k in advice_numbers.SNAPSHOT_STUDIES]
    h.append(r'\newcommand{\IfXDRRun}[2]{%s}' % ('#1' if (RES / 'xd_real_summary.json').is_file() else '#2'))      # XD stage r (real fire-free photographs) is a separate step of XD
    h.append(r'\newcommand{\TBDfor}[1]{\csname IfPend#1\endcsname{\SnapNA{}}{\TBD}}')      # a cell/number of study #1: "not run" in the snapshot, \TBD otherwise
    return h


def snapshot_expand(tex, pending, snapshot=True):
    """What LaTeX makes of the switches in `tex` for a given pending set (used by the tests and check_consistency to see the text a snapshot
    prints without compiling): \\IfPend<L>{a}{b}, \\IfAnyPend, \\IfSnapshot and \\TBDfor{L}; comment lines are dropped."""
    tex = '\n'.join(re.sub(r'(?<!\\)%.*$', '', ln) for ln in tex.splitlines())
    sw = re.compile(r'\\(IfPend[A-Za-z]+|IfAnyPend|IfSnapshot)(?![A-Za-z])|\\TBDfor\{([A-Za-z]+)\}')

    def group(t, i):
        while t[i].isspace():
            i += 1
        assert t[i] == '{', t[i:i + 40]
        d, j = 0, i
        while True:
            if t[j] == '\\':
                j += 2
                continue
            d += (t[j] == '{') - (t[j] == '}')
            j += 1
            if d == 0:
                return t[i + 1:j - 1], j

    out, i = [], 0
    while True:
        mm = sw.search(tex, i)
        if not mm:
            out.append(tex[i:])
            break
        out.append(tex[i:mm.start()])
        if mm.group(2):
            out.append(r'\SnapNA{}' if snapshot and advice_numbers.unmkey(mm.group(2)) in pending else r'\TBD')
            i = mm.end()
            continue
        a, j = group(tex, mm.end())
        b, j = group(tex, j)
        name = mm.group(1)
        on = snapshot and (bool(pending) if name == 'IfAnyPend' else True if name == 'IfSnapshot' else advice_numbers.unmkey(name[len('IfPend'):]) in pending)
        out.append(snapshot_expand(a if on else b, pending, snapshot))
        i = j
    return ''.join(out)


def check_final(m, tables, studies=False):
    """FINAL=1, the strict mode: any macro or table that is still \\TBD refuses the build (SystemExit)."""
    pend = [ln.split('}')[0].split('{\\')[1] for ln in m.lines[2:] if ln.endswith('{\\TBD}')]
    pend += [n for n, b in tables.items() if '\\TBD' in b]
    if studies:       # the real build: a study whose text is a 'not run' sentence is pending too
        pend += [f'study {k} (no result file)' for k, has in advice_numbers.pending_all().items() if not has]
    if pend:
        raise SystemExit(f'FINAL: {len(pend)} pending (TBD) macros/tables: {pend[:12]} ...')


def snapshot_problems(tex_files, numbers_text, pending):
    """What would still print a pending marker in a snapshot build: a literal \\TBD left after the switches are expanded (the definition of the
    figure-fallback box excepted) and every use of a result macro whose snapshot value is the clean "not run" fallback (i.e. a number that does
    not exist yet and that no \\IfPend<study>{pending}{normal} wraps).  [] means the snapshot text is complete."""
    na = {m.group(1) for m in re.finditer(r'\\newcommand\{\\([A-Za-z]+)\}\{\\SnapNA\{\}\}', numbers_text)}
    bad = []
    for f in tex_files:
        t = snapshot_expand(Path(f).read_text(encoding='utf8'), pending)
        t = '\n'.join(ln for ln in t.splitlines() if r'\newcommand{\fig}' not in ln)
        for mm in re.finditer(r'\\TBD(?![A-Za-z])', t):
            bad.append(f'{Path(f).name}: literal \\TBD near "{t[max(0, mm.start() - 50):mm.start() + 20].strip()}"')
        for mm in re.finditer(r'\\([A-Za-z]+)', t):
            if mm.group(1) in na:
                bad.append(f'{Path(f).name}: \\{mm.group(1)} (no result) near "{t[max(0, mm.start() - 50):mm.start() + 20].strip()}"')
    return bad


class Macros:
    def __init__(self):
        self.lines = ['% generated by scripts/paper_numbers.py -- do not edit', TBD_DEF]
        self.head = snapshot_head()        # the switches \\IfPendA ... (always defined, so that main.tex builds in every mode)
        self.names = set()

    def __setitem__(self, name, value):
        assert name.isalpha(), name
        self.names.add(name)
        self.lines.append(f'\\newcommand{{\\{name}}}{{{value}}}')

    def lookup(self, name):
        """The value set for `name`, or None (so a status macro can say 'pending' instead of \\TBD)."""
        for ln in reversed(self.lines):
            if ln.startswith(f'\\newcommand{{\\{name}}}{{'):
                v = ln[len(f'\\newcommand{{\\{name}}}{{'):-1]
                return None if v == r'\TBD' else v
        return None

    def override(self, name, value):
        """Replace the value of an already set macro (the snapshot wording of a status macro)."""
        for i, ln in enumerate(self.lines):
            if ln.startswith(f'\\newcommand{{\\{name}}}{{'):
                self.lines[i] = f'\\newcommand{{\\{name}}}{{{value}}}'
                return
        self[name] = value

    def pending(self, names):
        for n in names:
            if n not in self.names:
                self[n] = r'\TBD'

    def text(self):
        rest = self.lines[2:]
        if SNAPSHOT:      # a pending value that nothing wrapped in a pending form prints a clean "not run", never a TBD
            rest = [re.sub(r'\\TBD(?![A-Za-z])', lambda _: r'\SnapNA{}', ln) for ln in rest]
        return '\n'.join(self.lines[:2] + self.head + rest) + '\n'


def campaign(m: Macros, prefix: str, file: str):
    rows = ledger(file)
    if not rows:
        return None
    n = len(rows)
    ok = sum(r['correct'] for r in rows)
    wrong = sum(r['observed_action'] in ('ALLOW', 'ALLOW_AFTER_SEARCH') and r['expected_action'].startswith('DENY')
                for r in rows)
    lat = sorted(r['vlm_latency_s'] for r in rows if r.get('vlm_latency_s') is not None)
    retries = len(all_attempts(file)) - n
    m[f'{prefix}N'] = n
    m[f'{prefix}Correct'] = ok
    m[f'{prefix}CorrectCI'] = ci(ok, n)
    m[f'{prefix}Wrong'] = wrong
    m[f'{prefix}WrongCI'] = ci(wrong, n)
    m[f'{prefix}LatMed'] = f'{statistics.median(lat):.2f}' if lat else r'\TBD'
    m[f'{prefix}LatMax'] = f'{max(lat):.2f}' if lat else r'\TBD'
    m[f'{prefix}Retries'] = retries
    wall = [r['wall_s'] for r in rows if r.get('wall_s')]
    m[f'{prefix}WallMed'] = f'{statistics.median(wall):.0f}' if wall else r'\TBD'
    return rows


def _pfmt(b, c):
    """Exact two-sided McNemar p from discordant counts, in LaTeX (tiny values in powers of ten, never 0.0000)."""
    import math
    n, k = b + c, min(b, c)
    pv = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0   # exact two-sided McNemar
    if pv >= 1e-4:
        return f"{pv:.4f}"
    e = math.floor(math.log10(pv))
    return f"{pv / 10 ** e:.1f}\\times10^{{{e}}}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    m = Macros()
    import count_tests
    nt, nf = count_tests.n_tests(), count_tests.n_findings()
    m['NTests'] = str(nt) if nt is not None else r'\TBD'      # scripts/count_tests.py (run in rm-dev)
    m['NFindings'] = str(nf)                                     # rows of the main table in docs/FINDINGS.md
    # ---- campaign C (v3.3, 30 trials) and D (v3.4, 42 trials)
    c_rows = ledger('campaign_ledger.jsonl')
    if c_rows:
        m['CN'] = len(c_rows)
        m['CVlmCorrect'] = sum(r.get('vlm_correct', r.get('correct', False)) for r in c_rows)
    d_rows = campaign(m, 'D', 'campaign_D_ledger.jsonl')
    # ---- campaign E (randomised worlds)
    e_rows = campaign(m, 'E', 'campaign_E_ledger.jsonl')
    tables = {}
    if e_rows:
        safe = [r for r in e_rows if r['expected_action'] in ('ALLOW', 'DELIVER_AFTER_SEARCH')]
        ts = sum(r['correct'] for r in safe)
        m['ESafeN'] = len(safe)
        m['ETaskSuccess'] = ts
        m['ETaskSuccessCI'] = ci(ts, len(safe))
        # counterfactual baselines (same observations)
        b0_wrong = sum(r['expected_action'] != 'ALLOW' for r in e_rows)   # blind: delivers what is at the station
        b0_task = sum(r['expected_action'] == 'ALLOW' for r in e_rows)
        b1_task = sum(r['expected_action'] == 'ALLOW' and r['correct'] for r in e_rows)  # no recovery: swapped fails
        b1_wrong = sum(r.get('first_checkpoint_allow', False) and r['expected_action'] != 'ALLOW' for r in e_rows)
        m['EBzeroWrong'] = b0_wrong
        m['EBzeroWrongCI'] = ci(b0_wrong, len(e_rows))
        m['EBzeroTask'] = b0_task
        m['EBoneWrong'] = b1_wrong
        m['EBoneTask'] = b1_task
        strata = defaultdict(lambda: [0, 0, Counter()])
        proto = {t['id']: t for t in json.loads((ROOT / 'experiments/campaign_e_protocol.json').read_text())['trials']}
        for r in e_rows:
            t = proto[r['trial_id']]
            key = (t['expected_action'], t['condition'])
            strata[key][0] += 1
            strata[key][1] += r['correct']
            strata[key][2][r['observed_action']] += 1
        lines = [r'\begin{tabular}{llrrl}', r'\toprule', r'Expected & Condition & $n$ & Correct & Observed \\', r'\midrule']
        for (exp, cond), (n, ok, obs) in sorted(strata.items()):
            o = ', '.join(f'{k.replace("_", " ").lower()} {v}' for k, v in obs.most_common())
            lines.append(f'{exp.replace("_", " ").lower()} & {cond.replace("_", " ")} & {n} & {ok} & {o} \\\\')
        lines += [r'\bottomrule', r'\end{tabular}']
        tables['tab_e_strata.tex'] = '\n'.join(lines)
    # ---- held-out instruction parsing
    it = json.loads((RES / 'intent_hybrid_selected_qwen35_9b_i35.json').read_text())['summary']
    tf = json.loads((RES / 'intent_tfidf.json').read_text())['summary']
    m['IntN'] = it['n']; m['IntCorrect'] = it['correct']; m['IntUnsafe'] = it['unsafe_accepts']
    m['IntTfidfCorrect'] = tf['correct']; m['IntTfidfUnsafe'] = tf['unsafe_accepts']
    # ---- T1 held-out checkpoint test
    t1f = RES / 't1_summary.json'
    if t1f.is_file():
        t1 = json.loads(t1f.read_text())
        p = t1['models'].get('Qwen3.5-9B')
        if p:
            f = p['rules']['full']
            m['TNimages'] = p['n_images']; m['TNamb'] = p['n_ambiguous']
            m['TNdeny'] = f['n_deny']; m['TNallow'] = f['n_allow']
            m['TFA'] = f['false_approvals']; m['TFARate'] = pct(f['fa_rate'])
            m['TFACI'] = f"[{100 * f['fa_ci95'][0]:.1f}, {100 * f['fa_ci95'][1]:.1f}]\\%"
            m['TCA'] = f['correct_approvals']; m['TCARate'] = pct(f['ca_rate'])
            m['TCACI'] = f"[{100 * f['ca_ci95'][0]:.1f}, {100 * f['ca_ci95'][1]:.1f}]\\%"
            m['THazRecall'] = f"{p['hazard_recall'][0]}/{p['hazard_recall'][1]}"
            m['TConeAlarm'] = f"{p['hazard_false_alarm_cone'][0]}/{p['hazard_false_alarm_cone'][1]}"
            m['TLatPass'] = f"{p['latency_per_pass_s']['median']:.2f}"
            m['TAmbAllowed'] = p['ambiguous_allowed']
            cb, cb35 = p.get('cluster_bootstrap_full'), p.get('cluster_bootstrap_v35')
            if cb:
                fmt = lambda v: f"[{100 * v[0]:.1f}, {100 * v[1]:.1f}]\\%"
                m['TFACluster'] = fmt(cb['fa_ci95_cluster']); m['TvFACluster'] = fmt(cb35['fa_ci95_cluster'])
                m['TNworlds'] = cb['n_worlds']
            st = p['strata_full']
            sup = [v for k, v in st.items() if v['expected'] == 'deny' and not k.startswith('fire_visible')]
            m['TSupplyN'] = sum(v['n'] for v in sup); m['TSupplyFA'] = sum(v['allowed'] for v in sup)
            m['TSupplyFACI'] = ci(m_supply := sum(v['allowed'] for v in sup), sum(v['n'] for v in sup))
            fc = st.get('fire_visible_correct_supply', {'n': 0, 'allowed': 0})
            m['TFireCorrectN'] = fc['n']; m['TFireCorrectFA'] = fc['allowed']
            m['TAblNoHazFA'] = p['rules']['A3_no_hazard_question']['false_approvals']
            v = p['rules'].get('v35_tau_h_0.05')
            if v:
                m['TvFA'] = v['false_approvals']; m['TvFARate'] = pct(v['fa_rate'])
                m['TvFACI'] = f"[{100 * v['fa_ci95'][0]:.1f}, {100 * v['fa_ci95'][1]:.1f}]\\%"
                m['TvCA'] = v['correct_approvals']; m['TvCARate'] = pct(v['ca_rate'])
                m['TvCACI'] = f"[{100 * v['ca_ci95'][0]:.1f}, {100 * v['ca_ci95'][1]:.1f}]\\%"
                m['TvHazRecall'] = '/'.join(map(str, p['hazard_recall_tau_h_0.05']))
                m['TvConeAlarm'] = '/'.join(map(str, p['hazard_false_alarm_cone_tau_h_0.05']))
                m['TvNoFireAlarm'] = '/'.join(map(str, p['hazard_false_alarm_all_no_fire_tau_h_0.05']))
                m['TNoFireAlarm'] = '/'.join(map(str, p['hazard_false_alarm_all_no_fire']))
        m3 = t1['models'].get('Qwen2.5-VL-3B')
        if m3:
            m['TThreeBPassTwoFA'] = m3['rules']['A2_pass2_only']['false_approvals']
            m['TThreeBFullFA'] = m3['rules']['full']['false_approvals']
        jm = t1.get('json_method', {})
        if isinstance(jm.get('Qwen3.5-9B'), dict):
            m['TJsonNineFA'] = jm['Qwen3.5-9B']['false_approvals']; m['TJsonNineCA'] = jm['Qwen3.5-9B']['correct_approvals']
        if isinstance(jm.get('Qwen2.5-VL-3B'), dict):
            m['TJsonThreeErr'] = jm['Qwen2.5-VL-3B']['parse_or_inference_errors']
            m['TJsonThreeCA'] = jm['Qwen2.5-VL-3B']['correct_approvals']
        rec = [mm['hazard_recall'] for mm in t1['models'].values()]
        m['THazMin'] = min(r[0] for r in rec); m['THazMax'] = max(r[0] for r in rec); m['TNfireVis'] = rec[0][1]
        recs9 = json.loads((RES / 'devset_t1_qwen35_9b.json').read_text())['records']
        vis = [r for r in recs9 if r['hazard_visibility'] == 'visible']
        hz = lambda r: max(r['passes'][k]['scores']['hazard_prob'] for k in '12')
        big = [r for r in vis if r['fire_pixels'] >= 10000]; small = [r for r in vis if r['fire_pixels'] < 10000]
        m['TLargeDet'] = f"{sum(hz(r) >= 0.05 for r in big)}/{len(big)}"
        m['TSmallDet'] = f"{sum(hz(r) >= 0.05 for r in small)}/{len(small)}"
        # model table
        lines = [r'\begin{tabular}{lrrrrr}', r'\toprule',
                 r'Model & False approvals & Correct approvals & Hazard recall & Cone alarms & s/pass \\', r'\midrule']
        for name, mm in t1['models'].items():
            f = mm['rules']['full']
            lines.append(f"{name} & {f['false_approvals']}/{f['n_deny']} & {f['correct_approvals']}/{f['n_allow']} & "
                         f"{mm['hazard_recall'][0]}/{mm['hazard_recall'][1]} & {mm['hazard_false_alarm_cone'][0]}/{mm['hazard_false_alarm_cone'][1]} & "
                         f"{mm['latency_per_pass_s']['median']:.2f} \\\\")
        for name, v in t1.get('json_method', {}).items():
            if isinstance(v, dict):
                lines.append(f"{name} (free JSON) & {v['false_approvals']}/{v['n_deny']} & {v['correct_approvals']}/{v['n_allow']} & -- & -- & -- \\\\")
        lines += [r'\bottomrule', r'\end{tabular}']
        tables['tab_t1_models.tex'] = '\n'.join(lines)
        # ablation table (all scored models)
        names = {'full': 'Full rule', 'A1_pass1_only': 'A1: question 1 only', 'A2_pass2_only': 'A2: question 2 only',
                 'A3_no_hazard_question': 'A3: no hazard question', 'A4_no_confidence_threshold': r'A4: no threshold ($\tau_s{=}0$)',
                 'v35_tau_h_0.05': r'v3.5: $\tau_h{=}0.05$ (I-10)'}
        models = list(t1['models'])
        lines = [r'\begin{tabular}{l' + 'r' * len(models) + '}', r'\toprule',
                 'Decision rule & ' + ' & '.join(models) + r' \\', r'\midrule']
        for k, label in names.items():
            cells = []
            for name in models:
                v = t1['models'][name]['rules'][k]
                cell = f"{v['false_approvals']} / {v['n_allow'] - v['correct_approvals']}"
                if k != 'full' and v['vs_full']['mcnemar_p'] < 0.05:
                    cell += r'$^{*}$'
                cells.append(cell)
            lines.append(label + ' & ' + ' & '.join(cells) + r' \\')
        lines += [r'\bottomrule', r'\end{tabular}']
        tables['tab_t1_ablation.tex'] = '\n'.join(lines)
    # ---- timing breakdown of delivered, non-recovery missions (campaign D, and E when present)
    phases = [('drive to station', None, 'supply_station'), ('aim camera', 'supply_station', 'camera_aim_aligned'),
              ('wait until stationary', 'camera_aim_aligned', 'checkpoint_stationary_verified'),
              ('acquire and check frames', 'checkpoint_stationary_verified', 'checkpoint_frame'),
              ('VLM decision (scored queries)', 'checkpoint_frame', 'checkpoint_decision'),
              ('situation report (not used to decide)', 'checkpoint_decision', 'checkpoint_explanation'),
              ('drive to shelter', 'checkpoint_explanation', 'shelter_approach')]
    lines = [r'\begin{tabular}{lrrr}', r'\toprule', r'Phase & Median [s] & Min & Max \\', r'\midrule']
    durs = defaultdict(list)
    tf = RES / 'timing_runs.json'   # written by scripts/export_run_evidence.py from outputs/runs
    timing_runs = json.loads(tf.read_text()) if tf.is_file() else {}
    for rows in (d_rows or [], e_rows or []):
        for r in rows:
            if r['observed_action'] != 'ALLOW':
                continue
            mf = FULL_RUNS / r['run_id'] / 'mission.json'   # full record if present, else the committed export
            if mf.is_file():
                ev = {e['stage']: e.get('t_wall_s') for e in json.loads(mf.read_text())['events']}
            elif r['run_id'] in timing_runs:
                ev = timing_runs[r['run_id']]
            else:
                continue
            for name, a, b in phases:
                if b in ev and (a is None or a in ev):
                    durs[name].append(ev[b] - (ev[a] if a else 0.0))
    for name, _, _ in phases:
        v = durs.get(name)
        if v:
            lines.append(f'{name} & {statistics.median(v):.2f} & {min(v):.2f} & {max(v):.2f} \\\\')
    n_timing = len(durs.get('drive to shelter', []))
    lines += [r'\bottomrule', r'\end{tabular}']
    tables['tab_timing.tex'] = '\n'.join(lines)
    m['TimingN'] = n_timing
    med = {k: statistics.median(v) for k, v in durs.items() if v}
    if len(med) == len(phases):
        m['TimDrive'] = f"{med['drive to station'] + med['drive to shelter']:.0f}"   # sum of phase medians
        m['TimCheck'] = f"{sum(med[k] for k in ('aim camera', 'wait until stationary', 'acquire and check frames', 'VLM decision (scored queries)')):.1f}"
        m['TimVlm'] = f"{med['VLM decision (scored queries)']:.1f}"
    # ---- I-13 development selection table
    sf = RES / 'i13_selection.json'
    if sf.is_file():
        sel = json.loads(sf.read_text())
        keep = ['Q9B[h35_full] tau_h=0.05', 'Q9B[h35_tiles] tau_h=0.05', 'Q9B[h36_full] tau_h=0.05', 'Q9B[h36_tiles] tau_h=0.05',
                'Q4B tau_h=0.05', 'J(Clef) tau_h=0.35', 'J2(Clef-task) tau_h=0.05', 'J2(Clef-task,0.05)+Q9B[h36_tiles]']
        label = {'Q9B[h35_full] tau_h=0.05': 'v3.5: Qwen3.5-9B', 'Q9B[h35_tiles] tau_h=0.05': '+ enlarged crops',
                 'Q9B[h36_full] tau_h=0.05': '+ hidden-fire wording', 'Q9B[h36_tiles] tau_h=0.05': '+ wording + crops (v3.6)',
                 'Q4B tau_h=0.05': 'Qwen3.5-4B', 'J(Clef) tau_h=0.35': 'Clef-Flash, original Jev request',
                 'J2(Clef-task) tau_h=0.05': 'Clef-Flash, task wording',
                 'J2(Clef-task,0.05)+Q9B[h36_tiles]': 'Clef (task) + Qwen (v3.6), both approve'}
        rows = {t['config']: t for t in sel['table']}
        lines = [r'\begin{tabular}{lrrrl}', r'\toprule', r'Configuration & False appr. & Correct appr. & Fires refused & One V100 \\', r'\midrule']
        for k in keep:
            t = rows.get(k)
            if t:
                lines.append(f"{label[k]} & {t['false_approvals']}/{t['n_deny']} & {t['correct_approvals']}/{t['n_allow']} & "
                             f"{t['dh_fire_refused']}/{t['n_dh_fire']} & {'yes' if t['deployable_one_v100'] else 'no'} \\\\")
        lines += [r'\bottomrule', r'\end{tabular}']
        tables['tab_i13_dev.tex'] = '\n'.join(lines)
        b = rows.get('Q9B[h36_tiles] tau_h=0.05'); a = rows.get('Q9B[h35_full] tau_h=0.05')
        if a and b:
            m['DevFAvThreeFive'] = a['false_approvals']; m['DevFAB'] = b['false_approvals']
            m['DevFireN'] = a['n_dh_fire']
    # ---- campaign F (paired closed-loop A/B)
    ff = RES / 'f_summary.json'
    if ff.is_file():
        f = json.loads(ff.read_text())
        pr = f['primary']
        m['FPairs'] = pr['n_world_pairs_fire_visible_both']; m['FWrongA'] = pr['wrong_deliveries_A']
        m['FWrongB'] = pr['wrong_deliveries_B']; m['FMcNemarP'] = f"{pr['mcnemar_p']:.4f}"
        m['FDiscA'] = pr['discordant_A_only']; m['FDiscB'] = pr['discordant_B_only']
        for cfg in ('A', 'B'):
            c = f['per_config'][cfg]
            m[f'FCorrect{cfg}'] = f"{c['correct']}/{c['n']}"; m[f'FFalseStop{cfg}'] = f"{c['false_hazard_stops']}/{c['fire_free_trials']}"
            m[f'FLat{cfg}'] = f"{c['latency_median_s']:.1f}" if c['latency_median_s'] is not None else r'\TBD'
    # ---- T2 (held-out confirmation)
    tf = RES / 't2_summary.json'
    if tf.is_file():
        t2 = json.loads(tf.read_text())
        ref, selc = t2['results'].get(t2['reference']), t2['results'].get(t2['selected'])
        b = t2['results'].get('Q9B[h36_tiles] tau_h=0.05')
        for key, r in (('Ref', ref), ('Sel', selc), ('B', b)):
            if r:
                m[f'TT{key}FA'] = f"{r['false_approvals']}/{r['n_deny']}"; m[f'TT{key}CA'] = f"{r['correct_approvals']}/{r['n_allow']}"
                m[f'TT{key}Small'] = '/'.join(map(str, r['fire_small_refused']))
                if 'vs_v35_false_approval_mcnemar' in r:
                    m[f'TT{key}P'] = f"{r['vs_v35_false_approval_mcnemar'][2]:.3f}"
    # ---- T2: Clef-Flash alone (task wording)
    if tf.is_file():
        cj = t2['results'].get('J2(Clef-task) tau_h=0.05')
        if cj:
            m['TTClefFA'] = f"{cj['false_approvals']}/{cj['n_deny']}"; m['TTClefCA'] = f"{cj['correct_approvals']}/{cj['n_allow']}"
        cq = t2['results'].get('J2(Clef-task,0.05)+Q4B')   # the on-robot pair (Qwen3.5-4B + Clef-Flash)
        if cq:
            m['TTPairFA'] = f"{cq['false_approvals']}/{cq['n_deny']}"; m['TTPairCA'] = f"{cq['correct_approvals']}/{cq['n_allow']}"
    # ---- campaign G (look-around, paired)
    gf = RES / 'g_summary.json'
    if gf.is_file():
        g = json.loads(gf.read_text()); pr = g['primary']
        m['GPairs'] = pr['n_world_pairs_fire_perceivable']; m['GWrongB'] = pr['wrong_deliveries_B']
        m['GWrongC'] = pr['wrong_deliveries_C']; m['GMcNemarP'] = f"{pr['mcnemar_p']:.4f}"
        # R5 #1: plug-in value of the per-check error budget with look-around (eps_hat = wrong_C / pairs) and k = 2
        _lo, _hi = wilson(pr['wrong_deliveries_C'], pr['n_world_pairs_fire_perceivable'])
        m['GEpsHat'] = f"{pr['wrong_deliveries_C'] / pr['n_world_pairs_fire_perceivable']:.3f}"; m['GEpsUpper'] = f"{_hi:.2f}"
        m['GKEpsHat'] = f"{2 * pr['wrong_deliveries_C'] / pr['n_world_pairs_fire_perceivable']:.3f}"; m['GKEpsUpper'] = f"{2 * _hi:.2f}"
        m['GDiscB'] = pr['discordant_B_only']; m['GDiscC'] = pr['discordant_C_only']
        for cfg in ('B', 'C'):
            c = g['per_config'][cfg]
            m[f'GCorrect{cfg}'] = f"{c['correct']}/{c['n']}"; m[f'GFalseStop{cfg}'] = f"{c['false_hazard_stops']}/{c['fire_free_trials']}"
        led = [json.loads(x) for x in (RES / 'campaign_G_ledger.jsonl').read_text().splitlines()]
        led = [r for r in led if r.get('final', True) and r['observed_action'] in ('ALLOW', 'ALLOW_AFTER_SEARCH') and r.get('wall_s')]
        for cfg in ('B', 'C'):
            w = sorted(r['wall_s'] for r in led if r.get('config') == cfg)
            m[f'GWall{cfg}'] = f"{statistics.median(w):.0f}" if w else r'\TBD'
        # like-for-like look-around cost: delivered fire-free ("plain") runs only, same worlds in both arms
        pw = {cfg: statistics.median(r['wall_s'] for r in led if r.get('config') == cfg and r.get('condition') == 'plain')
              for cfg in ('B', 'C')}
        m['GWallPlainB'] = f"{pw['B']:.0f}"; m['GWallPlainC'] = f"{pw['C']:.0f}"; m['GLookCost'] = f"{pw['C'] - pw['B']:.0f}"
    # ---- study R (camera degradations, T2 subset)
    rf = RES / 'r_summary.json'
    if rf.is_file():
        r = json.loads(rf.read_text())
        m['RNimg'] = r['n_images']; m['RNdeny'] = r['n_deny']; m['RNallow'] = r['n_allow']; m['RNfire'] = r['n_visible_fire']
        m['RNcond'] = len(r['conditions']); m['RNworlds'] = r['n_worlds']
        p1 = r['P1_pooled']
        m['RPoolFA'] = f"{p1['false_approvals']}/{p1['n']}"
        # a world-cluster bootstrap interval is degenerate at zero events; report the Wilson upper bound instead
        m['RPoolCI'] = (f"[{100 * p1['cluster_ci95'][0]:.2f}, {100 * p1['cluster_ci95'][1]:.2f}]\\%" if p1['cluster_ci95'][1] > 0
                        else f"(degenerate at zero events; Wilson upper bound {100 * wilson(p1['false_approvals'], p1['n'])[1]:.2f}\\%)")
        m['RPoolSupported'] = 'supported' if p1['supported'] else 'not supported'
        m['RUnsafeConds'] = len(r['P2_unsafe_conditions'])
        cas = {c: o['correct_approvals'] for c, o in r['conditions'].items()}
        worst = min(cas, key=cas.get)
        m['RWorstCond'] = worst.replace('_', ' '); m['RWorstCA'] = f"{cas[worst]}/{r['n_allow']}"
        m['RCleanCA'] = f"{r['clean']['correct_approvals']}/{r['n_allow']}"
        m['RGateRej'] = sum(o['gate_rejected'] for o in r['conditions'].values())
        m['RFireMissMax'] = max(o['fire_missed'] for o in r['conditions'].values())
        # per-condition image-level bound: every condition re-uses the same n_deny must-refuse images, so pooling repeats them
        kmax = max(o['false_approvals'] for o in r['conditions'].values())
        m['RCondFAMax'] = f"{kmax}/{r['n_deny']}"
        m['RCondFAUpper'] = f"{100 * wilson(kmax, r['n_deny'])[1]:.2f}\\%"
        tab = ROOT / 'docs/paper/tab_r.tex'
        if tab.is_file():
            tables['tab_r.tex'] = tab.read_text().replace('% generated by scripts/paper_numbers.py\n', '').rstrip('\n')
    # ---- second-model overlap on development data (scripts/jev_overlap.py)
    jf = RES / 'jev_overlap.json'
    if jf.is_file():
        jo = json.loads(jf.read_text())['full_rule']
        m['JevOvN'] = jo['n_fires']; m['JevOvBoth'] = jo['both_miss']; m['JevOvQOnly'] = jo['qwen_only_miss']
        m['JevOvCOnly'] = jo['clef_only_miss']; m['JevOvNeither'] = jo['neither_miss']
        m['JevOvQ'] = jo['qwen_miss']; m['JevOvC'] = jo['clef_miss']
        m['JevOvCond'] = f"{100 * jo['p_clef_miss_given_qwen_miss']:.0f}\\%"
        m['JevOvCondCI'] = f"[{100 * jo['p_clef_miss_given_qwen_miss_wilson'][0]:.0f}, {100 * jo['p_clef_miss_given_qwen_miss_wilson'][1]:.0f}]\\%"
        m['JevOvJaccard'] = f"{jo['jaccard']:.2f}"
        jh = json.loads(jf.read_text())['hazard_question_only']
        m['JevOvHBoth'] = jh['both_miss']; m['JevOvHQ'] = jh['qwen_miss']; m['JevOvHC'] = jh['clef_miss']
    # ---- campaign H (cross-mission memory)
    hf = RES / 'h_summary.json'
    if hf.is_file():
        h = json.loads(hf.read_text())
        p1, p2, p3 = h['P1_efficiency_relocation_persist'], h['P2_safety_naive_vs_verified'], h['P3_no_extra_risk_vs_v36']
        for arm, k in (('M0', 'zero'), ('M1', 'one'), ('M2', 'two')):
            m[f'HWrong{k}'] = h['per_arm'][arm]['wrong_supply']; m[f'HFire{k}'] = h['per_arm'][arm]['into_fire']
        bt0, bt2 = h['per_arm']['M0']['by_transition'], h['per_arm']['M2']['by_transition']
        m['HChangeMzero'] = _num(bt0.get('relocation_change', {}).get('time_median_s')); m['HChangeMtwo'] = _num(bt2.get('relocation_change', {}).get('time_median_s'))
        import collections as _col
        seq = _col.defaultdict(lambda: _col.defaultdict(bool))
        for t in h['trials']:
            if t['k'] > 1:
                seq[t['sequence']][t['arm']] |= bool(t['unsafe_delivery'])
        b1 = sum(v['M1'] and not v['M2'] for v in seq.values()); c1 = sum(v['M2'] and not v['M1'] for v in seq.values())
        m['HSeqN'] = len(seq); m['HSeqMone'] = sum(v['M1'] for v in seq.values()); m['HSeqMtwo'] = sum(v['M2'] for v in seq.values())
        m['HSeqP'] = _pfmt(b1, c1)
        m['HUnsafeUpperzero'] = f"{100 * h['per_arm']['M0']['unsafe_ci95'][1]:.0f}"; m['HUnsafeUppertwo'] = f"{100 * h['per_arm']['M2']['unsafe_ci95'][1]:.0f}"
        m['HFasterPairs'] = f"{sum(1 for d in p1['diff_M2_minus_M0_s'] if d < 0)}/{p1['n_pairs']}"
        m['HPOneN'] = p1['n_pairs']; m['HTimeMzero'] = _num(p1['time_M0_median_s']); m['HTimeMtwo'] = _num(p1['time_M2_median_s'])
        m['HTimeDiff'] = _num(None if p1['median_diff_s'] is None else -p1['median_diff_s']); m['HPOneP'] = f"{p1['wilcoxon_exact_p']:.4f}"
        m['HPTwoN'] = p2['n_pairs']; m['HUnsafeMone'] = p2['unsafe_M1']; m['HUnsafeMtwo'] = p2['unsafe_M2']; m['HPTwoP'] = _pfmt(p2['discordant_M1_only'], p2['discordant_M2_only'])
        m['HUnsafeMzero'] = p3['unsafe_M0']
        # caution denominator: M2 missions (2-3) where memory tightened tau_h at a station; only those whose station had no perceivable fire can show a false refusal
        caut = [t for t in h['trials'] if t['arm'] == 'M2' and t['k'] > 1 and t.get('caution')]
        cfree = [t for t in caut if not t['fire_perceivable_at']]
        m['HCautN'] = len(caut); m['HCautFire'] = len(caut) - len(cfree); m['HCautFree'] = len(cfree)
        m['HCautFalse'] = sum(bool(t['false_refusal']) for t in cfree)
        m['HCautFalseUpper'] = f"{100 * wilson(sum(bool(t['false_refusal']) for t in cfree), len(cfree))[1]:.0f}\\%"
        m['HCautStopped'] = sum(t['observed'] == 'DENY_HAZARD' for t in caut if t['fire_perceivable_at'])
        m['HHeadline'] = 'supported' if h['headline_supported'] else 'not supported'
        for arm in ('M0', 'M1', 'M2'):
            a = h['per_arm'][arm]; k = {'M0': 'zero', 'M1': 'one', 'M2': 'two'}[arm]
            m[f'HFalseRef{k}'] = a['false_refusals']; m[f'HTimeAll{k}'] = _num(a['time_median_s'])
            m[f'HSafeCorrect{k}'] = f"{a['safe_correct_deliveries']}/{a['safe_option_missions']}"
            m[f'HFailed{k}'] = a['failed']
        rows = [r'\begin{tabular}{lrrrrr}', r'\toprule',
                r'Arm & Unsafe & Wrong supply & Into fire & False refusals & Median time [s] \\', r'\midrule']
        names = {'M0': 'M0 no memory (v3.6)', 'M1': 'M1 naive memory', 'M2': 'M2 verified memory (ours)'}
        for arm in ('M0', 'M1', 'M2'):
            a = h['per_arm'][arm]
            rows.append(f"{names[arm]} & {a['unsafe_deliveries']}/{a['n'] - a['failed']} & {a['wrong_supply']} & {a['into_fire']} & "
                        f"{a['false_refusals']} & {_num(a['time_median_s'])} \\\\")
        rows += [r'\bottomrule', r'\end{tabular}']
        tables['tab_h_arms.tex'] = '\n'.join(rows)
        # supplementary table: every paired mission (sequence, k) with the outcome and time under M0/M1/M2
        sym = {'deliver': r'\checkmark', 'unsafe': r'$\times$', 'refuse': r'$\circ$', 'false': r'$\triangle$', 'failed': 'F'}

        def cell(t):
            if t is None:
                return '--'
            o = ('failed' if t['failed'] else 'unsafe' if t['unsafe_delivery'] else 'deliver' if t['delivered']
                 else 'false' if t['false_refusal'] else 'refuse')
            tm = t.get('mission_time_s')
            return sym[o] + (f' ({tm:.0f}\\,s)' if tm is not None else '')
        by = {}
        for t in h['trials']:
            if t['k'] > 1:
                by.setdefault((t['sequence'], t['k']), {})[t['arm']] = t
        hr = [r'\begin{tabular}{rlllllc}', r'\toprule',
              r'Seq & Story & Transition & M0 & M1 & M2 & M2 source \\', r'\midrule']
        for (sq, k), v in sorted(by.items(), key=lambda kv: (str(kv[0][0]).zfill(4), kv[0][1])):
            ref = v.get('M2') or next(iter(v.values()))
            m2 = v.get('M2') or {}
            src = [n for n, on in (('memory', m2.get('first_station')), ('caution', m2.get('caution'))) if on]
            hr.append(f"{sq}.{k} & {ref['story']} & {(ref['transition'] or '--').replace('_', ' ')} & "
                      f"{cell(v.get('M0'))} & {cell(v.get('M1'))} & {cell(v.get('M2'))} & {'+'.join(src) or '--'} \\\\")
        hr += [r'\bottomrule', r'\end{tabular}']
        tables['tab_h_sequences.tex'] = '\n'.join(hr)
    cr = RES / 'h_change_rate.json'
    if cr.is_file():
        c = json.loads(cr.read_text())
        m['HModelPdet'] = f"{c['rates']['p_det']:.2f}"; m['HModelPdetN'] = c['rates']['p_det_n']
        q = c['q']; i = q.index(0.2) if 0.2 in q else len(q) // 2
        m['HModelQ'] = q[i]
        for arm, k in (('M0', 'zero'), ('M1', 'one'), ('M2', 'two')):
            m[f'HModelUnsafe{k}'] = c['policies'][arm][i]['unsafe_per_100']; m[f'HModelTime{k}'] = c['policies'][arm][i]['mean_time_s']
        for tag, qq in (('Zero', 0.0), ('Half', 0.5)):
            if qq in q:
                j_ = q.index(qq); pol = c['policies']
                sn = pol['M0'][j_]['mean_time_s'] - pol['M1'][j_]['mean_time_s']; sv = pol['M0'][j_]['mean_time_s'] - pol['M2'][j_]['mean_time_s']
                m[f'HPriceNaive{tag}'] = f"{sn:.1f}"; m[f'HPriceVer{tag}'] = f"{sv:.1f}"; m[f'HPriceFrac{tag}'] = f"{100 * sv / sn:.0f}\\%"
    ks = RES / 'h_k_scaling.json'                     # descriptive k-station scaling of verified memory (not registered)
    if ks.is_file():
        s = json.loads(ks.read_text())
        m['HKDelta'] = f"{s['delta_s']:.0f}"
        g = {(r['k'], r['q']): r for r in s['grid']}
        m['HKSaveTwo'] = f"{g[(2, 0.2)]['saving_s']:.0f}"; m['HKSaveEight'] = f"{g[(8, 0.2)]['saving_s']:.0f}"
    # ---- campaign J (Jev role + Qwen on the robot)
    jf = RES / 'j_summary.json'
    if jf.is_file():
        j = json.loads(jf.read_text())
        for cfg in ('A', 'J'):
            c = j['per_config'][cfg]
            m[f'JCorrect{cfg}'] = f"{c['correct']}/{c['n']}"; m[f'JUnsafe{cfg}'] = c['unsafe_deliveries']
            m[f'JFalseRef{cfg}'] = c['false_refusals']; m[f'JFailed{cfg}'] = c['failed']
            m[f'JUnsafe{cfg}Upper'] = f"{100 * wilson(c['unsafe_deliveries'], c['n'])[1]:.0f}\\%"   # exact Wilson bound next to the no-margin 'J <= A' claim
            m[f'JLat{cfg}'] = f"{c['check_latency_median_s']:.1f}" if c['check_latency_median_s'] else r'\TBD'
        m['JPeakVram'] = f"{j['P1_runs_on_one_v100']['peak_vram_mib'] / 1024:.1f}" if j['P1_runs_on_one_v100']['peak_vram_mib'] else r'\TBD'
        m['JMcNemarP'] = f"{j['P3_correct_paired']['mcnemar_p']:.4f}"
        m['JClaim'] = 'supported' if (j['P1_runs_on_one_v100']['supported'] and j['P2_no_extra_unsafe']['supported']) else 'not supported'
    # ---- study V (closed-loop test of the repeated-mission model's predictions)
    vp = RES / 'v_predictions.json'
    if vp.is_file():
        pv = json.loads(vp.read_text())
        d = pv['paired_mean_time_diff_s']['M0-M2']
        m['VPredDiff'] = f"{d['p50']:.0f}"; m['VPredDiffPI'] = f"{d['p2.5']:.0f}--{d['p97.5']:.0f}"
        for k, a in zip(('zero', 'one', 'two'), ('M0', 'M1', 'M2')):
            u = pv['arms'][a]['unsafe']
            m[f'VPredUnsafe{k}'] = f"{u['p50']:.0f} ({u['p2.5']:.0f}--{u['p97.5']:.0f})"
    vf = RES / 'v_summary.json'
    if vf.is_file():
        v = json.loads(vf.read_text())
        m['VObsDiff'] = f"{v['V1_time_diff']['mean_M0_minus_M2_s']:.0f}"
        for k, a in zip(('zero', 'one', 'two'), ('M0', 'M1', 'M2')):
            m[f'VUnsafeM{k}'] = v['arms'][a]['unsafe']
        m['VSeqP'] = f"{v['V4_safety']['seq_mcnemar_M1_vs_M2_p']:.4f}"
        m['VClaimModel'] = 'supported' if v['claim_model_predicts'] else 'not supported'
        m['VClaimMemory'] = 'supported' if v['claim_memory_under_random_change'] else 'not supported'
        mp_ = advice_numbers.memory_power()
        m['VSeqMone'] = mp_['m1_seqs']; m['VSeqMtwo'] = v['V4_safety']['seq_unsafe']['M2']
        m['VMinP'] = f"{mp_['p_min']:.3f}"
        m['VPredMtwoMed'] = mp_['pred_m2_median']; m['VPredMtwoPI'] = f"{mp_['pred_m2_lo']}--{mp_['pred_m2_hi']}"
        for k_, kk_ in (('M0', 'zero'), ('M2', 'two')):
            m[f'VAbsTime{kk_}'] = f"{mp_['mean_time'][k_]:.1f}"
            m[f'VAbsTimePI{kk_}'] = f"{mp_['pred_time'][k_][0]:.1f}--{mp_['pred_time'][k_][1]:.1f}"
        late_ = [mp_['mean_time'][k_] - mp_['pred_time_p50'][k_] for k_ in ('M0', 'M2')]
        m['VAbsLate'] = f"{min(late_):.0f}--{max(late_):.0f}"
    pm_ = advice_numbers.pooled_memory()
    if pm_:
        m['MemPoolN'] = pm_['n']
        for k_, kk_ in (('M0', 'zero'), ('M1', 'one'), ('M2', 'two')):
            m[f'MemPool{kk_}'] = pm_['unsafe'][k_]
        m['MemPoolCI'] = '[{:.1f}, {:.1f}]\\%'.format(*(100 * x for x in wilson(pm_['unsafe']['M2'], pm_['n'])))
    ilc_ = advice_numbers.interlock_check()
    if ilc_:
        m['IlcheckN'] = ilc_['missions']
    m['Nfailed'] = advice_numbers.n_failed_word()
    m['FailedList'] = advice_numbers.failed_list_tex()
    # ---- study Z (zero-shot contrastive baselines)
    zf = RES / 'z_summary.json'
    if zf.is_file():
        z = json.loads(zf.read_text())['models']
        for key, mk in (('siglip', 'Sig'), ('clip', 'Clip')):
            for t, tk in (('t1', 'TOne'), ('t2', 'TTwo')):
                b = z[key][t]['baseline']
                m[f'Z{mk}{tk}FA'] = f"{b['FA']}/{b['n_deny']}"; m[f'Z{mk}{tk}CA'] = f"{b['CA']}/{b['n_allow']}"
        for t, tk in (('t1', 'TOne'), ('t2', 'TTwo')):
            o = z['siglip'][t]['ours']
            m[f'ZOurs{tk}FA'] = f"{o['FA']}/{o['n_deny']}"; m[f'ZOurs{tk}CA'] = f"{o['CA']}/{o['n_allow']}"
        tab = ROOT / 'docs/paper/tab_z.tex'
        if tab.is_file():
            tables['tab_z.tex'] = '\n'.join(l for l in tab.read_text().splitlines() if not l.startswith('% generated'))
    # ---- study P (real photographs, D-Fire)
    pf = RES / 'p_summary.json'
    if pf.is_file():
        pp = json.loads(pf.read_text())
        m['PRecall'] = f"{pp['recall']['k']}/{pp['recall']['n']}"; m['PFalseAlarm'] = f"{pp['false_alarm']['k']}/{pp['false_alarm']['n']}"
        m['PRecallCI'] = f"[{100 * pp['recall']['ci95'][0]:.1f}, {100 * pp['recall']['ci95'][1]:.1f}]\\%"
        m['PFalseAlarmCI'] = f"[{100 * pp['false_alarm']['ci95'][0]:.0f}, {100 * pp['false_alarm']['ci95'][1]:.0f}]\\%"
        ps = RES / 'p_scores_qwen9b_h36_tiles.jsonl'          # descriptive, not registered: ranking quality on P
        if ps.is_file():
            rows = [json.loads(l) for l in ps.read_text().splitlines() if l.strip()]
            pos = [r['hazard_prob'] for r in rows if r['category'] != 'none']; neg = [r['hazard_prob'] for r in rows if r['category'] == 'none']
            m['PAuroc'] = f"{sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg)):.2f}"
    # ---- study P2 (site calibration of tau_h on real photographs; chosen wording, test endpoints, registered claim)
    p2f = RES / 'p2_summary.json'
    if p2f.is_file():
        p2 = json.loads(p2f.read_text())
        w = p2.get('chosen_wording')
        m['PTwoClaim'] = 'supported' if p2.get('claim_supported') else 'not supported'
        if w:
            ct = p2['chosen_test']
            fz = p2['test_at_frozen_tau_0.05'][w]
            m['PTwoWording'] = f'\\texttt{{{w}}}'
            m['PTwoTau'] = f"{p2['chosen_tau']:g}"
            m['PTwoRecall'] = f"{ct['recall']['k']}/{ct['recall']['n']}"
            m['PTwoRecallCI'] = ci(ct['recall']['k'], ct['recall']['n'])
            m['PTwoFA'] = f"{ct['false_alarm']['k']}/{ct['false_alarm']['n']}"
            m['PTwoFACI'] = ci(ct['false_alarm']['k'], ct['false_alarm']['n'])
            m['PTwoFrozenRecall'] = f"{fz['recall']['k']}/{fz['recall']['n']}"
            m['PTwoFrozenFA'] = f"{fz['false_alarm']['k']}/{fz['false_alarm']['n']}"
        else:   # no threshold in the grid reaches the calibration recall floor: nothing to test
            m['PTwoWording'] = 'none (no feasible threshold)'
            for n_ in ('PTwoTau', 'PTwoRecall', 'PTwoRecallCI', 'PTwoFA', 'PTwoFACI', 'PTwoFrozenRecall', 'PTwoFrozenFA'):
                m[n_] = 'n/a'
    # ---- study L (unseen layouts, 24 randomised station layouts; scripts/l_analysis.py -> l_summary.json)
    lf = RES / 'l_summary.json'
    if lf.is_file():
        lj = json.loads(lf.read_text())
        if lj.get('complete'):
            pl = lj['primary']
            m['LN'] = lj['n_trials']
            m['LCorrect'] = f"{pl['correct']}/{lj['n_trials']}"
            m['LCorrectCI'] = ci(pl['correct'], lj['n_trials'])
            m['LUnsafe'] = pl['unsafe_deliveries']
            m['LFalseRef'] = pl['false_refusals']
            m['LClaim'] = 'supported' if pl['claim_supported'] else 'not supported'
    # ---- study K (conformal calibration of tau_h on stored scores)
    kf = RES / 'k_summary.json'
    if kf.is_file():
        kk = json.loads(kf.read_text())
        m['KNcal'] = kk['n_cal']; m['KNfire'] = kk['n_fire']; m['KNfree'] = kk['n_free']
        m['KFrozenMiss'] = f"{kk['frozen']['heldout_miss']['k']}/{kk['n_fire']}"
        m['KFrozenFA'] = f"{kk['frozen']['heldout_false_alarm']['k']}/{kk['n_free']}"
        for a, an in (('0.05', 'Five'), ('0.1', 'Ten')):
            e = kk['alphas'][a]['K_PAC']
            m[f'KTau{an}'] = f"{e['tau']:.4f}"
            m[f'KMiss{an}'] = f"{e['heldout_miss']['k']}/{kk['n_fire']}"
            m[f'KMissCI{an}'] = ci(e['heldout_miss']['k'], kk['n_fire'])
            m[f'KFA{an}'] = f"{e['heldout_false_alarm']['k']}/{kk['n_free']}"
            m[f'KFACI{an}'] = ci(e['heldout_false_alarm']['k'], kk['n_free'])
            m[f'KHolds{an}'] = 'held' if e['guarantee_holds_heldout'] else 'did not hold'
        e10 = kk['alphas']['0.1']['K_PAC']['heldout_false_alarm']
        m['KFAMissionTen'] = f"{100 * (1 - (1 - e10['k'] / e10['n']) ** 3):.0f}\\%"       # three fire-free views per approval, independence assumed (descriptive)
        m['KFAViewTen'] = f"{100 * e10['k'] / e10['n']:.1f}\\%"
        c_ = kk.get('caution')    # per-view false-alarm rate at the caution threshold 0.01 and the cost-bound figures built from its Wilson upper limit
        if c_:
            fa_ = c_['heldout_false_alarm']; up_ = fa_['ci95'][1]
            m['KCautTau'] = f"{c_['tau']:g}"
            m['KCautFA'] = f"{fa_['k']}/{fa_['n']}"
            m['KCautFAUp'] = f"{100 * up_:.1f}\\%"
            pt_ = fa_['k'] / fa_['n']
            for v_, nm_ in ((3, 'Three'), (6, 'Six')):
                m[f'KCaut{nm_}Pt'] = f"{100 * (1 - (1 - pt_) ** v_):.1f}\\%"
                m[f'KCaut{nm_}Up'] = f"{100 * (1 - (1 - up_) ** v_):.1f}\\%"
                m[f'KCaut{nm_}Boole'] = f"{100 * min(1.0, v_ * up_):.1f}\\%"
        m['KSmallCal'] = f"{100 * kk['small_fire_frac']['cal']:.0f}\\%"; m['KSmallHeld'] = f"{100 * kk['small_fire_frac']['heldout']:.0f}\\%"
    cr = json.loads((RES / 'advice_credit_horizon.json').read_text()) if (RES / 'advice_credit_horizon.json').is_file() else None
    if cr:      # I-24 descriptive 100-mission model of advice credit (k = 4); not a registered claim
        last = lambda key: cr['runs'][key]['series'][-1]
        m['CrLiarNo'] = f"{last('k4/liar/monotone')['extra_s']:.0f}"
        m['CrLiarYes'] = f"{last('k4/liar/credit')['extra_s']:.0f}"
        m['CrFarmYes'] = f"{last('k4/farmer/credit')['extra_s']:.0f}"
        m['CrHonest'] = f"{-last('k4/honest/credit')['extra_s']:.0f}"
        m['CrFloodNo'] = str(last('k4/flooder_real/monotone')['false_refusals'])
        m['CrFloodYes'] = str(last('k4/flooder_real/credit')['false_refusals'])
        m['CrFloodDelta'] = f"{cr['delta_real']:.2f}"
        m['CrNoisyKeep'] = f"{100 * last('k4/noisy/credit')['extra_s'] / last('k4/noisy/monotone')['extra_s']:.0f}\\%"
        m['CrMissions'] = str(len(cr['runs']['k4/liar/credit']['series']))
    # ---- registered-claim status per study (Table of all studies): supported / not supported / pending / descriptive (no claim registered)
    def _load(n):
        f = RES / n
        return json.loads(f.read_text()) if f.is_file() else None
    sup = lambda b: 'supported' if b else 'not supported'
    m['StatD'] = 'descriptive'; m['StatE'] = 'descriptive'; m['StatP'] = 'descriptive'
    t1j = _load('t1_summary.json')
    try:   # E1: the claim "<2% false approvals" needs a Wilson upper bound below 2%
        m['StatTone'] = sup(t1j['models']['Qwen3.5-9B']['rules']['full']['fa_ci95'][1] < 0.02)
    except (TypeError, KeyError):
        m['StatTone'] = 'pending'
    t2j = _load('t2_summary.json')
    try:   # P1: fewer false approvals than v3.5 with McNemar p < 0.05 (selected configuration vs reference)
        r_ = t2j['results']; sel_ = r_[t2j['selected']]; b_, c_, p_ = sel_['vs_v35_false_approval_mcnemar']
        m['StatTtwo'] = sup(b_ < c_ and p_ < 0.05)
    except (TypeError, KeyError, ValueError):
        m['StatTtwo'] = 'pending'
    for nm_, fn_, k1, k2 in (('F', 'f_summary.json', 'wrong_deliveries_A', 'wrong_deliveries_B'), ('G', 'g_summary.json', 'wrong_deliveries_B', 'wrong_deliveries_C')):
        pr_ = (_load(fn_) or {}).get('primary')
        m[f'Stat{nm_}'] = sup(pr_[k2] < pr_[k1] and pr_['mcnemar_p'] < 0.05) if pr_ else 'pending'
    zj = _load('z_summary.json')
    try:   # Z: "safer" = fewer false approvals (p<0.05) with correct approvals not significantly lower, on T1 or T2, for each baseline
        def _safer(mod):
            for ds in ('t1', 't2'):
                d_ = mod[ds]
                if d_['mcnemar']['deny']['p'] < 0.05 and d_['ours']['FA'] < d_['baseline']['FA'] and not (d_['mcnemar']['allow']['p'] < 0.05 and d_['mcnemar']['allow']['baseline_only_approved'] > d_['mcnemar']['allow']['ours_only_approved']):
                    return True
            return False
        def _avail(mod):   # more correct approvals with p<0.05 and false approvals not significantly higher
            for ds in ('t1', 't2'):
                d_ = mod[ds]; al_, dn_ = d_['mcnemar']['allow'], d_['mcnemar']['deny']
                if al_['p'] < 0.05 and al_['ours_only_approved'] > al_['baseline_only_approved'] and not (dn_['p'] < 0.05 and dn_['ours_only_approved'] > dn_['baseline_only_approved']):
                    return True
            return False
        # the registered claims are per baseline: SigLIP 'safer', CLIP 'more available'
        zs_, za_ = _safer(zj['models']['siglip']), _avail(zj['models']['clip'])
        m['StatZ'] = sup(zs_ and za_) if zs_ == za_ else f"safer: {sup(zs_)}; available: {sup(za_)}"
    except (TypeError, KeyError):
        m['StatZ'] = 'pending'
    kj = _load('k_summary.json')
    m['StatK'] = sup(all(kj['alphas'][a_]['K_PAC']['guarantee_holds_heldout'] for a_ in ('0.05', '0.1'))) if kj else 'pending'
    m['StatR'] = m.lookup('RPoolSupported') or 'pending'
    m['StatH'] = m.lookup('HHeadline') or 'pending'
    jc_ = m.lookup('JClaim'); m['StatJ'] = jc_ if jc_ else 'pending'
    lc_ = m.lookup('LClaim'); m['StatL'] = lc_ if lc_ else 'pending'
    vm_, vk_ = m.lookup('VClaimModel'), m.lookup('VClaimMemory')
    m['StatV'] = (vm_ if vm_ == vk_ else f'model: {vm_}; memory: {vk_}') if (vm_ and vk_) else 'pending'
    m['StatPtwo'] = m.lookup('PTwoClaim') or 'pending'
    # ---- study W (look-around miss rate on small partly hidden fires; closest prior-art mechanisms) -- absent until w_analysis ran
    wf = RES / 'w_summary.json'
    if wf.is_file():
        w = json.loads(wf.read_text())
        wa, wb = w.get('W-a'), w.get('W-b')
        if isinstance(wa, dict):
            la, fr, tw = wa['miss_look_around'], wa['miss_front_only'], wa['twins']['extra_false_stop_from_side_views']
            m['WNPerc'] = la['n']; m['WMissLA'] = f"{la['k']}/{la['n']}"; m['WMissFront'] = f"{fr['k']}/{fr['n']}"
            m['WMissLARate'] = pct(la['rate']); m['WMissLACI'] = ci(la['k'], la['n'])
            m['WExtraStop'] = f"{tw['k']}/{tw['n']}"
            m['WClaimEps'] = sup(wa['criteria']['claim_eps_tight']); m['WClaimCost'] = sup(wa['criteria']['claim_cost_acceptable'])
            m['WMissFrontRate'] = pct(fr['rate']); m['WMissLAUpper'] = pct(la['ci95'][1])
            m['WMcNemarP'] = _pfmt(wa['front_vs_look_around']['first_only'], wa['front_vs_look_around']['second_only'])
            m['WCaughtOnlyByLA'] = wa['front_vs_look_around']['first_only']
            m['WNFront'] = wa['n_front_perceivable']; m['WNSideOnly'] = wa['n_side_only']
            m['WMissLAFront'] = f"{wa['miss_look_around_front_perceivable']['k']}/{wa['miss_look_around_front_perceivable']['n']}"
            m['WMissLAFrontUpper'] = pct(wa['miss_look_around_front_perceivable']['ci95'][1])
            m['WMissLASide'] = f"{wa['miss_look_around_side_only']['k']}/{wa['miss_look_around_side_only']['n']}"
            m['WMissFrontSide'] = f"{wa['miss_front_only_side_only']['k']}/{wa['miss_front_only_side_only']['n']}"
            m['WMissedWorlds'] = ', '.join(wa['missed_worlds'])
            m['WNotVisible'] = f"{wa['six_view']['n_not_visible_from_any_view']}/{wa['n_fire_worlds']}"
            m['WNotVisibleUpper'] = pct(wa['six_view']['share_not_visible_from_any_view']['ci95'][1])
            m['WSixViewUpper'] = pct(wa['six_view']['miss_look_around']['ci95'][1])
            m['WTwinCA'] = f"{wa['twins']['correct_approval_look_around']['k']}/{wa['twins']['correct_approval_look_around']['n']}"
            m['WExtraStopUpper'] = pct(wa['twins']['extra_false_stop_from_side_views']['ci95'][1])
            m['WTauMiss'] = '/'.join(str(wa['tau_h_sensitivity'][t]['miss_look_around']['k']) for t in ('0.02', '0.05', '0.1', '0.2'))
            oa = wa['oracle_steering']['label_FLR']['look_around']['by_k']; of = wa['oracle_steering']['label_FLR']['front_only']['by_k']
            m['WEpsAnyTwo'] = pct(oa['2']['eps_any']); m['WEpsAnyTwoCI'] = '[{:.1f}, {:.1f}]\\%'.format(*(100 * x for x in oa['2']['ci95_independent']))
            m['WEpsAnyFour'] = pct(oa['4']['eps_any']); m['WEpsAnyFourCI'] = '[{:.1f}, {:.1f}]\\%'.format(*(100 * x for x in oa['4']['ci95_independent']))
            m['WEpsAnyTwoFront'] = pct(of['2']['eps_any']); m['WEpsAnyFourFront'] = pct(of['4']['eps_any'])
            m['WEpsAnyTwoUpper'] = pct(oa['2']['ci95_independent'][1]); m['WEpsAnyFourUpper'] = pct(oa['4']['ci95_independent'][1])
            sd_ = wa['miss_look_around_side_only']
            m['WMissLASideRate'] = pct(sd_['rate']); m['WMissLASideCI'] = ci(sd_['k'], sd_['n'])
            fvis_ = wa['miss_front_only']['k'] - wa['miss_front_only_side_only']['k']      # front-only misses among fires the front view shows
            m['WMissFrontVis'] = f"{fvis_}/{wa['miss_front_only']['k']}"; m['WMissFrontVisN'] = wa['n_front_perceivable']
            v35 = w.get('W-a_v35_reference')
            if isinstance(v35, dict):
                m['WVOldMissFront'] = f"{v35['miss_front_only']['k']}/{v35['miss_front_only']['n']}"
                m['WVOldMissLA'] = f"{v35['miss_look_around']['k']}/{v35['miss_look_around']['n']}"
                m['WVOldMissLAUpper'] = pct(v35['miss_look_around']['ci95'][1])
                m['WMoveRemoved'] = v35['miss_front_only']['k'] - v35['miss_look_around']['k']
                m['WWordRemoved'] = v35['miss_look_around']['k'] - wa['miss_look_around']['k']
        ad = w.get('W-a_adaptive')
        if isinstance(ad, dict):
            m['WAdaptMiss'] = f"{ad['perceivable_FLR']['miss_adaptive']['k']}/{ad['perceivable_FLR']['miss_adaptive']['n']}"
            m['WAdaptMissUpper'] = pct(ad['perceivable_FLR']['miss_adaptive']['ci95'][1])
            m['WAdaptPaired'] = f"{ad['perceivable_FLR']['paired']['first_only']} vs {ad['perceivable_FLR']['paired']['second_only']}"
            m['WAdaptPairedP'] = _pfmt(ad['perceivable_FLR']['paired']['first_only'], ad['perceivable_FLR']['paired']['second_only'])
            m['WAdaptTwinCA'] = f"{ad['twins']['correct_approval_adaptive']['k']}/{ad['twins']['correct_approval_adaptive']['n']}"
            m['WAdaptTrigTwin'] = f"{ad['twins']['extra_view_trigger_rate']['k']}/{ad['twins']['extra_view_trigger_rate']['n']}"
            m['WAdaptTrigTwinCI'] = ci(ad['twins']['extra_view_trigger_rate']['k'], ad['twins']['extra_view_trigger_rate']['n'])
            m['WAdaptTrigFire'] = f"{ad['fire_trigger_rate']['k']}/{ad['fire_trigger_rate']['n']}"
            # the rule written in docs/IMPROVEMENT_LOG.md (I-20) before the scores: (1) fewer misses, paired, at least one world; (2) twin correct approvals drop by at most 3 of 75
            pr = ad['perceivable_FLR']['paired']; tw_ = ad['twins']
            r1 = pr['second_only'] == 0 and pr['first_only'] >= 1
            r2 = tw_['correct_approval_look_around']['k'] - tw_['correct_approval_adaptive']['k'] <= 3
            m['WAdaptRuleA'] = sup(r1); m['WAdaptRuleB'] = sup(r2); m['WAdaptAdopt'] = 'adopted as the v3.7 default' if (r1 and r2) else 'not adopted'
        sp = w.get('W-a_scrutiny_policies')
        if isinstance(sp, dict):
            pol = sp['policies']
            m['WScrutMissB'] = f"{pol['b_caution']['miss_perceivable_FLR']['k']}/{pol['b_caution']['miss_perceivable_FLR']['n']}"
            m['WScrutMissC'] = f"{pol['c_caution_extra_always']['miss_perceivable_FLR']['k']}/{pol['c_caution_extra_always']['miss_perceivable_FLR']['n']}"
            m['WScrutMissCUpper'] = pct(pol['c_caution_extra_always']['miss_perceivable_FLR']['ci95'][1])
            m['WScrutPC'] = _pfmt(pol['c_caution_extra_always']['miss_perceivable_FLR_vs_a']['first_only'], pol['c_caution_extra_always']['miss_perceivable_FLR_vs_a']['second_only'])
            m['WScrutTwinStopC'] = f"{pol['c_caution_extra_always']['twins_extra_false_stop_vs_a']['k']}/{pol['c_caution_extra_always']['twins_extra_false_stop_vs_a']['n']}"
        if isinstance(wb, dict):
            S, nd = wb['systems'], wb['n_deny']
            fa = lambda name: f"{S[name]['false_approvals']}/{nd}"
            m['WFAOursFull'] = fa(wb['primary_reference'])
            for key, name in zip(('Vote', 'KnowFive', 'KnowTen'), wb['primary_baselines']):
                m[f'WFA{key}'] = fa(name)
            m['WNDist'] = sum(bool(S[n_].get('mechanism_matters')) for n_ in wb['primary_baselines'])
            m['WNImages'] = wb['n_images']; m['WNDeny'] = wb['n_deny']; m['WNAllow'] = wb['n_allow']
            m['WFAOursDeployed'] = fa(wb['secondary_reference'])
            m['WFAOursFullRate'] = pct(S[wb['primary_reference']]['fa_rate'], 2)
            m['WFAOursDeployedCI'] = '[{:.2f}, {:.2f}]\\%'.format(*(100 * x for x in S[wb['secondary_reference']]['fa_ci95']))
            m['WCAOursFull'] = f"{S[wb['primary_reference']]['correct_approvals']}/{wb['n_allow']}"
            vote, kf, kt = (S[n_] for n_ in wb['primary_baselines'])
            m['WFAVoteRate'] = pct(vote['fa_rate'], 2); m['WFAVoteCI'] = ci(vote['false_approvals'], wb['n_deny'], 2)
            m['WVotePRaw'] = f"{vote['vs_ours_full']['false_approval']['mcnemar_p']:.3f}"
            m['WVoteHolm'] = f"{vote['primary_holm_p_false_approval']:.3f}"
            m['WVoteDisc'] = f"{vote['vs_ours_full']['false_approval']['baseline_only']} vs {vote['vs_ours_full']['false_approval']['ours_only']}"
            m['WVoteDeployedHolm'] = f"{vote['secondary_holm_p_false_approval']:.3f}"
            m['WVoteDeployedDisc'] = f"{vote['vs_ours_deployed']['false_approval']['baseline_only']} vs {vote['vs_ours_deployed']['false_approval']['ours_only']}"
            m['WVoteDeployedBetter'] = sup(bool(vote['deployed_better']))
            m['WCAKnowFive'] = f"{kf['correct_approvals']}/{wb['n_allow']}"
            m['WCAKnowFiveRate'] = pct(kf['ca_rate'])
            m['WCAKnowFiveDrop'] = kf['vs_ours_full']['correct_approval']['ours_only']
            m['WCAKnowFiveP'] = _pfmt(kf['vs_ours_full']['correct_approval']['ours_only'], kf['vs_ours_full']['correct_approval']['baseline_only'])
            m['WKnowTenSame'] = 'identical' if (kt['false_approvals'] == S[wb['primary_reference']]['false_approvals'] and kt['vs_ours_full']['false_approval']['ours_only'] == 0 == kt['vs_ours_full']['false_approval']['baseline_only'] and kt['vs_ours_full']['correct_approval']['ours_only'] == 0 == kt['vs_ours_full']['correct_approval']['baseline_only']) else 'different'
            m['WSmallOurs'] = f"{S[wb['secondary_reference']]['small_fires']['approved']}/{S[wb['secondary_reference']]['small_fires']['small_fires_correct_supply']}"
            m['WSmallVote'] = f"{vote['small_fires']['approved']}/{vote['small_fires']['small_fires_correct_supply']}"
            mond = S.get('KnowNo-Mondrian q1_h35 alpha=0.05')
            if mond:
                m['WMondCA'] = f"{mond['correct_approvals']}/{wb['n_allow']}"
    wce, wcc, wnd = m.lookup('WClaimEps'), m.lookup('WClaimCost'), m.lookup('WNDist')
    m['StatW'] = f"bound: {wce}; cost: {wcc}; prior art distinguished: {wnd}/3" if (wce and wcc and wnd is not None) else 'pending'
    # ---- study A (adversarial advice, closed loop; scripts/a_analysis.py -> a_summary.json) -- absent until it ran
    af = RES / 'a_summary.json'
    if af.is_file():
        a = json.loads(af.read_text())
        a1, a2, a3 = a['A1_unsafe_naive_vs_monotone'], a['A2_time_saved_truthful'], a['A3_dos_cost_vs_bound']
        m['APairs'] = a1['n_world_pairs']
        m['AUnsafeNaive'] = f"{a1['runs']['naive']['unsafe']}/{a1['runs']['naive']['n']}"
        m['AUnsafeOurs'] = f"{a1['runs']['monotone']['unsafe']}/{a1['runs']['monotone']['n']}"
        m['AUnsafeCtrl'] = f"{a1['control_runs_F_N']['unsafe']}/{a1['control_runs_F_N']['n']}"
        m['AMcNemarP'] = _pfmt(a1['discordant_naive_only'], a1['discordant_monotone_only'])
        m['AViol'] = len(a1['monotone_unsafe_where_control_safe'])
        a1b = a.get('A1b_unsafe_filtered_vs_monotone')          # guardrail baseline (absent in summaries of the two-arm design)
        if a1b:
            m['AUnsafeFiltered'] = f"{a1b['runs']['filtered']['unsafe']}/{a1b['runs']['filtered']['n']}"
            m['AMcNemarPFiltered'] = _pfmt(a1b['discordant_filtered_only'], a1b['discordant_monotone_only'])
            m['AClaimGuardrail'] = sup(a1b['supported'])
        m['AAuditFail'] = a1['n_audit_failures']
        m['ATimeSave'] = f"{a2['monotone']['median_saved_s']:.0f}" if a2['monotone']['median_saved_s'] is not None else r'\TBD'
        m['AWilcoxonP'] = a2['monotone']['wilcoxon_exact_p']
        m['ADoSVisits'] = a3['max_extra_visits'] if a3['max_extra_visits'] is not None else 0
        m['ADoSFalseRef'] = a3['false_refusals_monotone']
        m['ADoSN'] = a3['n_monotone_runs']
        m['ADoSAllowed'] = f"{a3['allowed_max_false_refusals_95']} at the 95th percentile"
        m['AClaimSafety'] = sup(a1['supported'])
        m['AClaimTime'] = sup(a2['supported']) if a2['monotone']['testable'] else 'not testable'
        m['AClaimCost'] = sup(a3['supported'])
        m['AClaim'] = sup(a['headline_supported'])
        m['AExtract'] = f"{a['extraction']['exact_match']}/{a['extraction']['n_operator_runs']}"
        bc_ = a['extraction']['by_condition']      # the attacks that relax a check (poison_safe, poison_location), not the easy ones
        m['AExtractRelax'] = f"{bc_['poison_safe']['exact'] + bc_['poison_location']['exact']}/{bc_['poison_safe']['n'] + bc_['poison_location']['n']}"
        af_ = advice_numbers.a_facts()        # the rest of the A numbers (worlds, guardrail flag rates, replay, A-steer) share one reader with README/report/YouTube
        if af_:
            kk = lambda t: f"{t[0]}/{t[1]}"
            if af_['worlds']['naive'] and af_['worlds']['filtered'] and af_['worlds']['monotone']:
                m['AWorldsNaive'], m['AWorldsFiltered'], m['AWorldsOurs'] = (kk(af_['worlds'][k_]) for k_ in ('naive', 'filtered', 'monotone'))
            m['ANPerChannel'] = af_['by_channel']['naive']['file'][1]        # runs per channel and arm in the A figure
            m['AFilterFlagOp'], m['AFilterFlagFile'] = kk(af_['filter_flag_operator']), kk(af_['filter_flag_file'])
            m['AFileUnsafeNaive'], m['AFileUnsafeFiltered'], m['AFileUnsafeOurs'] = (kk(af_['by_channel'][k_]['file']) for k_ in ('naive', 'filtered', 'ours'))
            m['AOpUnsafeNaive'], m['AOpUnsafeFiltered'], m['AOpUnsafeOurs'] = (kk(af_['by_channel'][k_]['operator']) for k_ in ('naive', 'filtered', 'ours'))
            m['ANaiveWrongSupply'], m['ANaiveIntoFire'] = af_['naive_wrong_supply'], af_['naive_into_fire']
            m['AHazardFalseRefNaive'], m['AHazardFalseRefFiltered'], m['AHazardFalseRefN'] = af_['dos_false_refusals_naive'], af_['dos_false_refusals_filtered'], af_['dos_n_baseline']
            if af_['replay']:
                m['AReplay'], m['AReplayViol'] = f"{af_['replay'][0]}/{af_['replay'][1]}", af_['replay'][2]
            m['ATimePos'] = f"{af_['time_pos']}/{af_['time_n']}"
            m['ATimeMed'] = f"{af_['time_median']:.1f}"
            pr_ = af_['price']
            m['AWBound'], m['AWOne'], m['AMaxExtra'], m['ALost'], m['ALostAllowed'] = f"{pr_['bound']:.1f}", f"{pr_['W']:.1f}", f"{pr_['max_extra']:.1f}", pr_['lost'], pr_['allowed']
            st_ = af_['steer']
            m['ARuns'], m['ARunsFailed'] = af_['runs'], af_['failed']
            m['ASteerN'] = st_['n']
            m['ASteerP'] = f"{st_['p_sign']:.2f}" if st_.get('p_sign') is not None else r'\TBD'
            m['AUnsafeOursUpper'] = f"{af_['unsafe_wilson_ours'][1]:.2f}"
            for key_, nm_ in (('ours', 'Ours'), ('control', 'Ctrl'), ('scrutiny', 'Scr'), ('naive', 'Naive')):
                m[f'ASteer{nm_}'] = f"{st_[key_]['unsafe']}/{st_[key_]['n']}"
                m[f'ASteerLost{nm_}'] = f"{st_[key_]['lost']}/{st_[key_]['n']}"
            m['ASteerOursUpper'], m['ASteerCtrlUpper'] = f"{st_['ours']['wilson'][1]:.2f}", f"{st_['control']['wilson'][1]:.2f}"
            m['ASteerTimeOurs'], m['ASteerTimeCtrl'] = f"{st_['ours']['median_s']:.0f}", f"{st_['control']['median_s']:.0f}"
            m['ASteerDelivScr'] = f"{st_['scrutiny']['delivered']}/{st_['n']}"
            m['ASteerWorlds'] = ', '.join(st_['unsafe_worlds'])
            m['AIntentAcc'] = f"{af_['intent_accepted']}/{af_['extract'][1]}" if af_['intent_accepted'] is not None else r'\TBD'
            m['AExtractSafe'] = kk(af_['extract_safe'])
            m['AOffline'] = r'has been scored (test half, once)' if af_['offline_done'] else 'has not been scored'
            aof_ = RES / 'advice_injection_eval_test.json'
            if aof_.is_file():
                oj_ = json.loads(aof_.read_text())
                m['AOffTexts'], m['AOffPlans'] = oj_['n'], oj_['relaxation_reachable_monotone']['n_plans']
                m['AOffWrong'] = f"{oj_['wrong_shelter_acceptance']['accepted']}/{oj_['wrong_shelter_acceptance']['n_requests']}"
                m['AOffIntent'] = f"{oj_['intent_accuracy']['ok']}/{oj_['intent_accuracy']['n']}"
                m['AOffMono'] = f"{oj_['relaxation_reachable_monotone']['relaxing_plans']}/{oj_['relaxation_reachable_monotone']['n_plans']}"
                m['AOffNaive'] = f"{oj_['naive_relaxation_reachable']['relaxing_plans']}/{oj_['naive_relaxation_reachable']['n_plans']}"
                m['AOffFilt'] = f"{oj_['filtered_relaxation_reachable']['relaxing_plans']}/{oj_['filtered_relaxation_reachable']['n_plans']}"
                m['AOffExact'] = f"{oj_['advice_extraction']['exact']}/{oj_['advice_extraction']['scored']}"
                ex_ = oj_['exhaustive_monotone_check']
                m['AOffSets'], m['AOffExhNaive'], m['AOffExhPlans'] = ex_['n_item_sets'], ex_['naive_relaxes'], ex_['n_plans']
                m['AOffExhMono'] = f"{ex_['monotone_relaxes']}/{ex_['n_plans']}"
                m['AOffFlag'] = f"{oj_['filter_flag_rates']['flagged']}/{oj_['filter_flag_rates']['n']}"

    ac_ = [m.lookup(k_) for k_ in ('AClaimSafety', 'AClaimTime', 'AClaimCost')]
    m['StatA'] = f"safety: {ac_[0]}; time: {ac_[1]}; cost: {ac_[2]}" if all(ac_) else 'pending'
    # abstract clause for the advice result: empty until study A has run (the abstract never shows a pending marker)
    m['AbsAdvice'] = (f"; unsafe worlds under hostile advice: naive baseline {m.lookup('AWorldsNaive')}, self-filter {m.lookup('AWorldsFiltered')}, ours {m.lookup('AWorldsOurs')}, no advice {m.lookup('AUnsafeCtrl')} runs"
                      if m.lookup('AWorldsNaive') and m.lookup('AWorldsFiltered') and m.lookup('AWorldsOurs') else '')
    # ---- study S (scene-text injection, image level; scripts/s_analysis.py -> s_summary.json) -- absent until it ran
    sf = RES / 's_summary.json'
    if sf.is_file():
        sj = json.loads(sf.read_text())
        so, s1_, sff = sj['systems'].get('OURS'), sj['systems'].get('ONE-PASS'), sj['systems'].get('FREE-FORM')
        m['SNPairs'] = sj['n_valid_pairs']
        if so:
            tx, st = so['by_text'], so['by_sign_type']
            fl = lambda g: g['attack_vs_none']['flips']
            m['SFlipsC'], m['SNC'] = fl(tx['letter_C']), tx['letter_C']['n_pairs']
            m['SFlipsA'], m['SNA'] = fl(tx['letter_A']), tx['letter_A']['n_pairs']
            m['SFlipsB'], m['SNB'] = fl(tx['letter_B']), tx['letter_B']['n_pairs']
            m['SFlipsMis'], m['SNMis'] = fl(st['mislabel']), st['mislabel']['n_pairs']
            m['SFlipsSafe'], m['SNSafe'] = fl(st['false_safe']), st['false_safe']['n_pairs']
        if s1_:
            m['SFlipsOneA'] = f"{s1_['by_text']['letter_A']['attack_vs_none']['flips']} of {s1_['by_text']['letter_A']['n_pairs']}"
        if sff:
            m['SFlipsMisFree'] = f"{sff['by_sign_type']['mislabel']['attack_vs_none']['flips']} of {sff['by_sign_type']['mislabel']['n_pairs']}"
        lg_ = (sj.get('legibility') or {}).get('S0_signs_legible')
        m['SLegible'] = {True: 'yes', False: 'no'}[lg_] if lg_ is not None else r'\TBD'
        cr_ = sj.get('criteria') or {}
        hyp_ = [cr_.get(k_) for k_ in ('S1_naive_letter_C_not_effective_on_OURS', 'S2_permutation_helps_against_letter_A', 'S3_adaptive_letter_B_effective_on_OURS',
                                       'S4_mislabel_residual_on_OURS', 'S5_false_safe_not_effective_on_OURS', 'S6_letter_C_availability_attack_on_OURS', 'S7_benign_text_inert')]
        if all(h_ is not None for h_ in hyp_) and lg_ is not None:
            m['SClaim'] = sup(hyp_[0] and hyp_[1] and lg_)      # registered claim: the permuted check is not fooled by a letter written for one option order (H1, H2, S0)
            m['SHyp'] = f"{sum(hyp_)}/7"
        fa_ = ((sj.get('defence') or {}).get('OCR-MASK') or {}).get('false_approvals_with_attack_sign', {}).get('OURS')     # all attack-sign worlds that OURS refuses without the sign
        if fa_:
            m['SPoolFlips'], m['SPoolN'], m['SPoolUpper'] = fa_['k'], fa_['n'], f"{100 * fa_['ci95'][1]:.1f}\\%"
        d7_ = cr_.get('S7_detail') or {}
        if 'FREE-FORM' in d7_ and 'OURS' in d7_:
            m['SBenignFree'], m['SBenignOurs'] = d7_['FREE-FORM'], d7_['OURS']
        lc_ = ((sj.get('defence') or {}).get('OCR-MASK') or {}).get('legit_cost')
        if lc_:
            m['SLegitKept'] = f"{lc_['ours_approved']}/{lc_['n_images']}"
    if sf.is_file():        # supplementary table of study S: every system, approvals of must-refuse worlds without a sign / with the attack sign / with a benign text
        rows_ = [r'\begin{tabular}{lcccc}', r'\toprule', r'System & no sign & attack sign & benign text & flips \\', r'\midrule']
        for nm_, sy_ in sj['systems'].items():
            mr_ = sy_['must_refuse_all']
            c_ = lambda g_: f"{g_['k']}/{g_['n']}"
            rows_.append(f"{nm_.replace('+', '+').replace('_', ' ')} & {c_(mr_['bad_no_sign'])} & {c_(mr_['bad_attack'])} & {c_(mr_['bad_benign'])} & {mr_['attack_vs_none']['flips']} \\\\")
        rows_ += [r'\bottomrule', r'\end{tabular}']
        tables['tab_s_systems.tex'] = '\n'.join(rows_)
    m['StatS'] = f"letters: {m.lookup('SClaim')}; {m.lookup('SHyp')} hypotheses" if m.lookup('SClaim') else 'pending'
    # ---- study IF (request text switching the requested supply; advice_numbers.if_facts reads if_summary.json)
    iff_ = advice_numbers.if_facts()
    if iff_:
        m['IFK'], m['IFN'] = iff_['k'], iff_['n']
        m['IFCI'] = f"{100 * iff_['ci'][0]:.0f}--{100 * iff_['ci'][1]:.0f}\\%"
        for k_, nm_ in (('flip_system', 'System'), ('flip_forwarded', 'Forwarded'), ('flip_hidden', 'Hidden')):
            m[f'IF{nm_}'] = f"{iff_['cat'][k_][0]}/{iff_['cat'][k_][1]}"
        m['IFBoth'] = iff_['both']
        m['IFCorr'] = f"{iff_['corr'][0]}/{iff_['corr'][1]}"
        m['IFCtrl'] = f"{iff_['ctrl'][0]}/{iff_['ctrl'][1]}"
        m['IFWrong'] = iff_['ctrl_wrong'] + iff_['corr_wrong'][0]
        m['IFClaim'] = 'supported' if iff_['held'] else 'not supported'
        m['StatIF'] = f"IF1 {m.lookup('IFClaim')}: {iff_['k']}/{iff_['n']} switched"
    # ---- IF re-run with the intent prompt i38 (exploratory; if_i38_summary.json)
    iif_ = RES / 'if_i38_summary.json'
    if iif_.is_file():
        ii_ = json.loads(iif_.read_text())
        m['IFPromptK'], m['IFPromptN'] = ii_['IF1_flip_acceptance']['k'], ii_['IF1_flip_acceptance']['n']
        m['IFPromptCI'] = ci(ii_['IF1_flip_acceptance']['k'], ii_['IF1_flip_acceptance']['n'])
        m['IFPromptCorr'] = f"{ii_['IF2_correction_followed']['k']}/{ii_['IF2_correction_followed']['n']}"
    # ---- study IF2 (ask-back rule I-27; if2_summary.json)
    i2f_ = RES / 'if2_summary.json'
    if i2f_.is_file():
        ij_ = json.loads(i2f_.read_text())
        ab_, pl_ = ij_['arms']['ask_back'], ij_['arms']['plain']
        m['IFtwoK'], m['IFtwoN'] = ab_['flip_acceptance']['k'], ab_['flip_acceptance']['n']
        m['IFtwoUpper'] = pct(ab_['flip_acceptance']['ci95'][1])
        m['IFtwoCtrl'] = f"{ab_['control_accepted']['k']}/{ab_['control_accepted']['n']}"
        m['IFtwoPlainK'], m['IFtwoPlainUpper'] = pl_['flip_acceptance']['k'], pct(pl_['flip_acceptance']['ci95'][1])
        pc_ = ab_['per_category']
        m['IFtwoPrice'] = f"{pc_['negation']['not_accepted'] + pc_['correction']['not_accepted']}/{pc_['negation']['n'] + pc_['correction']['n']}"
        m['IFtwoWrong'] = ab_['wrong_item_any'] + pl_['wrong_item_any']
        m['IFtwoClaim'] = sup(ij_['claim_supported'])
        m['StatIFtwo'] = f"IF2 {m.lookup('IFtwoClaim')}: {ab_['flip_acceptance']['k']}/{ab_['flip_acceptance']['n']} switched with ask-back"
    # ---- study B (advice credit in closed loop, mechanics; b_summary.json) -- absent until it ran
    bf_ = RES / 'b_summary.json'
    if bf_.is_file():
        bj = json.loads(bf_.read_text())
        liar_ = bj['B1_liar']['sequences']
        m['BRuns'], m['BMissions'] = bj['n_runs'], bj['m']
        m['BSeqs'], m['BSeqsAll'] = bj['B1_liar']['n_complete'], len(liar_)
        w_no_, w_cr_ = {v['wasted_nocredit'] for v in liar_.values()}, {v['wasted_credit'] for v in liar_.values()}
        m['BWastedNo'], m['BWastedCredit'] = (str(min(w_no_)) if len(w_no_) == 1 else f'{min(w_no_)}--{max(w_no_)}'), (str(min(w_cr_)) if len(w_cr_) == 1 else f'{min(w_cr_)}--{max(w_cr_)}')
        m['BBound'] = max(v['prop3_bound'] for v in liar_.values())
        m['BHonestWasted'] = sum(v['wasted'] for v in bj['B2_honest']['sequences'].values())
        m['BAuditFail'] = len(bj['B3_audits']['audit_failures'])
        m['BUnsafe'] = len(bj['B3_audits']['unsafe_deliveries'])
        m['BSave'], m['BSavePred'] = f"{bj['B4_time_descriptive']['median_saving_s']:.0f}", f"{bj['B4_time_descriptive']['predicted_saving_per_sequence_s']:.0f}"
        m['BClaim'] = sup(bj['headline_supported'])
        m['StatB'] = f"credit bound: {m.lookup('BClaim')}"
    # ---- study Q (real photographs, 405 Commons images; q_summary.json + the score file for the descriptive split of the refusals)
    qf_ = RES / 'q_summary.json'
    if qf_.is_file():
        qj_ = json.loads(qf_.read_text())
        qq_, qc_ = qj_['qwen9b_v35'], qj_['qwen9b_v35']['claim']
        m['QN'] = qj_['n']
        m['QFA'], m['QNDeny'] = f"{qq_['FA']}/{qq_['n_deny']}", qq_['n_deny']
        m['QFAUpper'] = pct(qq_['FA_ci'][1])
        m['QCA'], m['QCARate'] = f"{qq_['CA']}/{qq_['n_allow']}", pct(qq_['CA_rate'])
        m['QCACI'] = '[{:.1f}, {:.1f}]\\%'.format(*(100 * x for x in qq_['CA_ci']))
        ca_ = qj_['breakdown']['correct_approvals']
        m['QCAWater'], m['QCAMed'] = f"{ca_['water']['k']}/{ca_['water']['n']}", f"{ca_['medicine']['k']}/{ca_['medicine']['n']}"
        m['QSigFA'], m['QClipFA'] = f"{qj_['siglip']['counts']['FA']}/{qj_['siglip']['counts']['n_deny']}", f"{qj_['clip']['counts']['FA']}/{qj_['clip']['counts']['n_deny']}"
        m['QCAHigh'], m['QCAHigher'] = (f"{qj_['tau_s_sensitivity'][t_]['CA']}/{qj_['tau_s_sensitivity'][t_]['n_allow']}" for t_ in ('0.7', '0.9'))
        m['QSafe'], m['QAvail'] = sup(qc_['safety_FA_upper_bound_le_0.05']), sup(qc_['availability_CA_ge_0.70'])
        m['QClaim'] = sup(qc_['supply_check_transfers'])
        qs_ = RES / 'q_scores_qwen9b_v35.jsonl'
        if qs_.is_file():      # descriptive: why the correct images were refused (both passes said "other" / the two option orders disagreed)
            al_ = [r_ for r_ in (json.loads(x_) for x_ in qs_.read_text().splitlines()) if r_['expected'] == 'allow']
            ref_ = [r_ for r_ in al_ if not all(r_['passes'][k_]['supply'] == r_['requested'] for k_ in '12')]
            m['QRefused'] = qq_['n_allow'] - qq_['CA']      # one more correct image has the right answer in both orders but p below tau_s
            m['QRefOther'] = sum(all(r_['passes'][k_]['supply'] == 'other' for k_ in '12') for r_ in ref_)
            m['QRefDisagree'] = sum(r_['passes']['1']['supply'] != r_['passes']['2']['supply'] for r_ in ref_)
        m['StatQ'] = f"safety: {m.lookup('QSafe')}; availability: {m.lookup('QAvail')}; transfers: {m.lookup('QClaim')}"
    # ---- study XD (image level, depot; xd_summary.json).  The I-20 revert verdict is recomputed from the raw records with the code that was
    # committed before XD was scored (xd_analysis.i20_revert_verdict); the fields shared with the summary must agree.
    xdf_ = RES / 'xd_summary.json'
    if xdf_.is_file():
        xj_ = json.loads(xdf_.read_text())
        xm_, xr_ = xj_['XD_main'], xj_['XD_recalibration']
        sys.path.insert(0, str(ROOT))
        from scripts import xd_analysis as _xa
        xrec_ = json.loads((RES / 'devset_xd_h36_tiles.json').read_text())['records']
        xv_ = _xa.summarise_main(xrec_)['i20_revert_verdict']
        rt_ = lambda d_: f"{d_['k']}/{d_['n']}"
        pl_, bc_ = xm_['xd1_pooled'], xm_['xd1_by_class']
        m['XDNWorlds'], m['XDNHaz'], m['XDNPerc'] = xm_['n_worlds'], xm_['n_hazard'], xm_['n_perceivable']
        m['XDMissFront'], m['XDMissFrontRate'] = rt_(pl_['front_only']), pct(pl_['front_only']['rate'], 0)
        m['XDMissLA'], m['XDMissLARate'] = rt_(pl_['look_around']), pct(pl_['look_around']['rate'])
        m['XDMissLAUpper'] = pct(pl_['look_around']['ci95'][1]); m['XDMissLACI'] = '[{:.1f}, {:.1f}]\\%'.format(*(100 * x for x in pl_['look_around']['ci95']))
        hd_ = bc_['tongues_small']
        m['XDHardFront'], m['XDHardLA'], m['XDHardLARate'] = rt_(hd_['front_only']), rt_(hd_['look_around']), pct(hd_['look_around']['rate'], 0)
        m['XDHardLAUpper'] = pct(hd_['look_around']['ci95'][1]); m['XDHardLACI'] = '[{:.1f}, {:.1f}]\\%'.format(*(100 * x for x in hd_['look_around']['ci95']))
        m['XDHardAdapt'], m['XDHardAdaptUpper'] = rt_(hd_['adaptive']), pct(hd_['adaptive']['ci95'][1])
        m['XDMissAdapt'], m['XDMissAdaptUpper'] = rt_(pl_['adaptive']), pct(pl_['adaptive']['ci95'][1])
        m['XDBigLA'], m['XDSmokeLA'] = rt_(bc_['tongues_big']['look_around']), rt_(bc_['smoke_only']['look_around'])
        m['XDRemoved'] = round(100 * xm_['criteria']['O1_front_misses_removed_share']); m['XDNSideOnly'] = xm_['n_side_only']
        pr_ = xm_['caught_by_extra_views']['paired_la_vs_adaptive']
        m['XDAdaptRemoved'], m['XDAdaptAdded'], m['XDAdaptP'] = pr_['first_only'], pr_['second_only'], _pfmt(pr_['first_only'], pr_['second_only'])
        tr_ = xm_['xd3_extra_view_trigger_rate_on_twins']
        m['XDTrig'], m['XDTrigRate'], m['XDTrigCI'] = rt_(tr_), pct(tr_['rate']), '[{:.1f}, {:.1f}]\\%'.format(*(100 * x for x in tr_['ci95']))
        m['XDTwinCAAdapt'] = rt_(xm_['xd3_adaptive_correct_approvals_twins'])
        ca_ = xm_['xd3_correct_approvals']['pooled']
        m['XDCAFront'], m['XDCALA'] = rt_(ca_['front_only']), rt_(ca_['look_around'])
        wr_ = xm_['xd3_wrong_supply_false_approvals']['pooled']['look_around']
        m['XDWrongFA'], m['XDWrongUpper'] = rt_(wr_), pct(wr_['ci95'][1])
        ar_ = xm_['arena_reference']['eps_look_around_depot_vs_arena_W']
        m['XDArenaMiss'], m['XDArenaP'] = rt_(ar_['arena']), f"{ar_['fisher_two_sided_p']:.3f}"
        hs_ = xm_['oracle_steering']['hard_class_tongues_small']['label_FLR']['look_around']['by_k']
        m['XDHardEpsAnyTwo'], m['XDHardEpsAnyFour'] = pct(hs_['2']['eps_any']), pct(hs_['4']['eps_any'])
        m['XDHardEpsAnyTwoCI'] = '[{:.1f}, {:.1f}]\\%'.format(*(100 * x for x in hs_['2']['ci95_independent']))
        m['XDHardEpsAnyFourCI'] = '[{:.1f}, {:.1f}]\\%'.format(*(100 * x for x in hs_['4']['ci95_independent']))
        sn_ = xm_['tau_h_sensitivity']
        m['XDTauMissTwo'], m['XDTauCATwo'] = rt_(sn_['0.02']['miss_look_around']), rt_(sn_['0.02']['correct_approval_look_around'])
        ti_ = xr_['test_image_level']['at_frozen']
        m['XDTestRecall'], m['XDTestRecallRate'] = rt_(ti_['recall']), pct(ti_['recall']['rate'])
        m['XDTestFA'], m['XDTestFARate'] = rt_(ti_['false_alarm']), pct(ti_['false_alarm']['rate'])
        m['XDTestWorldMiss'] = rt_(xr_['test_world_level']['at_frozen']['miss_look_around'])
        m['XDTauStar'] = 'none' if xr_['calibration']['tau_star'] is None else str(xr_['calibration']['tau_star'])
        cr_ = xm_['criteria']
        m['XDClaimEps'] = sup(cr_['claim_eps_tight_hard_class']); m['XDClaimRel'] = sup(cr_['claim_relative_ordering_transfers'])
        m['XDClaimCal'] = sup(xr_['claim_calibration_usable']); m['XDClaimCost'] = sup(cr_['C1_correct_approvals_at_least_0.80'])
        m['XDOne'], m['XDTwo'], m['XDFour'] = sup(cr_['O1_look_around_removes_at_least_half_of_front_misses']), sup(cr_['O2_small_hidden_harder_than_big_visible']), sup(cr_['O4_no_wrong_supply_false_approval'])
        m['XDThree'] = sup(cr_['O3_adaptive_no_worse_and_trigger_rate_at_most_0.15'])
        m['XDRevert'] = xv_['status']
        m['XDRevertFired'] = ', '.join(k_[0] for k_, v_ in xv_['fired'].items() if v_) or 'none'
        rows_ = [r'\begin{tabular}{@{}lrccc@{}}', r'\toprule', r'Class & Worlds & Front only & Look-around & + extra views \\', r'\midrule']
        for cl_, nm_ in (('tongues_small', 'small flames, partly hidden'), ('tongues_big', 'big flames, visible'), ('smoke_only', 'smoke only'),
                         ('mesh_flame', 'mesh flames'), ('sprite', 'sprite flames')):
            c_ = bc_[cl_]
            rows_.append(f"{nm_} & {c_['look_around']['n']} & {rt_(c_['front_only'])} & {rt_(c_['look_around'])} & {rt_(c_['adaptive'])} \\\\")
        rows_ += [r'\midrule', f"all perceivable & {pl_['look_around']['n']} & {rt_(pl_['front_only'])} & {rt_(pl_['look_around'])} & {rt_(pl_['adaptive'])} \\\\",
                  r'\bottomrule', r'\end{tabular}']
        tables['tab_xd_classes.tex'] = '\n'.join(rows_)
        xs_ = RES / 'xd_site_tau_sus.json'
        if xs_.is_file():
            sj_ = json.loads(xs_.read_text())
            tt_ = sj_['test']
            m['XDSiteTau'] = f"{sj_['tau_sus_site']:.4f}"
            m['XDSiteTrig'] = f"{tt_['triggered']}/{tt_['twins_with_extra']}"
            m['XDSiteRemoved'], m['XDSiteLA'] = f"{tt_['look_around_misses'] - tt_['adaptive_misses']}", f"{tt_['look_around_misses']}"
            m['XDSiteRefMiss'] = f"{sj_['reference_tau_sus_0.005']['adaptive_misses']}/{tt_['perceivable']}"
            m['XDSiteRefTrig'] = f"{sj_['reference_tau_sus_0.005']['triggered']}/{sj_['reference_tau_sus_0.005']['of']}"
        xh_ = RES / 'xd_site_tau_h.json'
        if xh_.is_file():
            hj_ = json.loads(xh_.read_text())
            m['XDSiteTauH'] = f"{hj_['tau_h_site']:g}"
            m['XDSiteHardMiss'] = f"{hj_['test_site']['hard_misses']}/{hj_['test_site']['hard_n']}"
        xrf_ = RES / 'xd_real_summary.json'
        if xrf_.is_file():
            rj_ = json.loads(xrf_.read_text())['false_alarm']
            m['XDRFA'], m['XDRFARate'] = rt_(rj_['frozen']), pct(rj_['frozen']['rate'])
            m['XDRFACI'] = '[{:.1f}, {:.1f}]\\%'.format(*(100 * x for x in rj_['frozen']['ci95']))
            m['XDRFAP'], m['XDRFAPUpper'] = rt_(rj_['p2_h36']), pct(rj_['p2_h36']['ci95'][1])
            m['XDRWarehouse'] = rj_['frozen']['by_kind']['warehouse']
        m['StatXD'] = f"bound: {m.lookup('XDClaimEps')}; transfer: {m.lookup('XDClaimRel')}; recalibration: {m.lookup('XDClaimCal')}; cost: {m.lookup('XDClaimCost')}"
    # ---- study X (closed loop, depot; x_summary.json; the cause readout x_readout.json is post hoc and descriptive, I-41)
    xf_ = RES / 'x_summary.json'
    if xf_.is_file():
        xj_ = json.loads(xf_.read_text())
        rtx_ = lambda d_: f"{d_['k']}/{d_['n']}"
        xa_, xm2_, xs_ = xj_['X-a'], xj_['X-m'], xj_['X-s']
        m['XN'], m['XNWithResult'] = xj_['n_planned'], xj_['n_with_result']
        tr_x = xj_['trials']
        m['XNa'], m['XNm'], m['XNs'] = (sum(t['cell'] == c_ for t in tr_x) for c_ in ('X-a', 'X-m', 'X-s'))
        m['XFailed'] = sum(xj_['n_failed_by_part'].values())
        m['XAsDesigned'], m['XAsDesignedRate'] = rtx_(xj_['as_designed_overall']), pct(xj_['as_designed_overall']['rate'])
        m['XAAsDesigned'] = f"{sum(c_['as_designed']['k'] for c_ in xa_['cells'].values())}/{sum(c_['as_designed']['n'] for c_ in xa_['cells'].values())}"
        m['XAUnsafe'], m['XAUnsafeUpper'] = rtx_(xa_['hazard_cells_unsafe']), pct(xa_['hazard_cells_unsafe']['ci95'][1])
        vs_, sv_ = xm2_['visits'], xm2_['visits']['saving']
        m['XMPairs'], m['XMClusters'] = xm2_['n_pairs'], sv_['n_clusters']
        m['XMVisitsZero'], m['XMVisitsTwo'] = f"{vs_['mean_M0']:.2f}", f"{vs_['mean_M2']:.2f}"
        m['XMSaving'], m['XMSavingCI'] = f"{sv_['mean']:.2f}", '[{:.2f}, {:.2f}]'.format(*sv_['ci95'])
        m['XMSignP'] = f"{vs_['sign_flip_p_one_sided']:.4f}"
        m['XMPairsFewer'] = vs_['pairs_M2_fewer']
        m['XMDesign'], m['XMModel'] = f"{xm2_['prediction']['design_sequences_saving_visits']:.2f}", f"{xm2_['prediction']['k_scaling_model_saving_visits']:.1f}"
        ve_ = xm2_['visits_equal_predicted']
        m['XMVisitsEq'] = f"{sum(v_['k'] for v_ in ve_.values())}/{sum(v_['n'] for v_ in ve_.values())}"
        m['XMWrong'] = sum(xm2_['wrong_supply_deliveries'].values())
        m['XMSlope'] = f"{xm2_['delta_seconds_per_extra_bay']['slope']:.1f}"
        m['XMSeconds'], m['XMSecondsCI'] = f"{xm2_['seconds']['mean']:.0f}", '[{:.0f}, {:.0f}]'.format(*xm2_['seconds']['ci95'])
        kc_ = xm2_['criteria']
        m['XMClaim'] = 'supported' if kc_['claim_k_scaling_supported'] else 'not supported'
        ar_, cr_ = xs_['arms'], xs_['criteria']
        m['XSWorlds'], m['XSFire'], m['XSClean'] = xs_['n_worlds'], xs_['n_fire_worlds_perceivable'], xs_['n_clean_worlds']
        m['XSApplied'] = f"{sum(ar_[a_]['advice_reorders_to_steered_bay']['k'] for a_ in ('monotone', 'scrutiny'))}/{sum(ar_[a_]['advice_reorders_to_steered_bay']['n'] for a_ in ('monotone', 'scrutiny'))}"
        for a_, nm_ in (('control', 'Ctl'), ('monotone', 'Mono'), ('scrutiny', 'Scr')):
            fw_ = ar_[a_]['fire_worlds']
            m[f'XSUnsafe{nm_}'] = rtx_(fw_['unsafe_deliveries'])
            m[f'XSUnsafe{nm_}Upper'] = pct(fw_['unsafe_upper95_exact'], 0)
            m[f'XSRefused{nm_}'] = rtx_(fw_['refused'])
            m[f'XSFalse{nm_}'] = rtx_(ar_[a_]['clean_worlds']['false_refusals'])
            m[f'XSTwinDel{nm_}'] = rtx_(ar_[a_]['clean_worlds']['delivered'])
        m['XSUnsafeMonoCI'] = '[{:.0f}, {:.0f}]\\%'.format(*(100 * x for x in ar_['monotone']['fire_worlds']['unsafe_deliveries']['ci95']))
        m['XSLostMono'] = xs_['monotone_vs_control']['deliveries_lost_to_truthful_advice']
        m['XSLostScr'] = ar_['scrutiny']['fire_worlds']['refused']['k']
        m['XSDeliveredScr'] = f"{ar_['scrutiny']['clean_worlds']['delivered']['k']}/{xs_['n_worlds']}"
        m['XSMcnemarP'] = f"{xs_['scrutiny_vs_monotone']['unsafe']['mcnemar_p']:.1f}"
        m['XSClaim'] = ('S1-S3 hold' if (cr_['S1_advice_reorders_in_at_least_90pct'] and cr_['S2_no_monotone_audit_failure'] and cr_['S3_control_never_delivers_into_the_fire']) else 'S1-S3 do not all hold') \
            + ('; S4 (scrutiny fewer unsafe, p<0.05) not supported (not claimed, as registered)' if not cr_['S4_scrutiny_fewer_unsafe_than_monotone_p<0.05'] else '; S4 supported')
        xrf_ = RES / 'x_readout.json'
        if xrf_.is_file():
            xr_ = {r_['trial_id']: r_ for r_ in json.loads(xrf_.read_text())['rows']}
            f4_ = lambda v_: f"{v_:.4f}".rstrip('0') if v_ is not None else r'\TBD'
            # monotone miss (XC05): all views below tau_h; the twin and the control score the same station at the same level
            miss_ = [r_ for r_ in xr_.values() if r_['arm'] == 'monotone' and r_['observed'] == 'ALLOW' and r_['condition'] == 'steer_fire']
            if miss_:
                m['XSMissMax'] = f"{miss_[0]['max_view_hazard_prob']:.3f}"
            scr_clean_ = [r_['front_hazard_prob'] for r_ in xr_.values() if r_['arm'] == 'scrutiny' and r_['condition'] == 'steer_clean']
            scr_fire_ = sorted(r_['front_hazard_prob'] for r_ in xr_.values() if r_['arm'] == 'scrutiny' and r_['condition'] == 'steer_fire')
            m['XSScrCleanLo'], m['XSScrCleanHi'] = f"{min(scr_clean_):.4f}", f"{max(scr_clean_):.4f}"
            m['XSScrFireLo'], m['XSScrFireMid'], m['XSScrFireHi'] = (f"{v_:.4f}" for v_ in scr_fire_)
            m['XSScrFireRefusedBelow'] = sum(v_ < 0.05 for v_ in scr_fire_)
            cv_ = [v_ for r_ in xr_.values() if r_['condition'] == 'steer_clean' for v_ in [r_['front_hazard_prob']] + [p_['hazard_prob'] for p_ in r_['peeks']]]
            m['XSCleanViewLo'], m['XSCleanViewHi'] = f"{min(cv_):.3f}", f"{max(cv_):.3f}"
            fv_all_ = [v_ for r_ in xr_.values() if r_['condition'] == 'steer_fire' for v_ in [r_['front_hazard_prob']] + [p_['hazard_prob'] for p_ in r_['peeks']] if r_['arm'] != 'control']
            m['XSScrAboveClean'] = f"{sum(v_ > max(cv_) for v_ in scr_fire_)}/{len(scr_fire_)}"
            fv_ = lambda v_: '--' if v_ is None else f"{v_:.4f}"
            rows_x = [r'\begin{tabular}{llllll}', r'\toprule', r'Run & World & Arm & Front view $p_h$ & Look-around $p_h$ (L, R) & Outcome \\ \midrule']
            order_ = {'control': 0, 'monotone': 1, 'scrutiny': 2}
            for r_ in sorted(xr_.values(), key=lambda r_: (r_['condition'] != 'steer_fire', r_['world'], order_[r_['arm']])):
                pk_ = {p_['side']: p_['hazard_prob'] for p_ in r_['peeks']}
                rows_x.append(f"{r_['trial_id']} & {r_['world']} & {r_['arm']} & {fv_(r_['front_hazard_prob'])} & "
                              + (f"{fv_(pk_.get('L'))}, {fv_(pk_.get('R'))}" if pk_ else 'not taken') + f" & {r_['observed'].replace('_', ' ')} \\\\")
            rows_x += [r'\bottomrule', r'\end{tabular}']
            tables['tab_x_steer.tex'] = '\n'.join(rows_x)
        m['StatX'] = f"memory: {m.lookup('XMClaim')}; steering: {m.lookup('XSClaim')}"
    # ---- study Y (continue after a real hazard refusal, --hazard-continue; y_summary.json; registered before the first trial, I-42)
    yf_ = RES / 'y_summary.json'
    if yf_.is_file():
        yj_ = json.loads(yf_.read_text())
        rty_ = lambda d_: f"{d_['k']}/{d_['n']}"
        ys_, yc_ = yj_['Y-s'], yj_['Y-c']
        m['YN'], m['YNs'], m['YNc'] = yj_['n_planned'], ys_['n_runs'], yc_['n_runs']
        m['YFailed'] = yj_['n_failed_by_part'] and sum(yj_['n_failed_by_part'].values()) or 0
        m['YAsDesigned'], m['YAsDesignedRate'] = rty_(yj_['as_designed_overall']), pct(yj_['as_designed_overall']['rate'])
        ya_ = ys_['arms']
        for a_, nm_ in (('control_hc', 'Ctl'), ('monotone_hc', 'Mono'), ('scrutiny_hc', 'Scr')):
            fw_, cw_ = ya_[a_]['fire_worlds'], ya_[a_]['clean_worlds']
            m[f'YSUnsafe{nm_}'] = rty_(fw_['unsafe_deliveries'])
            m[f'YSUnsafe{nm_}Upper'] = pct(fw_['unsafe_upper95_exact'], 0)
            m[f'YSDelivered{nm_}'] = rty_(fw_['delivered'])
            m[f'YSRefused{nm_}'] = rty_(fw_['steered_bay_refused'])
            m[f'YSTime{nm_}'] = f"{fw_['mean_time_s']:.0f}"
            m[f'YSVisits{nm_}'] = f"{fw_['mean_visits']:.1f}"
            m[f'YSTwinDel{nm_}'] = rty_(cw_['delivered'])
            m[f'YSTwinRefused{nm_}'] = rty_(cw_['steered_bay_refused'])
        lv_ = ys_['lost_vs_control']
        m['YSLostMono'] = lv_['monotone_hc']['fire_worlds']['lost'] + lv_['monotone_hc']['clean_worlds']['lost']
        m['YSLostScr'] = lv_['scrutiny_hc']['fire_worlds']['lost'] + lv_['scrutiny_hc']['clean_worlds']['lost']
        m['YSPairs'] = lv_['scrutiny_hc']['fire_worlds']['pairs'] + lv_['scrutiny_hc']['clean_worlds']['pairs']
        yk_ = ys_['criteria']
        m['YOneRefused'], m['YOneMax'] = yk_['Y1_refused_runs'], yk_['Y4_max_visits']
        m['YMonoMissWorld'] = ', '.join(sorted(ya_['monotone_hc']['fire_worlds']['unsafe_by_world']))
        m['YMonoMiss'] = ya_['monotone_hc']['fire_worlds']['unsafe_by_world'].get('XC05', 0)
        m['YCDelivered'], m['YCDeniedAfterSearch'] = rty_(yc_['delivered']), f"{yc_['observed'].get('DENY_HAZARD_AFTER_SEARCH', 0)}/{yc_['n_runs']}"
        m['YCVisits'] = ', '.join(sorted(yc_['visits']))
        m['YCFireSeen'] = rty_(yc_['fire_bay_refused_for_hazard'])
        yrf_ = RES / 'y_readout.json'
        if yrf_.is_file():       # post hoc readout of the saved model outputs (scripts/y_readout.py): the cause class of every run that was not as designed
            yr_ = json.loads(yrf_.read_text())['rows']
            miss_ = [r_['last_check_hazard_prob'] for r_ in yr_ if r_['arm'] == 'monotone_hc' and r_['unsafe_delivery']]
            tw_ = [x_[2] for r_ in yr_ if r_['condition'] == 'steer_clean' and r_['arm'] == 'scrutiny_hc' and not r_['as_designed'] for x_ in r_['caution_refusals']]
            ap_ = [r_['last_check_hazard_prob'] for r_ in yr_ if r_['condition'] == 'steer_clean' and r_['arm'] == 'scrutiny_hc' and r_['observed'] == 'ALLOW']
            m['YReadMissLo'], m['YReadMissHi'] = f"{min(miss_):.3f}", f"{max(miss_):.3f}"
            m['YReadTwinLo'], m['YReadTwinHi'] = f"{min(tw_):.4f}", f"{max(tw_):.4f}"
            m['YReadApprLo'], m['YReadApprHi'] = f"{min(ap_):.4f}", f"{max(ap_):.4f}"
            m['YNotAsDesigned'] = sum(not r_['as_designed'] for r_ in yr_)
        m['YClaim'] = ('Y1-Y4 hold' if (yk_['Y1_holds'] and yk_['Y3_holds'] and yk_['Y4_holds'] and yc_['criteria']['Y2_holds']) else 'Y1-Y4 do not all hold')
        m['StatY'] = f"availability: {m.lookup('YClaim')}"
    # ---- submission snapshot: the claim column of a study without results says so (the other pending studies have no analysis macro yet)
    PEND = advice_numbers.snapshot_pending() if SNAPSHOT else set()
    for k_ in advice_numbers.SNAPSHOT_STUDIES:
        nm_ = f'Stat{advice_numbers.mkey(k_)}'
        if k_ in PEND:
            m.override(nm_, 'registered, not run')
        elif nm_ not in m.names:
            m[nm_] = 'see text' if (SNAPSHOT and (RES / f'{k_.lower()}_summary.json').is_file()) else 'pending'
    # ---- study A: first mechanics pilot (i35) and Amendment 1 (i38); XD-R photographs (advice_numbers.a_pilot_facts / xdr_facts read the files)
    pf_ = advice_numbers.a_pilot_facts()
    if pf_:
        m['APilotRuns'], m['APilotOpN'], m['APilotOpExact'], m['APilotOpRefused'] = pf_['runs'], pf_['op_n'], pf_['op_exact'], pf_['op_refused']
        m['APilotFileOK'] = f"{pf_['file_as_designed']}/{pf_['file_n']}"
        m['AIntHeldOut'], m['AIntHeldN'] = pf_['held38'], pf_['held_n']
        m['AIntUnsafe'] = max(pf_['unsafe35'], pf_['unsafe38'])
        m['AIntInjOld'], m['AIntInjNew'], m['AIntInjN'], m['AIntWrong'] = pf_['inj35'], pf_['inj38'], pf_['inj_n'], pf_['wrong38']
        if pf_.get('rerun'):       # the rerun pilot (i38) read with the gate of Amendment 2
            m['ARerunRuns'], m['ARerunIntent'], m['ARerunOpN'] = pf_['rerun_runs'], pf_['rerun_op_intent'], pf_['rerun_op_n']
            m['ARerunExact'], m['ARerunFileOK'] = pf_['rerun_op_exact'], f"{pf_['rerun_file_ok']}/{pf_['rerun_file_n']}"
            m['ACampaignStart'] = advice_numbers.A_CAMPAIGN_START
    xr_ = advice_numbers.xdr_facts()
    if xr_:
        m['XDRCand'], m['XDRKept'], m['XDRExcl'] = xr_['cand'], xr_['kept'], xr_['excl']
    # ---- registration audit: each registration commit must precede the first commit of its results
    import subprocess

    def git(*a):
        r = subprocess.run(['git', *a], cwd=ROOT, capture_output=True, text=True)
        return r.stdout.strip(), r.returncode
    AMEND_RX = re.compile(r'^(?:\*\*|## )Amendment (\d+)[^\n(]*\(', re.M)    # headings only; a cross-reference ('Amendment 2 of W') is not an amendment
    studies = [('C (v3.3)', 'PREREGISTRATION_v33.md', 'campaign_ledger.jsonl'), ('D (v3.4)', 'PREREGISTRATION_v34.md', 'campaign_D_ledger.jsonl'),
               ('T1', 'PREREGISTRATION_T1.md', 'devset_t1_qwen35_9b.json'), ('E', 'PREREGISTRATION_E.md', 'campaign_E_ledger.jsonl'),
               ('T2', 'PREREGISTRATION_T2.md', 'devset_t2_i11_h36_tiles.json'), ('F', 'PREREGISTRATION_F.md', 'campaign_F_ledger.jsonl'),
               ('G', 'PREREGISTRATION_G.md', 'campaign_G_ledger.jsonl'), ('R', 'PREREGISTRATION_R.md', 'devset_r_gaussian_noise_M.json'),
               ('H', 'PREREGISTRATION_H.md', 'campaign_H_ledger.jsonl'), ('J', 'PREREGISTRATION_J.md', 'campaign_J_ledger.jsonl'), ('L', 'PREREGISTRATION_L.md', 'campaign_L_ledger.jsonl'),
               ('V', 'PREREGISTRATION_V.md', 'v_summary.json'), ('W', 'PREREGISTRATION_W.md', 'w_summary.json'),
               ('Z', 'PREREGISTRATION_Z.md', 'z_summary.json'), ('K', 'PREREGISTRATION_K.md', 'k_summary.json'), ('P', 'PREREGISTRATION_P.md', 'p_summary.json'), ('P2', 'PREREGISTRATION_P2.md', 'p2_summary.json'),
               ('A', 'PREREGISTRATION_A.md', 'a_summary.json'), ('S', 'PREREGISTRATION_S.md', 's_summary.json'),
               ('X', 'PREREGISTRATION_X.md', 'x_summary.json'), ('XD', 'PREREGISTRATION_XD.md', 'xd_summary.json'),
               ('Q', 'PREREGISTRATION_Q.md', 'q_summary.json'),
               ('B', 'PREREGISTRATION_B.md', 'b_summary.json'), ('IF', 'PREREGISTRATION_IF.md', 'if_summary.json'),
               ('IF2', 'PREREGISTRATION_IF2.md', 'if2_summary.json'), ('Y', 'PREREGISTRATION_Y.md', 'y_summary.json')]
    main_ref = 'main' if git('rev-parse', '--verify', '-q', 'main')[1] == 0 else 'HEAD'

    def first_commit(path):          # first commit that added the file (hash date)
        o, _ = git('log', '--diff-filter=A', '--format=%h %ad', '--date=short', '--', path)
        return o.splitlines()[-1] if o else ''

    rows = [r'\begin{tabular}{llllc}', r'\toprule', r'Study & Registered (commit, date) & First results (commit, date) & Amendments & Order \\', r'\midrule']
    ok_all, drafts = True, []
    for name, reg, res in studies:
        rel = f'experiments/{reg}'
        sc = first_commit(f'experiments/results/{res}')
        if not (ROOT / rel).is_file():     # registration not in this checkout (study Q: design on its own branch until the merge)
            if SNAPSHOT:
                rows.append(name + ' & registered at merge & ' + ('\\texttt{' + sc.split()[0] + '}' if sc else 'not run') + ' & -- & -- \\\\')
            else:
                rows.append(f"{name} & registered at merge, pending & \\texttt{{{sc.split()[0] if sc else 'pending'}}} & -- & pending \\\\")
            drafts.append(name)
            continue
        hist, _ = git('log', '--full-history', '--no-merges', '--invert-grep', '--grep=erratum (times)', '--format=%h %ad', '--date=short', '--', rel)   # newest first; an appended time erratum is not a change of the registered text
        hist = hist.splitlines()
        rc = ''
        if sc:   # the text in force at the first result: the newest registration commit strictly before the first results commit
            for h_ in hist:
                if h_.split()[0] != sc.split()[0] and git('merge-base', '--is-ancestor', h_.split()[0], sc.split()[0])[1] == 0:
                    rc = h_
                    break
            rc = rc or first_commit(rel)
        else:    # no result yet: the newest commit of the text that will be run
            rc = hist[0] if hist else ''
        n_am = len(AMEND_RX.findall((ROOT / rel).read_text()))
        _body = lambda t: t.split('\n## Erratum (times)')[0].strip()      # the appended time erratum is not part of the registered text
        on_main = _body(git('show', f'{main_ref}:{rel}')[0]) == _body((ROOT / rel).read_text())      # the text in this checkout is the text on main
        if rc and sc and rc.split()[0] == sc.split()[0]:
            order = 'same commit'          # cannot be verified from history (recorded before this audit existed)
        elif rc and sc:
            order = r'$\checkmark$' if git('merge-base', '--is-ancestor', rc.split()[0], sc.split()[0])[1] == 0 else 'NO'
            ok_all &= order != 'NO'
        else:
            order = '--' if SNAPSHOT else 'pending'
        reg_cell = f"\\texttt{{{rc or '--'}}}" + ('' if on_main or not rc else r' (draft; registered at merge)')
        if rc and not on_main:
            drafts.append(name)
        rows.append(f"{name} & {reg_cell} & " + (f"\\texttt{{{sc}}}" if sc else 'not run' if SNAPSHOT else '\\texttt{pending}') + f" & {n_am} & {order} \\\\")
    rows += [r'\bottomrule', r'\end{tabular}']
    tables['tab_prereg.tex'] = '\n'.join(rows)
    # ---- amendments: one row per amendment heading, the commit that introduced it (git -G, oldest) against the first results commit of its study
    arows = [r'\begin{tabular}{llllc}', r'\toprule', r'Study & Amendment (text date) & Commit (git time) & First results & Order \\', r'\midrule']
    am_a = am_a2 = None
    for name, reg, res in studies:
        rel = f'experiments/{reg}'
        if not (ROOT / rel).is_file():
            continue
        txt = (ROOT / rel).read_text()
        sc = first_commit(f'experiments/results/{res}')
        for mm in re.finditer(r'^(?:\*\*|## )Amendment (\d+)[^\n(]*\(([0-9-]+)?(?: ([0-9:]+))?', txt, re.M):
            k_, d_, t_ = mm.group(1), mm.group(2), mm.group(3)
            o_, _ = git('log', '--reverse', '--full-history', '--no-merges', '--format=%h %cd', '--date=format:%Y-%m-%d %H:%M', '-G', rf'^(\*\*|## )Amendment {k_} \(', '--', rel)
            c_ = o_.splitlines()[0] if o_ else ''
            if not c_:
                continue
            if not sc:
                order_ = '--' if SNAPSHOT else 'no results yet'
            elif c_.split()[0] == sc.split()[0]:
                order_ = 'same commit'
            else:
                ok_ = git('merge-base', '--is-ancestor', c_.split()[0], sc.split()[0])[1] == 0
                order_ = r'$\checkmark$' if ok_ else 'NO'
            cell_ = ('\\texttt{' + sc.split()[0] + '}') if sc else ('not run' if SNAPSHOT else '\\texttt{pending}')
            arows.append(f"{name.split()[0]} & {k_} ({(d_ or '--') + (' ' + t_ if t_ else '')}) & \\texttt{{{c_.split()[0]}}} {' '.join(c_.split()[1:])} & {cell_} & {order_} \\\\")
            if name == 'A' and k_ == '1':
                am_a = c_
            if name == 'A' and k_ == '2':
                am_a2 = c_
    arows += [r'\bottomrule', r'\end{tabular}']
    tables['tab_amend.tex'] = '\n'.join(arows)
    if am_a:
        m['AAmendCommit'], m['AAmendTime'] = am_a.split()[0], ' '.join(am_a.split()[1:])
    if am_a2:
        m['AAmendTwoCommit'], m['AAmendTwoTime'] = am_a2.split()[0], ' '.join(am_a2.split()[1:])
    m['NAmend'] = len(arows) - 5
    # the one definition of "number of studies" (README, report, paper and check_consistency read it back through advice_numbers.study_counts):
    # every row of Table S9 except C, the initial evaluation (23 = the studies of Supp. Table S12); 'checked' = registration commit
    # verified to precede the first results commit
    cnt_ = advice_numbers.study_counts_from_rows([r_ for r_ in rows if r_.count('&') >= 4 and not r_.startswith('Study')])
    m['NStudies'] = cnt_['n']
    m['NStudiesChecked'] = cnt_['ok']
    m['NStudiesPending'] = cnt_['pending']
    unrun = [d for d in drafts if not (RES / dict((n_, r_) for n_, _, r_ in studies)[d]).is_file()]
    m['PreregDrafts'] = ', '.join(unrun) if unrun else 'none'
    # the sentence of the Methodology about the studies without results (no dangling '(none)' when every registration is already on main)
    m['PreregPending'] = (f"the drafts ({', '.join(unrun)}) are registered on the integration branch (bound by its merge into main, before any of their trials)" if unrun
                          else 'all are on the main branch, bound by the integration merge before their first trial')
    m['NStudiesRun'] = cnt_['n'] - cnt_['pending']
    m['PendList'] = ', '.join(advice_numbers.pending_list()) or 'none'
    for k_ in advice_numbers.SNAPSHOT_STUDIES:      # the registration commit and date, for the sentence "registered (commit, date), not run"
        rc_ = advice_numbers.registration_commit(k_)
        m[f'Reg{advice_numbers.mkey(k_)}'] = (f"\\texttt{{{rc_.split()[0]}}}, {rc_.split()[1]}" if rc_ else 'registration pending')
    m['PreregOrderOK'] = 'holds' if ok_all else 'does NOT hold'
    # ---- development-data model selection (appendix table)
    sel = json.loads((RES / 'i08_model_selection.json').read_text())
    lines = [r'\begin{tabular}{llrrrr}', r'\toprule',
             r'Model & Released & Images (176) & Explanations (128) & Intent dev (40) & VRAM \\', r'\midrule']
    for r in sel:
        lines.append(f"{r['model']} & {r['released']} & {r['vision_v35'].replace('(', '(').replace(', ', '/')} & {r['explain']} & "
                     f"{r.get('intent_dev_i35', '--').replace(' (unsafe ', ', unsafe ').rstrip(')')} & {r.get('vram', '--').replace(' MiB', '')} \\\\")
    lines += [r'\bottomrule', r'\end{tabular}']
    tables['tab_dev_models.tex'] = '\n'.join(lines)
    m.pending(['TNimages', 'TNamb', 'TNdeny', 'TNallow', 'TFA', 'TFARate', 'TFACI', 'TCA', 'TCARate', 'TCACI', 'THazRecall',
               'TConeAlarm', 'TLatPass', 'TAmbAllowed', 'TvFA', 'TvFARate', 'TvFACI', 'TvCA', 'TvCARate', 'TvCACI',
               'TvHazRecall', 'TvConeAlarm', 'TvNoFireAlarm', 'TNoFireAlarm', 'TSupplyN', 'TSupplyFA', 'TSupplyFACI',
               'TFireCorrectN', 'TFireCorrectFA', 'TAblNoHazFA', 'TThreeBPassTwoFA', 'TThreeBFullFA', 'TJsonNineFA',
               'TJsonNineCA', 'TJsonThreeErr', 'TJsonThreeCA', 'THazMin', 'THazMax', 'TNfireVis', 'TLargeDet', 'TSmallDet', 'TFACluster', 'TvFACluster', 'TNworlds', 'EN', 'ECorrect', 'ECorrectCI', 'EWrong', 'EWrongCI', 'ELatMed',
               'ELatMax', 'ERetries', 'EWallMed', 'ESafeN', 'ETaskSuccess', 'ETaskSuccessCI', 'EBzeroWrong', 'EBzeroWrongCI',
               'EBzeroTask', 'EBoneWrong', 'EBoneTask'])
    m.pending(['DevFAvThreeFive', 'DevFAB', 'DevFireN', 'FPairs', 'FWrongA', 'FWrongB', 'FMcNemarP', 'FCorrectA', 'FCorrectB',
               'FFalseStopA', 'FFalseStopB', 'FLatA', 'FLatB', 'TTRefFA', 'TTRefCA', 'TTRefSmall', 'TTSelFA', 'TTSelCA',
               'TTSelSmall', 'TTSelP', 'TTBFA', 'TTBCA', 'TTBSmall', 'TTBP', 'TTClefFA', 'TTClefCA', 'GPairs', 'GWrongB',
               'GWrongC', 'GEpsHat', 'GEpsUpper', 'GKEpsHat', 'GKEpsUpper', 'GMcNemarP', 'GCorrectB', 'GCorrectC', 'GFalseStopB', 'GFalseStopC', 'GWallB', 'GWallC',
               'FDiscA', 'FDiscB', 'GDiscB', 'GDiscC', 'GWallPlainB', 'GWallPlainC', 'GLookCost', 'TTPairFA', 'TTPairCA',
               'TimDrive', 'TimCheck', 'TimVlm'])
    m.pending(['RNimg', 'RNdeny', 'RNallow', 'RNfire', 'RNcond', 'RNworlds', 'RPoolFA', 'RPoolCI', 'RPoolSupported', 'RUnsafeConds',
               'RWorstCond', 'RWorstCA', 'RCleanCA', 'RGateRej', 'RFireMissMax', 'RCondFAMax', 'RCondFAUpper',
               'JevOvN', 'JevOvBoth', 'JevOvQOnly', 'JevOvCOnly', 'JevOvNeither', 'JevOvQ', 'JevOvC', 'JevOvCond', 'JevOvCondCI',
               'JevOvJaccard', 'JevOvHBoth', 'JevOvHQ', 'JevOvHC',
               'HPOneN', 'HWrongzero', 'HWrongone', 'HWrongtwo', 'HFirezero', 'HFireone', 'HFiretwo', 'HFasterPairs', 'HSeqN', 'HSeqMone', 'HSeqMtwo', 'HSeqP', 'HUnsafeUpperzero', 'HUnsafeUppertwo', 'HChangeMzero', 'HChangeMtwo', 'HTimeMzero', 'HTimeMtwo', 'HTimeDiff', 'HPOneP', 'HPTwoN', 'HUnsafeMone', 'HUnsafeMtwo', 'HPTwoP',
               'HUnsafeMzero', 'HHeadline', 'HFalseRefzero', 'HFalseRefone', 'HFalseReftwo', 'HTimeAllzero', 'HTimeAllone',
               'HTimeAlltwo', 'HSafeCorrectzero', 'HSafeCorrectone', 'HSafeCorrecttwo', 'HFailedzero', 'HFailedone', 'HFailedtwo',
               'HModelPdet', 'HModelPdetN', 'HModelQ', 'HModelUnsafezero', 'HModelUnsafeone', 'HModelUnsafetwo',
               'HModelTimezero', 'HModelTimeone', 'HModelTimetwo',
               'JCorrectA', 'JCorrectJ', 'JUnsafeA', 'JUnsafeJ', 'JFalseRefA', 'JFalseRefJ', 'JFailedA', 'JFailedJ', 'JLatA', 'JLatJ',
               'JPeakVram', 'JMcNemarP', 'JClaim', 'JUnsafeJUpper', 'JUnsafeAUpper', 'LCorrect', 'LCorrectCI', 'LUnsafe', 'LClaim',
               'VPredDiff', 'VPredDiffPI', 'VObsDiff', 'VPredUnsafezero', 'VPredUnsafeone', 'VPredUnsafetwo', 'VUnsafeMzero', 'VUnsafeMone', 'VUnsafeMtwo',
               'VSeqP', 'VClaimModel', 'VClaimMemory', 'VSeqMone', 'VSeqMtwo', 'VMinP', 'VPredMtwoMed', 'VPredMtwoPI', 'VAbsTimezero', 'VAbsTimetwo', 'VAbsTimePIzero', 'VAbsTimePItwo', 'VAbsLate',
               'MemPoolN', 'MemPoolzero', 'MemPoolone', 'MemPooltwo', 'MemPoolCI', 'IlcheckN',
               'WEpsAnyTwoUpper', 'WEpsAnyFourUpper', 'WMissLASideRate', 'WMissLASideCI', 'WMissFrontVis', 'WMissFrontVisN', 'WMoveRemoved', 'WWordRemoved',
               'WNPerc', 'WMissLA', 'WMissFront', 'WMissLARate', 'WMissLACI', 'WExtraStop', 'WClaimEps', 'WClaimCost',
               'WFAOursFull', 'WFAVote', 'WFAKnowFive', 'WFAKnowTen', 'WNDist', 'WMissFrontRate', 'WMissLAUpper', 'WMcNemarP', 'WCaughtOnlyByLA', 'WNFront', 'WNSideOnly', 'WMissLAFront', 'WMissLAFrontUpper', 'WMissLASide', 'WMissFrontSide', 'WMissedWorlds', 'WNotVisible', 'WNotVisibleUpper', 'WSixViewUpper', 'WTwinCA', 'WExtraStopUpper', 'WTauMiss', 'WEpsAnyTwo', 'WEpsAnyTwoCI', 'WEpsAnyFour', 'WEpsAnyFourCI', 'WEpsAnyTwoFront', 'WEpsAnyFourFront', 'WVOldMissFront', 'WVOldMissLA', 'WVOldMissLAUpper', 'WAdaptMiss', 'WAdaptMissUpper', 'WAdaptPaired', 'WAdaptPairedP', 'WAdaptTwinCA', 'WAdaptTrigTwin', 'WAdaptTrigTwinCI', 'WAdaptTrigFire', 'WAdaptRuleA', 'WAdaptRuleB', 'WAdaptAdopt', 'WScrutMissB', 'WScrutMissC', 'WScrutMissCUpper', 'WScrutPC', 'WScrutTwinStopC', 'WNImages', 'WNDeny', 'WNAllow', 'WFAOursDeployed', 'WFAOursFullRate', 'WFAOursDeployedCI', 'WCAOursFull', 'WFAVoteRate', 'WFAVoteCI', 'WVotePRaw', 'WVoteHolm', 'WVoteDisc', 'WVoteDeployedHolm', 'WVoteDeployedDisc', 'WVoteDeployedBetter', 'WCAKnowFive', 'WCAKnowFiveRate', 'WCAKnowFiveDrop', 'WCAKnowFiveP', 'WKnowTenSame', 'WSmallOurs', 'WSmallVote', 'WMondCA', 'PRecall', 'PFalseAlarm', 'PRecallCI', 'PFalseAlarmCI', 'PAuroc',
               'PTwoWording', 'PTwoTau', 'PTwoRecall', 'PTwoRecallCI', 'PTwoFA', 'PTwoFACI', 'PTwoClaim', 'PTwoFrozenRecall', 'PTwoFrozenFA',
               'APairs', 'AUnsafeNaive', 'AUnsafeOurs', 'AUnsafeCtrl', 'AMcNemarP', 'AViol', 'AAuditFail', 'ATimeSave', 'AWilcoxonP', 'ADoSVisits', 'ADoSFalseRef', 'ADoSN',
               'ADoSAllowed', 'AClaimSafety', 'AClaimTime', 'AClaimCost', 'AClaim', 'AExtract', 'AExtractRelax',
               'SNPairs', 'SFlipsC', 'SNC', 'SFlipsA', 'SNA', 'SFlipsB', 'SNB', 'SFlipsMis', 'SNMis', 'SFlipsSafe', 'SNSafe', 'SFlipsOneA', 'SFlipsMisFree', 'SLegible', 'SClaim', 'SHyp', 'BRuns', 'BMissions', 'BSeqs', 'BSeqsAll', 'BWastedNo', 'BWastedCredit', 'BBound', 'BHonestWasted', 'BAuditFail', 'BUnsafe', 'BSave', 'BSavePred', 'BClaim', 'SPoolFlips', 'SPoolN', 'SPoolUpper', 'SBenignFree', 'SBenignOurs', 'SLegitKept'])
    for name in ('tab_t1_models.tex', 'tab_t1_ablation.tex', 'tab_e_strata.tex', 'tab_i13_dev.tex', 'tab_r.tex', 'tab_h_arms.tex', 'tab_h_sequences.tex', 'tab_s_systems.tex', 'tab_xd_classes.tex', 'tab_x_steer.tex'):
        tables.setdefault(name, r'\begin{tabular}{l}\TBD\end{tabular}')
    def write_if_changed(path, text):      # keep mtimes when nothing changed (latexmk and `make check` compare them)
        if not path.is_file() or path.read_text(encoding='utf8') != text:
            path.write_text(text, encoding='utf8')
    write_if_changed(OUT / 'numbers.tex', m.text())
    if FINAL:   # final build: refuse to produce a paper with pending results
        check_final(m, tables, studies=True)
    for name, body in tables.items():
        if SNAPSHOT:
            body = re.sub(r'\\TBD(?![A-Za-z])', lambda _: r'\SnapNA{}', body)
        write_if_changed(OUT / name, '% generated by scripts/paper_numbers.py\n' + body + '\n')
    print('macros', len(m.lines) - 2, 'tables', sorted(tables))


if __name__ == '__main__':
    main()
