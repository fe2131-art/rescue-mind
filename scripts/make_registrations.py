#!/usr/bin/env python3
"""Generate docs/REGISTRATIONS.md, the registration ledger, from git (no hand-written numbers).

For every experiments/PREREGISTRATION_*.md:
  * binding   = the commit that put the file on `main`: for a file already on main before the integration merge INTEGRATION_MERGE it is
    the first commit of main's first-parent line that added it; for the files that came with that merge it is the merge itself;
  * sha256    = of the file at that commit ("bound"), at the first results commit ("at results", if any) and at HEAD;
  * results   = the first commit that added the study's results file (experiments/results/<file>), and whether the binding precedes it;
  * amendments = one row per `Amendment` heading: the commit that introduced it (oldest `git log -G`), its git time, the date/time
    written in the heading, whether that text is later than the commit time (then the commit time is the binding one; the file
    carries an appended "Erratum (times)"), and whether the amendment commit precedes the study's first results commit.

The file is deterministic: it depends on the git history and on the files at HEAD only (no clock).  `--check` exits 1 when
docs/REGISTRATIONS.md differs from what this script would write (used by scripts/check_consistency.py).
Usage: python3 scripts/make_registrations.py [--check]
"""
from __future__ import annotations
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/REGISTRATIONS.md'
ERRATUM_RX = re.compile(r'^## Erratum \(times\)', re.M)
ERRATUM_GREP = 'erratum (times)'                    # subject marker of the commits that only append a time erratum
# study label -> (registration file key, results file whose first commit is "the first result")
STUDIES = [
    ('C (v3.3)', 'v33', 'campaign_ledger.jsonl'), ('D (v3.4)', 'v34', 'campaign_D_ledger.jsonl'),
    ('T1', 'T1', 'devset_t1_qwen35_9b.json'), ('E', 'E', 'campaign_E_ledger.jsonl'), ('T2', 'T2', 'devset_t2_i11_h36_tiles.json'),
    ('F', 'F', 'campaign_F_ledger.jsonl'), ('G', 'G', 'campaign_G_ledger.jsonl'), ('R', 'R', 'devset_r_gaussian_noise_M.json'),
    ('H', 'H', 'campaign_H_ledger.jsonl'), ('J', 'J', 'campaign_J_ledger.jsonl'), ('L', 'L', 'campaign_L_ledger.jsonl'),
    ('V', 'V', 'v_summary.json'), ('W', 'W', 'w_summary.json'), ('Z', 'Z', 'z_summary.json'), ('K', 'K', 'k_summary.json'),
    ('P', 'P', 'p_summary.json'), ('P2', 'P2', 'p2_summary.json'), ('A', 'A', 'a_summary.json'), ('S', 'S', 's_summary.json'),
    ('X', 'X', 'x_summary.json'), ('XD', 'XD', 'xd_summary.json'), ('Q', 'Q', 'q_summary.json'),
    ('B', 'B', 'b_summary.json'), ('IF', 'IF', 'if_summary.json'), ('IF2', 'IF2', 'if2_summary.json'), ('Y', 'Y', 'y_summary.json')]
# facts about the running campaigns that git cannot show (source: the untracked campaign ledger in the main checkout)
NOTES = {'A': 'the A campaign (226 trials) started 2026-10-18 11:11 JST (first trial A001): after both amendments and after the commits above'}
HEAD = 'HEAD'
# The merge of the integration branch i21-depot into main (2026-10-18 09:08).  Main was later fast-forwarded to the integration line, so the
# first-parent history of main no longer shows this merge; it is therefore named here.  Its first parent is the main tip before the merge.
INTEGRATION_MERGE = '587f033'


