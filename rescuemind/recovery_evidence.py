"""I-02: audit a recovery search (requested supply missing/wrong at the first station).

A recovery is legitimate only if:
  * the FIRST checkpoint really denied for 'wrong/missing supply' (recomputed from the
    saved model outputs and the saved JPEG hash) — never for a hazard or low confidence;
  * the robot held still for the denial dwell, then started the search, and only then
    reached the other station, where a NEW checkpoint decided;
  * the second station is the other one, and the request (supply) did not change.
The final checkpoint itself is audited by the normal completion / denial audits.
"""
from __future__ import annotations
import hashlib
from pathlib import Path


class RecoveryEvidenceError(ValueError):
    pass


def _nth(order: list, name: str, n: int) -> int:
    """Index of the n-th (0-based) event called `name`."""
    seen = -1
    for i, stage in enumerate(order):
        if stage == name:
            seen += 1
            if seen == n:
                return i
    raise ValueError(f'event {name} #{n + 1} not found')


def audit_recovery(mission: dict, run_dir: Path, *, completed: bool) -> dict:
    """I-02 (two stations) and I-21 (k stations): a recovery is a chain of hops.  Hop 0 is `first_checkpoint`, hop j >= 1
    is `hops[j-1]`; every hop must be a wrong/missing-supply denial; the stations visited (hops, then the searched
    station whose checkpoint is the final one) must be a PREFIX of the recorded candidate order: no skipped candidate,
    no repeat.  Records without 'candidates' (the arena) must visit both of water / medicine."""
    rec = mission.get('recovery')
    if not isinstance(rec, dict):
        raise RecoveryEvidenceError('no recovery block')
    item = mission.get('intent', {}).get('item')
    first, searched = rec.get('first_station'), rec.get('searched_station')
    hops = rec.get('hops') or []
    denied = [first] + [h.get('station') for h in hops]
    visited = denied + [searched]
    cands = rec.get('candidates')
    if cands is None:
        if {first, searched} != {'water', 'medicine'} or hops:
            raise RecoveryEvidenceError('recovery must visit both distinct stations')
    else:
        from .stations import validate_visits
        try:
            validate_visits(cands, visited)
        except ValueError as exc:
            raise RecoveryEvidenceError(str(exc)) from exc
        if len(set(cands)) != len(cands):
            raise RecoveryEvidenceError('candidate order has a repeated station')
    if mission.get('checkpoint_station') != searched:
        raise RecoveryEvidenceError('final checkpoint is not at the searched station')
    checkpoints = [(rec.get('first_checkpoint') or {}, rec.get('first_checkpoint_image', ''))] + [
        (h.get('checkpoint') or {}, h.get('checkpoint_image', '')) for h in hops]
    kinds = [rec.get('first_kind')] + [h.get('kind') for h in hops]
    soft_ok = mission.get('caution_soft') is True          # R5 #5: soft hops exist only under --caution-soft
    for j, (cp, _) in enumerate(checkpoints):
        dec = cp.get('decision') or {}
        if kinds[j] == 'caution_only':
            # a caution-only refusal; whether it really was one (no hazard under the standard rule) is recomputed below
            if not soft_ok or dec.get('allow') is not False or dec.get('reason') != 'visible_hazard_at_checkpoint' or dec.get('expected') != item:
                raise RecoveryEvidenceError(f'hop {j + 1} is a soft refusal without --caution-soft or not a refusal for the same request')
            continue
        if kinds[j] is not None:
            raise RecoveryEvidenceError(f'unknown hop kind {kinds[j]!r}')
        if dec.get('allow') is not False or dec.get('reason') != 'local_vlm_disagree_or_wrong_supply' or dec.get('expected') != item:
            raise RecoveryEvidenceError('first checkpoint was not a wrong/missing-supply denial for the same request' if j == 0 else
                                        f'checkpoint of hop {j + 1} was not a wrong/missing-supply denial for the same request')
    events = mission.get('events') or []
    order = [e.get('stage') for e in events]
    hop_events = ['recovery_supply_station', 'recovery_checkpoint_frame', 'recovery_checkpoint_decision',
                  'recovery_checkpoint_denial_dwell_finished', 'recovery_search_started']
    final_events = ['supply_station', 'checkpoint_frame', 'checkpoint_decision']
    try:
        idx = [_nth(order, n, j) for j in range(len(checkpoints)) for n in hop_events]
        idx += [order.index(n) for n in final_events]
    except ValueError as exc:
        raise RecoveryEvidenceError(f'missing recovery event: {exc}') from exc
    if order.count('recovery_search_started') != len(checkpoints):
        raise RecoveryEvidenceError('number of recovery searches does not match the hops')
    if idx != sorted(idx):
        raise RecoveryEvidenceError('recovery events out of order')
    times = [events[i].get('t_wall_s') for i in idx]
    if any(not isinstance(t, (int, float)) for t in times) or times != sorted(times):
        raise RecoveryEvidenceError('recovery event times not monotonic')
    from .local_run_audit import audit_local_checkpoint
    for j, (cp, name) in enumerate(checkpoints):
        frame = events[idx[j * 5 + 1]]
        image = Path(run_dir) / name
        if not image.is_file() or hashlib.sha256(image.read_bytes()).hexdigest() != frame.get('image_sha256'):
            raise RecoveryEvidenceError('first checkpoint image missing or hash mismatch' if j == 0
                                        else f'checkpoint image of hop {j + 1} missing or hash mismatch')
        res = audit_local_checkpoint(cp, frame['image_sha256'], expected=item)
        if kinds[j] == 'caution_only' and not res.get('caution_only'):
            raise RecoveryEvidenceError(f'hop {j + 1} was continued as a caution-only refusal, but the saved outputs show a real hazard')
    from .caution_soft import audit_caution_refusals, CautionError
    try:
        caution = audit_caution_refusals(mission)
    except CautionError as exc:
        raise RecoveryEvidenceError(str(exc)) from exc
    final = (mission.get('checkpoint') or {}).get('decision') or {}
    if completed and final.get('allow') is not True:
        raise RecoveryEvidenceError('completed recovery without an allow at the searched station')
    n = len(checkpoints)
    out = {'pass': True, 'first_station': first, 'searched_station': searched,
           'first_reason': checkpoints[0][0]['decision']['reason'],
           'first_supplies': [checkpoints[0][0]['decision'].get('first_supply'), checkpoints[0][0]['decision'].get('second_supply')],
           'final_allow': final.get('allow'), 'search_started_t': times[4], 'final_decision_t': times[n * 5 + 2]}
    if caution['n_caution_refusals']:
        out['caution'] = caution
    if cands is not None:
        out.update({'candidates': list(cands), 'visited': visited, 'n_checks': len(visited)})
    return out
