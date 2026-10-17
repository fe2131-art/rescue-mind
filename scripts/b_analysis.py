#!/usr/bin/env python3
"""Study B analysis exactly as pre-registered (experiments/PREREGISTRATION_B.md).

  python3 scripts/b_analysis.py            # -> experiments/results/b_summary.json
  python3 scripts/b_analysis.py --pilot    # mechanics pilot check (exit 1 unless every run behaved as registered)

Reads the run ledger (run_campaign.py) and, per run, outputs/runs/<run_id>/mission.json.  The credit settlements are
RECOMPUTED offline from mission.json with advice_credit.visits_from_mission / settle, replayed over each sequence from a
fresh ledger, and compared with the plan's credit snapshot and with the ledger file the orchestrator kept.
Ground truth (scene) is used only here: the station that holds the requested supply is its own (catalog) station in a
nominal scene and the other station in a swapped scene.  A wasted visit is a visit to the other station of a liar (a
station that does not hold the supply).

  B1 liar, wasted visits per sequence: m without credit, exactly C_LOC with credit; missions C_LOC+1..m throttled with the
     first station = catalog.  (Secondary: the Proposition 3 bound, wasted <= C_LOC + RHO_SHADOW m.)
  B2 honest: no throttling, the advised station first, identical visit counts in both arms, 0 wasted visits.
  B3 every run passes advice_audit (incl. audit_credit), 0 unsafe deliveries, ledger settlements = offline recomputation.
  B4 (descriptive) time saved per liar sequence by credit vs 4 x W.
Sequences with a missing or FAILED run are dropped from B1/B2/B4 and listed (B3 still covers every run that exists).
"""
from __future__ import annotations
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind import advice_credit as ac  # noqa: E402

RES = ROOT / 'experiments/results'
DELIVERED = ('ALLOW', 'ALLOW_AFTER_SEARCH', 'ALLOW_MEMORY', 'ALLOW_ADVICE')
OTHER = {'water': 'medicine', 'medicine': 'water'}


def med(v):
    return statistics.median(v) if v else None


def read_ledger(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding='utf8').splitlines() if x.strip()]


def read_mission(runs_dir: Path, run_id) -> dict | None:
    if not run_id:
        return None
    try:
        return json.loads((runs_dir / run_id / 'mission.json').read_text(encoding='utf8'))
    except (OSError, ValueError):
        return None


def audit_run(runs_dir: Path, run_id: str, mission: dict) -> dict:
    """The orchestrator's advice_audit (monotone audit + audit_credit), recomputed from mission.json."""
    try:
        from scripts import v32_orchestrate as orch
        ev = orch.advice_audit(runs_dir / run_id)
    except Exception as exc:               # AdviceError, CreditError, ValueError ...
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    if ev is None:
        return {'ok': False, 'error': 'no advice record in mission.json'}
    return {'ok': True, 'credit_checked': bool((ev.get('credit') or {}).get('checked'))}


def run_record(trial: dict, row: dict, runs_dir: Path) -> dict:
    item = trial['expected']
    holder = item if trial['scene'] == 'nominal' else OTHER[item]
    obs = row.get('observed_action')
    rec = {'trial_id': trial['id'], 'sequence': trial['sequence'], 'k': trial['mission_index'], 'arm': trial['config'],
           'condition': trial['condition'], 'run_id': row.get('run_id'), 'observed': obs, 'state': row.get('state'),
           'failed': obs == 'FAILED', 'mission_time_s': row.get('mission_time_s'), 'holder': holder,
           'expected_first_station': trial['expected_first_station'], 'expected_wasted_visits': trial['expected_wasted_visits'],
           'expected_throttled': trial['expected_throttled'], 'expected_action': trial['expected_action'],
           'delivered': obs in DELIVERED,
           'unsafe_delivery': obs in DELIVERED and row.get('final_station') != holder}
    il = row.get('interlock_audit')
    rec['interlock_permits'] = il.get('permits') if isinstance(il, dict) else None       # I-22 (Amendment 2, B5)
    m = read_mission(runs_dir, row.get('run_id'))
    rec['mission_json'] = m is not None
    if m is None:
        rec['first_station'] = row.get('first_station_planned')
        return rec
    plan = m.get('memory') or {}
    advice = plan.get('advice') or {}
    visits = ac.visits_from_mission(m)
    rec.update(first_station=plan.get('first_station'), visited=[v['station'] for v in visits],
               n_visits=len(visits), wasted_visits=sum(v['station'] != holder for v in visits),
               n_throttled=len(advice.get('throttled') or []),
               n_applied_reorder=sum(a.get('effect') == 'reorder' for a in advice.get('applied') or []),
               credit_snapshot=advice.get('credit'))
    rec['audit'] = audit_run(runs_dir, row['run_id'], m)
    rec['_mission'] = m
    return rec


