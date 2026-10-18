#!/usr/bin/env python3
"""Pre-flight guard against a stale ledger (docs/PREFLIGHT_2026-10-18.md).

`scripts/run_campaign.py` skips every trial that already has a final row in the ledger, whatever stack arguments that row was run
with.  After an Amendment that changes the stack (study A: the intent prompt i38 instead of i35) a ledger left over from the
earlier run would therefore be reused silently and the amended protocol would never run.  This check compares, for every trial
of the protocol that has a row in the ledger, the stack arguments the row recorded with the ones the protocol asks for now
(`common_stack_args` + the trial's own `stack_args`, exactly as run_campaign.py composes them) and fails on any difference.

  python3 scripts/ledger_stack_check.py --protocol experiments/campaign_a_pilot_protocol.json \\
      --ledger experiments/results/campaign_A_pilot_ledger.jsonl
  exit 0: no ledger, or every row matches;  exit 1: mismatch (the rows are listed; move the old ledger aside, e.g. to
  campaign_A_pilot1_ledger.jsonl, and run again).
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def mismatches(protocol: dict, rows: list) -> list:
    """[(trial_id, recorded stack args, expected stack args)] for the rows whose stack arguments differ from the protocol's."""
    common = list(protocol.get('common_stack_args') or [])
    trials = {t['id']: t for t in protocol['trials']}
    bad, seen = [], set()
    for r in rows:
        t = trials.get(r.get('trial_id'))
        if t is None:
            continue
        want = common + list(t.get('stack_args') or [])
        got = list(r.get('stack_args') or [])
        if got != want and (r['trial_id'], json.dumps(got)) not in seen:
            seen.add((r['trial_id'], json.dumps(got)))
            bad.append((r['trial_id'], got, want))
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--protocol', required=True)
    ap.add_argument('--ledger', required=True)
    a = ap.parse_args(argv)
    ledger = Path(a.ledger)
    if not ledger.is_file():
        return 0
    protocol = json.loads(Path(a.protocol).read_text(encoding='utf8'))
    rows = [json.loads(x) for x in ledger.read_text(encoding='utf8').splitlines() if x.strip()]
    bad = mismatches(protocol, rows)
    if bad:
        print(f'{len(bad)} ledger row(s) in {ledger.name} were run with other stack arguments than {Path(a.protocol).name} asks for now '
              f'(first: {bad[0][0]}: recorded {bad[0][1]}, wanted {bad[0][2]}).', file=sys.stderr)
        print('The ledger is from before an Amendment: run_campaign.py would skip these trials. Move it aside '
              f'(mv {ledger} <name>_old.jsonl) and run again.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
