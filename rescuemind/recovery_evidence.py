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


def audit_recovery(mission: dict, run_dir: Path, *, completed: bool) -> dict:
    rec = mission.get('recovery')
    if not isinstance(rec, dict):
        raise RecoveryEvidenceError('no recovery block')
    item = mission.get('intent', {}).get('item')
    first, searched = rec.get('first_station'), rec.get('searched_station')
    if {first, searched} != {'water', 'medicine'}:
        raise RecoveryEvidenceError('recovery must visit both distinct stations')
    if mission.get('checkpoint_station') != searched:
        raise RecoveryEvidenceError('final checkpoint is not at the searched station')
    cp = rec.get('first_checkpoint') or {}
    dec = cp.get('decision') or {}
    if dec.get('allow') is not False or dec.get('reason') != 'local_vlm_disagree_or_wrong_supply' or dec.get('expected') != item:
        raise RecoveryEvidenceError('first checkpoint was not a wrong/missing-supply denial for the same request')
    events = mission.get('events') or []
    order = [e.get('stage') for e in events]
    need = ['recovery_supply_station', 'recovery_checkpoint_frame', 'recovery_checkpoint_decision',
            'recovery_checkpoint_denial_dwell_finished', 'recovery_search_started', 'supply_station',
            'checkpoint_frame', 'checkpoint_decision']
    try:
        idx = [order.index(n) for n in need]
    except ValueError as exc:
        raise RecoveryEvidenceError(f'missing recovery event: {exc}') from exc
    if idx != sorted(idx):
        raise RecoveryEvidenceError('recovery events out of order')
    times = [events[i].get('t_wall_s') for i in idx]
    if any(not isinstance(t, (int, float)) for t in times) or times != sorted(times):
        raise RecoveryEvidenceError('recovery event times not monotonic')
    frame = events[idx[1]]
    image = Path(run_dir) / rec.get('first_checkpoint_image', '')
    if not image.is_file() or hashlib.sha256(image.read_bytes()).hexdigest() != frame.get('image_sha256'):
        raise RecoveryEvidenceError('first checkpoint image missing or hash mismatch')
    from .local_run_audit import audit_local_checkpoint
    audit_local_checkpoint(cp, frame['image_sha256'], expected=item)
    final = (mission.get('checkpoint') or {}).get('decision') or {}
    if completed and final.get('allow') is not True:
        raise RecoveryEvidenceError('completed recovery without an allow at the searched station')
    return {'pass': True, 'first_station': first, 'searched_station': searched,
            'first_reason': dec['reason'], 'first_supplies': [dec.get('first_supply'), dec.get('second_supply')],
            'final_allow': final.get('allow'), 'search_started_t': times[4], 'final_decision_t': times[7]}