def as_registered(r: dict) -> bool:
    return (r['mission_json'] and not r['failed'] and r['first_station'] == r['expected_first_station']
            and r['wasted_visits'] == r['expected_wasted_visits'] and r['n_throttled'] >= r['expected_throttled']
            and (r['n_throttled'] == 0 or r['expected_throttled'] > 0) and r['observed'] == r['expected_action'])


def replay_credit(recs: list[dict], ledger_path: Path | None) -> dict:
    """Replay the settlements of one credit-arm sequence offline and compare with the plan snapshots and the ledger file."""
    recs = sorted(recs, key=lambda r: r['k'])
    if not recs or any(not r['mission_json'] for r in recs) or [r['k'] for r in recs] != list(range(1, len(recs) + 1)):
        return {'checked': False, 'why': 'incomplete chain of missions'}
    led, problems, charges = ac.new_ledger(), [], {}
    p = led['params']
    for r in recs:
        m = r['_mission']
        plan = m.get('memory') or {}
        snap = (plan.get('advice') or {}).get('credit')
        if snap is not None:
            for key, got in snap.items():
                want = led['sources'].get(key) or {'loc': p['c_loc'], 'haz': p['c_haz']}
                if abs(got['loc'] - want['loc']) > 1e-3 or abs(got['haz'] - want['haz']) > 1e-3:
                    problems.append(f"mission {r['k']}: plan credit snapshot {key} {got} != offline {want}")
        charges[r['run_id']] = ac.settle(led, plan, ac.visits_from_mission(m), mission_id=r['run_id'])['charges']
    out = {'checked': True, 'offline_credit': {k: {'loc': v['loc'], 'haz': v['haz']} for k, v in led['sources'].items()},
           'offline_charges': [c for r in recs for c in charges[r['run_id']]]}
    if ledger_path is None or not Path(ledger_path).is_file():
        problems.append('ledger file missing')
    else:
        try:
            kept = json.loads(Path(ledger_path).read_text(encoding='utf8'))
            ac._check(kept)
        except Exception as exc:
            kept = None
            problems.append(f'ledger file unreadable: {exc}')
        if kept is not None:
            by_id = {h.get('mission'): h for h in kept.get('history') or []}
            for r in recs:
                h = by_id.get(r['run_id'])
                if h is None:
                    problems.append(f"mission {r['k']}: no settlement in the ledger file")
                elif h.get('charges') != charges[r['run_id']]:
                    problems.append(f"mission {r['k']}: ledger charges {h.get('charges')} != offline {charges[r['run_id']]}")
            extra = len(kept.get('history') or []) - len(recs)
            out['extra_settlements_in_file'] = extra          # settled attempts of runs that were retried (no visits, no charge)
            if extra == 0:
                for key, acc in led['sources'].items():
                    got = (kept['sources'].get(key) or {})
                    if abs(got.get('loc', -1) - acc['loc']) > 1e-6 or abs(got.get('haz', -1) - acc['haz']) > 1e-6:
                        problems.append(f"final credit of {key}: file {got.get('loc')}/{got.get('haz')} != offline {acc['loc']}/{acc['haz']}")
            elif kept['sources'].get('file') and abs(kept['sources']['file']['loc'] - led['sources'].get('file', {}).get('loc', -1)) > 1e-6:
                problems.append('final location credit of peer differs although the extra settlements carry no charge')
    out['problems'] = problems
    out['ok'] = not problems
    return out


def sequence_table(recs: list[dict]) -> dict:
    by = defaultdict(dict)
    for r in recs:
        by[r['arm']][r['k']] = r
    return by


