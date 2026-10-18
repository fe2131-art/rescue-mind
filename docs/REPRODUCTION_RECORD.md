# Reproduction record: clean-clone `make verify`

A third-party-style run of the Proposition 2 machine check, following `docs/REPRODUCE.md` section 3 on a fresh clone and a fresh venv.
Scratch directory below is written `<scratch>`.

## Result

**PASS.** `make verify` exited 0 and printed `VERIFY_OK: every verdict equals the committed record`; pytest `90 passed`.

## Environment

| Item | Value |
|---|---|
| Date (UTC) | 2026-10-18 |
| Commit under test | `5c95d70e4a8fd7525c910c528fee9bab08f43dae` (branch `i21-depot`, cloned from the GitHub origin) |
| OS | Ubuntu 22.04.5 LTS, Linux 5.15, 4-core Intel Xeon E5-2623 v3 @ 3.0 GHz |
| Python | 3.10.12 (fresh `python3 -m venv`) |
| z3-solver | 5.3.1.0 |
| hypothesis | 6.168.5 |
| pytest | 9.1.1 |
| Installed from | `requirements-verify.txt` only |
| CPU limit | one core (`taskset -c 3`) at nice 19, because a timing-sensitive campaign was running on the same host |

## Commands

```bash
cd <scratch>/clean-verify
git clone --branch i21-depot <origin-url> repo           # 13 s
python3 -m venv venv && . venv/bin/activate
cd repo && pip install -r requirements-verify.txt        # 10 s
make verify NICE="nice -n 19 taskset -c 3"               # equivalent to prefixing the command as run
```

The run was started as `nice -n 19 taskset -c 3 make verify`; the Makefile's own `nice -n 19` then applied to every step as well (the same CPU set is inherited).

## Output (tail of `make verify`, one line abridged)

```
differential: {'plan': 1500, 'station': 1500, 'p2': 1500, 'p2_noassert': 1500, 'credit': 1500, 'loop': 1500} total 9000
code mutants: 11 of 11 'sat' as expected
114/114 checks as expected; mutants (model): plan=6/6, station=5/5, loop=2/2; 239.846 s
queries 114 (committed 114), unsat 99, solver 239.8 s, z3 5.3.1
differential cases 9000, code mutants 11
VERIFY_OK: every verdict equals the committed record
90 passed in 312.07s (0:05:12)
```

| Step | Wall time |
|---|---|
| z3 proofs + differential + mutants (`verify_advice_smt.py`) | about 4 min (solver 239.8 s) |
| `verify_compare.py` | seconds |
| pytest (3 files) | 312.07 s |
| **`make verify` total** | **553 s (9 min 13 s)** on one core |

`docs/REPRODUCE.md` section 3 reports 8 min 46 s on the author's host; the single-core pin explains the extra 27 s. Verdicts are identical to the committed record
(`experiments/results/smt_advice_proof.json`). `git status` in the clone was clean afterwards.

## Problems found in the guide, and fixes

No failure; no missing file; no author-machine path was needed. Documentation and Makefile gaps, fixed in the same commit:

1. `docs/REPRODUCE.md` did not say how to limit CPU on a busy host. The `NICE` Make variable (default `nice -n 19`) is the hook; the guide now shows `make verify NICE="nice -n 19 taskset -c 3"` and its single-core time.
2. The guide did not say that the venv has to be active in the shell running `make` (the Makefile calls plain `python3`). Now stated.
3. The Makefile wrote its fresh result files to hard-coded `/tmp/rescuemind_smt_{fresh,quick}.json`, which collide between concurrent runs or users on a shared host
   (an old file from a previous run was in fact present and was overwritten). New Make variable `SMT_TMP` (default `/tmp`, so behaviour is unchanged); documented.

Not exercised here: `make numbers`, `make check`, `make test`, `make verify-quick` as separate targets (`docs/REPRODUCE.md` section 9 records them on the reference host).