def git(*a):
    r = subprocess.run(['git', *a], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.rstrip('\n'), r.returncode


def sha(text):
    return hashlib.sha256(text.encode('utf8')).hexdigest()[:16] if text is not None else '--'


def show(commit, rel):
    o, rc = git('show', f'{commit}:{rel}')
    return o + '\n' if rc == 0 else None


def tm(iso):                       # 2026-10-18T09:08:26+09:00 -> 2026-10-18T09:08
    return iso[:16]


def main_ref():
    """The commit whose first-parent line is main as it was before the integration merge."""
    if git('rev-parse', '--verify', '-q', INTEGRATION_MERGE + '^1')[1] == 0:
        return INTEGRATION_MERGE + '^1'
    return 'HEAD'


def binding_commit(rel, base):
    """(hash, iso time) of the commit that put `rel` on main (see the module docstring)."""
    if show(base, rel) is not None:                       # already on main before the integration merge
        return first_commit(rel, base, first_parent=True)
    if show(INTEGRATION_MERGE, rel) is not None:          # came with the integration merge
        o = git('log', '-1', '--format=%h %cI', INTEGRATION_MERGE)[0]
        return tuple(o.split())
    return first_commit(rel)                              # later registrations: the commit that added the file


def is_anc(a, b):
    return git('merge-base', '--is-ancestor', a, b)[1] == 0


def first_commit(path, ref=HEAD, first_parent=False):
    """(hash, iso time) of the oldest commit that added `path`, or None."""
    args = ['log', ref] + (['--first-parent'] if first_parent else []) + ['--diff-filter=A', '--format=%h %cI', '--', path]
    o, _ = git(*args)
    return tuple(o.splitlines()[-1].split()) if o else None


def amendments(txt):
    """[(number or '', text date, text time)] for every Amendment heading (numbered or not)."""
    return [(m.group(1) or '', m.group(2), m.group(3))
            for m in re.finditer(r'^(?:\*\*|## )Amendment(?: (\d+))?[^\n(]*\(([0-9-]+)?(?: ([0-9:]+))?', txt, re.M)]


def introducing_commit(rel, k):
    pat = rf'^(\*\*|## )Amendment {k} \(' if k else r'^(\*\*|## )Amendment \('
    o, _ = git('log', '--reverse', '--full-history', '--no-merges', '--format=%h %cI', '-G', pat, '--', rel)
    return tuple(o.splitlines()[0].split()) if o else None


def text_later(d, t, iso):
    """True when the date (and time, when written) in the amendment heading is later than the commit time; None without a date."""
    if not d:
        return None
    cd, ct = iso[:10], iso[11:16]
    if d != cd:
        return d > cd
    return (t[:5] > ct) if t else False


def build():
    mref = main_ref()
    known = {f'PREREGISTRATION_{k}.md' for _, k, _ in STUDIES}
    unknown = [f.name for f in sorted(ROOT.glob('experiments/PREREGISTRATION_*.md')) if f.name not in known]
    assert not unknown, f'registration files without an entry in scripts/make_registrations.py: {unknown}'
    rows, arows, erratum_studies, merge_bound = [], [], [], {}
    for label, key, res in STUDIES:
        rel = f'experiments/PREREGISTRATION_{key}.md'
        if not (ROOT / rel).is_file():
            continue
        short = label.split()[0]
        b = binding_commit(rel, mref)
        rc_ = first_commit(f'experiments/results/{res}')
        bound_txt, head_txt = show(b[0], rel), show(HEAD, rel)
        res_txt = show(rc_[0], rel) if rc_ else None
        order = 'no results yet'
        if rc_:
            order = 'same commit' if rc_[0] == b[0] else ('yes' if is_anc(b[0], rc_[0]) else 'NO')
        last = git('log', '-1', HEAD, '--invert-grep', f'--grep={ERRATUM_GREP}', '--format=%h %cI', '--', rel)[0].split()
        has_err = bool(ERRATUM_RX.search(head_txt or ''))
        if has_err:
            erratum_studies.append(short)
        merge_bound.setdefault(b[0], []).append(short)
        rows.append(f"| {label} | `{b[0]}` {tm(b[1])} | `{sha(bound_txt)}` | "
                    f"{('`' + rc_[0] + '` ' + tm(rc_[1])) if rc_ else '--'} | {('`' + sha(res_txt) + '`') if rc_ else '--'} | {order} | "
                    f"`{last[0]}` {tm(last[1])} | `{sha(head_txt)}`{' (= bound)' if head_txt == bound_txt else ''}{' + erratum' if has_err else ''} |")
        for k, d, t in amendments(head_txt or ''):
            c = introducing_commit(rel, k)
            if not c:
                continue
            late = text_later(d, t, c[1])
            if not rc_:
                o2 = 'no results yet'
            elif c[0] == rc_[0]:
                o2 = 'same commit'
            else:
                o2 = 'yes' if is_anc(c[0], rc_[0]) else 'NO'
            arows.append(f"| {short} | {k or '--'} | `{c[0]}` {tm(c[1])} | {(d or '--') + (' ' + t if t else '')} | "
                         f"{'--' if late is None else ('later than the commit; the commit time is binding' if late else 'no')} | "
                         f"{('`' + rc_[0] + '` ' + tm(rc_[1])) if rc_ else 'none yet'} | {o2} |")
    return mref, rows, arows, erratum_studies, merge_bound


def render():
    mref, rows, arows, erratum_studies, merge_bound = build()
    m_hash, m_studies = max(merge_bound.items(), key=lambda kv: len(kv[1]))
    m_time = tm(git('log', '-1', '--format=%cI', m_hash)[0])
    L = ['# Registration ledger',
         '',
         f'Generated by `scripts/make_registrations.py` from `git log` (the first-parent line of `main` before the integration merge `{INTEGRATION_MERGE}`, and that merge) and from the files at HEAD; '
         'it contains no clock time, so it changes only when a registration, an amendment or a results file changes. '
         'Do not edit it by hand: `python3 scripts/make_registrations.py` rewrites it and `scripts/check_consistency.py` fails when it is stale.',
         '',
         f'A pre-registration binds from the first commit in which it is on `main`; the first-parent history of `main` gives that commit. '
         f'The pre-registrations of {", ".join(m_studies)} reached `main` with the integration merge `{m_hash}` at {m_time} JST. '
         "Study A's pilot started at 09:14 on that day; IF, S, B, XD, X and Q had not run any trial or inference at that time.",
         '',
         'Some of these files still carry a "DRAFT" line in their own text. That line describes the draft stage *before* the merge. '
         'The binding version is the one in the table below. The text of a registration is not edited after the merge, so that it '
         'stays byte-identical up to the amendments. An amendment is only appended, with its own date and commit (table "Amendments" below).',
         '',
         'Verify any row: `git log 587f033^1 --first-parent --format=\'%h %cI\' --diff-filter=A -- experiments/PREREGISTRATION_X.md` (first commit on main; empty for the files that came with the merge `587f033`, whose tree contains them while its first parent does not), '
         '`git merge-base --is-ancestor <registration commit> <first result commit>`, `git show <commit>:experiments/PREREGISTRATION_X.md | sha256sum`. '
         'An external timestamp (OpenTimestamps; hashes only) of the manifest `docs/timestamps/registrations_manifest_20261019.txt` (the hash of this file and of every commit that touched it, as of 2026-10-19) proves that these hashes existed by the Bitcoin block time of its `.ots` proof, not the order of the earlier studies; study Y has its own stamp, taken before its first trial (`docs/timestamps/study_y_registration.txt.ots`).',
         '',
         '## Registrations',
         '',
         '"Bound" is the text at the binding commit, "at results" the text at the first results commit, "HEAD" the text at HEAD '
         '(sha256, first 16 hex digits). "+ erratum" marks a file to which an "Erratum (times)" section was appended after the fact '
         '(see below); the registered text above it is unchanged. "Last change" skips commits that only append such an erratum. '
         'The first results commit is the first commit that added the study\'s results file (`experiments/results/`); C\'s registration and ledger entered the repository together, '
         'so their order cannot be verified from the history.',
         '',
         '| study | binding commit, time (JST) | sha256 bound | first results commit, time | sha256 at results | binding precedes results | last change of the text | sha256 at HEAD |',
         '|---|---|---|---|---|---|---|---|'] + rows + [
         '',
         '## Amendments',
         '',
         'One row per `Amendment` heading in a registration file (the rows of the amendments table of the paper supplement, '
         '`docs/paper/tab_amend.tex`, plus the unnumbered ones). "Commit" is the oldest commit that introduced the heading; its git time is the binding time. '
         '"Text date" is what the heading itself says. Where that is later than the commit time, the commit time is the binding one and the file '
         'ends with an appended `Erratum (times)` that says so (studies: ' + ', '.join(erratum_studies) + '). '
         'The last column asks whether the amendment commit precedes the study\'s first results commit.',
         '',
         '| study | amendment | commit, time (JST) | text date | text vs commit | first results commit | amendment precedes first results |',
         '|---|---|---|---|---|---|---|'] + arows + ['']
    for k, v in NOTES.items():
        L.append(f'* Study {k}: {v}.')
    L += ['',
          'The default of the v3.6 robot stays the intent prompt i35; study IF measures i35, as registered. The registered text of A was amended '
          '(Amendment 1: i38 for every A run; Amendment 2: the operator-channel pilot gate is intent acceptance, exact extraction is reported); '
          'compare "sha256 bound" with "sha256 at HEAD" in the first table.', '']
    return '\n'.join(L)


def main():
    txt = render()
    if '--check' in sys.argv:
        cur = OUT.read_text(encoding='utf8') if OUT.is_file() else ''
        if cur != txt:
            print('docs/REGISTRATIONS.md is stale: run python3 scripts/make_registrations.py')
            raise SystemExit(1)
        print('docs/REGISTRATIONS.md up to date')
        return
    OUT.write_text(txt, encoding='utf8')
    print('wrote', OUT.relative_to(ROOT), f'({txt.count(chr(10))} lines)')


if __name__ == '__main__':
    main()