def analyse(proto: dict, rows: list[dict], runs_dir: Path, root: Path = ROOT) -> dict:
    trials = {t['id']: t for t in proto['trials']}
    final = {r['trial_id']: r for r in rows if r.get('final', True) and r['trial_id'] in trials}
    recs = [run_record(trials[tid], row, runs_dir) for tid, row in sorted(final.items())]
    missing = sorted(set(trials) - set(final))
    m_missions, c_loc = proto['m'], proto.get('c_loc', ac.C_LOC)
    bysq = defaultdict(list)
    for r in recs:
        bysq[r['sequence']].append(r)
    seqs, dropped = {}, {}
    for seq, info in proto['sequences'].items():
        want = {t['id'] for t in proto['trials'] if t['sequence'] == seq}
        have = [r for r in bysq[seq] if r['trial_id'] in want]
        bad = sorted(want - {r['trial_id'] for r in have}) + [r['trial_id'] for r in have if r['failed'] or not r['mission_json']]
        if bad:
            dropped[seq] = {'missing_or_failed': sorted(bad)}
            continue
        seqs[seq] = (info, sequence_table(have), have)
    out = {'registered': 'experiments/PREREGISTRATION_B.md', 'n_planned': len(trials), 'n_runs': len(recs), 'missing_runs': missing,
           'sequences_dropped': dropped, 'm': m_missions, 'c_loc': c_loc}
    # B1 / B2 -- per sequence
    b1, b2, per_seq = {}, {}, {}
    for seq, (info, tab, have) in seqs.items():
        per_seq[seq] = {arm: {'wasted_per_mission': [tab[arm][k]['wasted_visits'] for k in sorted(tab[arm])],
                              'wasted_total': sum(tab[arm][k]['wasted_visits'] for k in tab[arm]),
                              'first_station': [tab[arm][k]['first_station'] for k in sorted(tab[arm])],
                              'throttled': [tab[arm][k]['n_throttled'] for k in sorted(tab[arm])],
                              'visits': [tab[arm][k]['n_visits'] for k in sorted(tab[arm])],
                              'mission_time_s': [tab[arm][k]['mission_time_s'] for k in sorted(tab[arm])]} for arm in tab}
        ok = all(as_registered(r) for r in have)
        if info['condition'] == 'liar':
            nc, cr = per_seq[seq]['nocredit']['wasted_total'], per_seq[seq]['credit']['wasted_total']
            bound = int(c_loc + ac.RHO_SHADOW * m_missions + 1e-9)
            b1[seq] = {'wasted_nocredit': nc, 'wasted_credit': cr, 'as_registered': ok,
                       'exact': nc == m_missions and cr == int(c_loc), 'within_prop3_bound': cr <= bound, 'prop3_bound': bound}
        else:
            same = all(tab['nocredit'][k]['n_visits'] == tab['credit'][k]['n_visits']
                       and tab['nocredit'][k]['first_station'] == tab['credit'][k]['first_station'] for k in tab['credit'])
            b2[seq] = {'as_registered': ok, 'no_throttling': all(r['n_throttled'] == 0 for r in have),
                       'identical_in_both_arms': same, 'wasted': sum(r['wasted_visits'] for r in have)}
    out['per_sequence'] = per_seq
    out['B1_liar'] = {'sequences': b1, 'n_complete': len(b1),
                      'supported': len(b1) >= 2 and all(v['as_registered'] and v['exact'] for v in b1.values()),
                      'bound_held': all(v['within_prop3_bound'] for v in b1.values()) if b1 else None}
    out['B2_honest'] = {'sequences': b2, 'n_complete': len(b2),
                        'supported': len(b2) >= 1 and all(v['as_registered'] and v['no_throttling'] and v['identical_in_both_arms']
                                                          and v['wasted'] == 0 for v in b2.values())}
    # B3 -- every existing run, complete sequences or not
    audits = [{'trial_id': r['trial_id'], **r['audit']} for r in recs if 'audit' in r]
    replays = {}
    for seq, info in proto['sequences'].items():
        cr = [r for r in bysq.get(seq, []) if r['arm'] == 'credit']
        tr = next((t for t in proto['trials'] if t['sequence'] == seq and t['config'] == 'credit'), None)
        led_path = (Path(root) / tr['advice_credit']['file']) if tr else None
        replays[seq] = replay_credit(cr, led_path)
    unsafe = [r['trial_id'] for r in recs if r['unsafe_delivery']]
    audit_fail = [a['trial_id'] for a in audits if not a['ok']]
    no_json = [r['trial_id'] for r in recs if not r['mission_json'] and not r['failed']]
    unchecked_credit = [r['trial_id'] for r in recs if 'audit' in r and r['arm'] == 'credit'
                        and r['audit']['ok'] and not r['audit']['credit_checked']]
    out['B3_audits'] = {'runs_audited': len(audits), 'audit_failures': audit_fail, 'runs_without_mission_json': no_json,
                        'credit_arm_runs_without_credit_audit': unchecked_credit, 'unsafe_deliveries': unsafe,
                        'ledger_replay': replays,
                        'ledger_replay_failures': [s for s, v in replays.items() if v['checked'] and not v['ok']],
                        'supported': bool(audits) and not audit_fail and not no_json and not unchecked_credit and not unsafe
                        and all(v['ok'] for v in replays.values() if v['checked']) and any(v['checked'] for v in replays.values())}
    # B4 -- descriptive time saved by credit on the liar
    lseq = [s for s in b1]
    first = [r['mission_time_s'] for s in lseq for r in seqs[s][2] if r['k'] <= int(c_loc) and r['mission_time_s'] is not None]
    later_c = [r['mission_time_s'] for s in lseq for r in seqs[s][2] if r['k'] > int(c_loc) and r['arm'] == 'credit'
               and r['mission_time_s'] is not None]
    w = (med(first) - med(later_c)) if first and later_c else None
    saved = {}
    for s in lseq:
        tab = seqs[s][1]
        d = [tab['nocredit'][k]['mission_time_s'] - tab['credit'][k]['mission_time_s'] for k in range(int(c_loc) + 1, m_missions + 1)
             if tab['nocredit'][k]['mission_time_s'] is not None and tab['credit'][k]['mission_time_s'] is not None]
        saved[s] = round(sum(d), 1) if len(d) == m_missions - int(c_loc) else None
    pred = None if w is None else round(w * (m_missions - int(c_loc)), 1)
    got = [v for v in saved.values() if v is not None]
    out['B4_time_descriptive'] = {'W_s': None if w is None else round(w, 1), 'predicted_saving_per_sequence_s': pred,
                                  'saving_per_sequence_s': saved, 'median_saving_s': med(got),
                                  'median_time_nocredit_s': med([r['mission_time_s'] for s in lseq for r in seqs[s][2]
                                                                 if r['arm'] == 'nocredit' and r['mission_time_s'] is not None]),
                                  'median_time_credit_throttled_missions_s': med(later_c)}
    # B5 (Amendment 2): with the delivery interlock on, a delivered run has exactly one permit and a refused run none
    if '--delivery-interlock' in (proto.get('common_stack_args') or []):
        done = [r for r in recs if not r['failed']]
        bad5 = [r['trial_id'] for r in done
                if r['interlock_permits'] is None or r['interlock_permits'] != (1 if r['delivered'] else 0)]
        out['B5_interlock'] = {'runs': len(done), 'violations': bad5, 'supported': bool(done) and not bad5}
    out['headline_supported'] = bool(out['B1_liar']['supported'] and out['B2_honest']['supported'] and out['B3_audits']['supported'])
    out['trials'] = [{k: v for k, v in r.items() if not k.startswith('_')} for r in recs]
    return out


