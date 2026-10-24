#!/usr/bin/env python3
"""Every registered study must appear in every generated audit artifact (incident I-136: Table S9 had silently stopped at study Y, 19 studies unaudited).

  python3 scripts/check_study_coverage.py      # exit 0 = complete; exit 1 = a study is missing somewhere (printed)

Source of truth: the registration files experiments/PREREGISTRATION_*.md, mapped to study labels by scripts/make_registrations.STUDIES (which itself
asserts that every file has an entry).  Checked artifacts (files on disk, not code, so a stale generated file is caught too):
  * docs/paper/tab_prereg.tex   one row per study (Table S9, registration order)
  * docs/paper/tab_amend.tex    one row per Amendment heading of every study (Table S10)
  * docs/REGISTRATIONS.md       one row per study (the registration ledger)
  * README.md                   the audit sentence names the same number of studies ("論文のN研究")
  * no script keeps a hand-written study list: a literal tuple/list naming 12 or more study keys must be the ledger list itself.
Called by tests/test_study_coverage.py, scripts/check_consistency.py, scripts/final_check.sh and the Stop hook (scripts/stop_hook_gpu_idle.py).
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import make_registrations as mr  # noqa: E402

AMEND_RX = re.compile(r'^(?:\*\*|## )Amendment (\d+)[^\n(]*\(', re.M)       # same rule as paper_numbers.py (Table S10)
HAND_LIST_MIN = 12


def studies():
    """[(short label, registration file)] for every registration file that exists."""
    out = []
    for lab, key, _res in mr.STUDIES:
        f = ROOT / 'experiments' / f'PREREGISTRATION_{key}.md'
        if f.is_file():
            out.append((lab.split()[0], f))
    return out


def row_labels(tex: Path) -> list:
    return [x.split('&')[0].strip().split()[0] for x in tex.read_text(encoding='utf8').splitlines()
            if x.count('&') >= 3 and not x.startswith(('Study', r'\toprule', r'\midrule'))]


def hand_lists(keys: set) -> list:
    """Script lines with a literal of >= HAND_LIST_MIN quoted study keys (a hand-written study list that will go stale)."""
    bad = []
    for f in sorted((ROOT / 'scripts').glob('*.py')):
        if f.name in ('make_registrations.py', 'check_study_coverage.py'):
            continue
        lines = f.read_text(encoding='utf8').splitlines()
        i = 0
        while i < len(lines):              # a window of 8 lines, so a list written over several lines is caught too
            win = '\n'.join(lines[i:i + 8])
            q = set(re.findall(r"'([A-Z][A-Z0-9]{0,3})'", win))
            if len(q & keys) >= HAND_LIST_MIN and 'study-subset' not in win and 'make_registrations' not in win:
                bad.append(f'{f.relative_to(ROOT)}:{i + 1}')
                i += 8
            else:
                i += 1
    return bad


def problems() -> list:
    st = studies()
    labels = [s for s, _ in st]
    out = []
    pre = ROOT / 'docs/paper/tab_prereg.tex'
    got = row_labels(pre) if pre.is_file() else []
    miss = [s for s in labels if s not in got]
    if miss:
        out.append(f'Table S9 (tab_prereg.tex) lacks {len(miss)} studies: {" ".join(miss)}  -> python3 scripts/paper_numbers.py')
    am = ROOT / 'docs/paper/tab_amend.tex'
    rows = row_labels(am) if am.is_file() else []
    for s, f in st:
        n = len(AMEND_RX.findall(f.read_text(encoding='utf8')))
        if rows.count(s) != n:
            out.append(f'Table S10 (tab_amend.tex): {s} has {rows.count(s)} rows, its registration has {n} amendments  -> python3 scripts/paper_numbers.py')
    reg = (ROOT / 'docs/REGISTRATIONS.md').read_text(encoding='utf8') if (ROOT / 'docs/REGISTRATIONS.md').is_file() else ''
    miss = [s for s in labels if not re.search(rf'^\| {re.escape(s)}[ |(]', reg, re.M)]
    if miss:
        out.append(f'docs/REGISTRATIONS.md lacks {" ".join(miss)}  -> python3 scripts/make_registrations.py')
    readme = (ROOT / 'README.md').read_text(encoding='utf8')
    n_paper = len([s for s in labels if s != 'C'])
    for m in re.finditer(r'論文の(\d+)研究', readme):
        if int(m.group(1)) != n_paper:
            out.append(f'README says 論文の{m.group(1)}研究, the registrations give {n_paper}  -> python3 scripts/paper_numbers.py && python3 scripts/update_readme_results.py')
    keys = set(labels) | {k for _l, k, _r in mr.STUDIES}
    for loc in hand_lists(keys):
        out.append(f'hand-written study list (derive it from make_registrations.STUDIES, or mark the line "study-subset" if it is a deliberate subset): {loc}')
    return out


def main():
    p = problems()
    for x in p:
        print('COVERAGE:', x)
    print(f'{len(p)} coverage problems ({len(studies())} registered studies)')
    return 1 if p else 0


if __name__ == '__main__':
    sys.exit(main())
