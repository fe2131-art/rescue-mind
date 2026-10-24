#!/usr/bin/env python3
"""Has a finished study been taken into every document? (I-155; FINAL_PLAN step 1)

  python3 scripts/ingest_check.py JL IJ JM      # exit 1 and a list of what is missing

For each study with a summary file in experiments/results/: the supplement section exists (not only the draft) and its Reading is no
longer the placeholder; its paper macros are in docs/paper/numbers.tex; README names it; the YouTube description names it;
FINDINGS.md, IMPROVEMENT_LOG.md (a Result line) and TRIAL_AND_ERROR.md mention it; every failed claim of it is placed by trial_chain.
A study without a summary file is reported as "not finished" (not an error).
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
sys.path.insert(0, str(ROOT / 'scripts'))

PLACEHOLDER = '(Written after the numbers'


def problems(study: str) -> list:
    s, low = study.upper(), study.lower()
    summ = RES / f'{low}_summary.json'
    if not summ.is_file():
        return [f'{s}: not finished (no {summ.name})']
    out = []
    sec = ROOT / 'docs/paper' / f'{low}_section.tex'
    if not sec.is_file():
        out.append(f'{s}: docs/paper/{sec.name} missing (copy the draft and write the Reading)')
    elif PLACEHOLDER in sec.read_text(encoding='utf8'):
        out.append(f'{s}: {sec.name} still has the placeholder Reading')
    nums = (ROOT / 'docs/paper/numbers.tex').read_text(encoding='utf8')
    if not re.search(rf'\\newcommand\{{\\{s}[A-Z]', nums):
        out.append(f'{s}: no {s}* macro in numbers.tex (run scripts/paper_numbers.py)')
    for rel, pat in (('README.md', f'評価{s}'), ('docs/YOUTUBE_DESCRIPTION.md', f'評価{s}'), ('docs/FINDINGS.md', rf'\b{s}\b'),
                     ('docs/TRIAL_AND_ERROR.md', rf'\b{s}\b')):
        if not re.search(pat, (ROOT / rel).read_text(encoding='utf8')):
            out.append(f'{s}: {rel} does not mention {s}')
    log = (ROOT / 'docs/IMPROVEMENT_LOG.md').read_text(encoding='utf8')
    if not re.search(rf'^## [^\n]*(result[^\n]*\b{s}(\d|\b)|\b{s}\b[^\n]*result)', log, re.M | re.I):      # '## I-107 Result ...: JK1-JK3 hold' or '## I-95 ... GM result integrated'
        out.append(f'{s}: IMPROVEMENT_LOG has no Result line for {s}')
    import trial_chain
    if trial_chain.unplaced():
        out.append(f'trial_chain: unplaced failed claims {trial_chain.unplaced()}')
    return out


def main(argv):
    studies = argv or ['JL', 'IJ', 'JM']
    p = [x for s in studies for x in problems(s)]
    for x in p:
        print('INGEST:', x)
    hard = [x for x in p if 'not finished' not in x]
    print(f'{len(hard)} ingestion problems ({", ".join(studies)})')
    return 1 if hard else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