def pilot_check(proto: dict, rows: list[dict], runs_dir: Path, root: Path = ROOT) -> dict:
    """Mechanics pilot: every run present, none failed, each as registered (first station, wasted visits, throttling,
    outcome), every audit passes, no unsafe delivery, and the credit settlements equal the offline recomputation."""
    s = analyse(proto, rows, runs_dir, root)
    bad = [r['trial_id'] for r in s['trials'] if not as_registered_dict(r)]
    replay_ok = all(v['ok'] for v in s['B3_audits']['ledger_replay'].values() if v['checked'])
    replay_any = any(v['checked'] for v in s['B3_audits']['ledger_replay'].values())
    ok = (not s['missing_runs'] and not s['sequences_dropped'] and not bad and not s['B3_audits']['audit_failures']
          and not s['B3_audits']['unsafe_deliveries'] and not s['B3_audits']['credit_arm_runs_without_credit_audit']
          and replay_ok and replay_any)
    return {'ok': ok, 'not_as_registered': bad, 'missing_runs': s['missing_runs'], 'sequences_dropped': s['sequences_dropped'],
            'audit_failures': s['B3_audits']['audit_failures'], 'unsafe_deliveries': s['B3_audits']['unsafe_deliveries'],
            'ledger_replay_ok': replay_ok and replay_any}


def as_registered_dict(r: dict) -> bool:
    return bool(r.get('mission_json')) and as_registered(dict(r))


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--protocol', default=None)
    ap.add_argument('--ledger', default=None)
    ap.add_argument('--runs-dir', default=str(ROOT / 'outputs/runs'))
    ap.add_argument('--root', default=str(ROOT), help='repository root the ledger files of the protocol are relative to')
    ap.add_argument('--out', default=str(RES / 'b_summary.json'))
    a = ap.parse_args(argv)
    proto_p = a.protocol or str(ROOT / ('experiments/campaign_b_pilot_protocol.json' if a.pilot else 'experiments/campaign_b_protocol.json'))
    led_p = Path(a.ledger or RES / ('campaign_B_pilot_ledger.jsonl' if a.pilot else 'campaign_B_ledger.jsonl'))
    proto = json.loads(Path(proto_p).read_text(encoding='utf8'))
    rows = read_ledger(led_p)
    if a.pilot:
        res = pilot_check(proto, rows, Path(a.runs_dir), Path(a.root))
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0 if res['ok'] else 1
    out = analyse(proto, rows, Path(a.runs_dir), Path(a.root))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    print(json.dumps({k: v for k, v in out.items() if k not in ('trials', 'per_sequence')}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
