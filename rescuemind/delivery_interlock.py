"""I-22: delivery interlock, pure logic (no ROS).

Recomputes the station decision from the SAVED model outputs in an approval record, with the run audit's own functions
(`local_run_audit.audit_local_checkpoint`, `advice.audit_plan` / `assert_monotone` / `audit_scrutiny`), not with the
mission node's code path, and issues a time-limited permit only if everything holds:

  1. the saved images exist and hash to what the model calls and the look-around entries say they were run on;
  2. the recomputed decision (two passes, optional Jev role, memory/advice caution, side views, adaptive views) is
     'approve' and equals the decision in the record;
  3. the applied plan relaxes nothing (no skipped check, no refusal-without-visit, monotone w.r.t. its pre-advice base,
     scrutiny station carried caution and the three extra views), and the caution of the delivering station really was
     applied to the checkpoint;
  4. the views that the interlock's policy (or the record's own configuration, which can only ADD requirements) asks for
     were taken: side views L and R, and the adaptive block.

Anything else, including any exception, is a denial (fail-closed).  The guard (`delivery_permit.PermitGate`) then keeps
the robot still during the delivery leg without a permit.
"""
from __future__ import annotations
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from . import delivery_permit as dp
from .advice import AdviceError, audit_plan, assert_monotone, audit_scrutiny, _tau
from .local_run_audit import LocalReceiptError, audit_local_checkpoint
from .mission_memory import STATIONS

RULE_VERSION = 'v3.6'


@dataclass(frozen=True)
class Policy:
    """Requirements fixed when the interlock starts (independent of what the record says about itself)."""
    require_look_around: bool = False
    require_adaptive: bool = False
    image_root: str | None = None        # if set, the record's image directory must lie inside it


@dataclass
class Decision:
    permit: bool
    reason: str
    record_hash: str = ''
    run_id: str = ''
    station: str = ''
    checks: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {'permit': self.permit, 'reason': self.reason, 'record_hash': self.record_hash, 'run_id': self.run_id,
                'station': self.station, 'checks': list(self.checks), 'rule_version': RULE_VERSION}


def sha256_file(path) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


class _Deny(Exception):
    pass


def _need(cond, reason):
    if not cond:
        raise _Deny(reason)


def _image_path(images: dict, name, policy: Policy) -> Path:
    _need(isinstance(name, str) and name and '/' not in name and '\\' not in name and name not in ('.', '..'), 'bad_image_name')
    d = images.get('dir')
    _need(isinstance(d, str) and d, 'bad_image_dir')
    d = Path(d).resolve()
    if policy.image_root is not None:
        _need(d.is_relative_to(Path(policy.image_root).resolve()), 'image_dir_outside_root')
    return d / name


def decide(raw, policy: Policy = Policy(), file_sha=sha256_file) -> Decision:
    """Decide on the raw approval-record text.  Never raises."""
    rh = dp.record_hash(raw) if isinstance(raw, str) else ''
    out = Decision(False, 'unprocessed', rh)
    try:
        _need(isinstance(raw, str) and len(raw) <= dp.MAX_RECORD_BYTES, 'record_too_large_or_not_text')
        rec = json.loads(raw)
        _need(isinstance(rec, dict) and rec.get('v') == dp.RECORD_VERSION, 'malformed_record')
        run_id, station, expected = rec.get('run_id'), rec.get('station'), rec.get('expected')
        out.run_id, out.station = str(run_id), str(station)
        _need(isinstance(run_id, str) and run_id and isinstance(station, str) and station, 'malformed_record')
        _need(expected in ('water', 'medicine'), 'bad_expected_item')
        cp, plan = rec.get('checkpoint'), rec.get('plan')
        _need(isinstance(cp, dict), 'no_checkpoint')
        _need(plan is None or isinstance(plan, dict), 'malformed_plan')
        plan = plan or {}
        blk = rec.get('stations')
        ids = tuple(blk['ids']) if isinstance(blk, dict) and isinstance(blk.get('ids'), list) else (
            tuple(plan['order']) if plan.get('order') else STATIONS)
        _need(station in ids, 'unknown_station')
        out.checks.append('record_wellformed')

        # --- the plan relaxes nothing -------------------------------------------------------------------------
        _need(not plan.get('skip_check') and not plan.get('deny_without_visit'), 'plan_skips_or_refuses_without_visit')
        adv = plan.get('advice')
        try:
            audit_plan(plan)
            if adv and adv.get('mode') != 'monotone':
                assert_monotone(adv.get('base') or {}, plan)       # also for naive / filtered: the effects must be monotone
            audit_scrutiny({'memory': plan, 'advice_scrutiny': rec.get('advice_scrutiny'), 'checkpoint': cp,
                            'checkpoint_station': station, 'look_around': cp.get('look_around')})
        except AdviceError as e:
            raise _Deny('plan: ' + str(e))
        caution = (plan.get('caution') or {}).get(station)
        if caution:     # the plan's caution for the delivering station must really have been applied to the checkpoint
            tau_plan, tau_cp = _tau(caution), cp.get('memory_caution_tau_h')
            _need(isinstance(tau_cp, float) and 0 < tau_cp <= tau_plan + 1e-12, 'plan_caution_not_applied')
        out.checks.append('plan_monotone')

        # --- images and recomputed decision -------------------------------------------------------------------
        images = rec.get('images')
        _need(isinstance(images, dict), 'no_images')
        front_sha = file_sha(_image_path(images, images.get('front'), policy))
        _need(front_sha is not None, 'front_image_missing')
        la = cp.get('look_around')
        peeks = (la or {}).get('peeks') or [] if isinstance(la, dict) else []
        for pk in peeks:
            sha = file_sha(_image_path(images, pk.get('image'), policy))
            _need(sha is not None, 'side_image_missing')
            _need(sha == pk.get('image_sha256'), 'side_image_hash_mismatch')
        out.checks.append('image_hashes')
        try:
            audit = audit_local_checkpoint(cp, front_sha, expected=expected)
        except (LocalReceiptError, KeyError, TypeError, ValueError, AttributeError) as e:
            raise _Deny('recompute: ' + str(e))
        _need(audit.get('allow') is True, 'recomputed_decision_is_' + str(audit.get('reason')))
        out.checks.append('recomputed_approve')

        # --- the views that were required were taken ----------------------------------------------------------
        cfg = rec.get('config') if isinstance(rec.get('config'), dict) else {}
        need_la = policy.require_look_around or _pos(cfg.get('look_around'))
        need_ad = policy.require_adaptive or _pos(cfg.get('adaptive_views'))
        if need_la or need_ad:
            _need(isinstance(la, dict) and la.get('station') == station, 'look_around_missing')
            _need({'L', 'R'} <= {pk.get('side') for pk in peeks}, 'standard_side_views_missing')
        if need_ad:
            _need(isinstance(la.get('adaptive'), dict), 'adaptive_views_missing')
        out.checks.append('required_views')
        out.permit, out.reason = True, 'approved'
    except _Deny as e:
        out.permit, out.reason = False, str(e)
    except Exception as e:          # fail closed on anything unexpected
        out.permit, out.reason = False, f'interlock_error: {type(e).__name__}: {e}'
    return out


def _pos(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0


class Interlock:
    """Stateful wrapper used by the ROS node (and by the pure message-flow simulation in the tests)."""

    def __init__(self, policy: Policy = Policy(), key: bytes | None = None, ttl_s: float = 4.0, max_life_s: float = 240.0,
                 file_sha=sha256_file):
        self.policy, self.key, self.ttl_s, self.max_life_s, self.file_sha = policy, key, ttl_s, max_life_s, file_sha
        self.hash: str | None = None
        self.decision: Decision | None = None
        self.first_seen = 0.0

    def on_record(self, raw, now: float):
        """Decide on a record not seen before (identical repeats are ignored).  Returns the new Decision or None."""
        h = dp.record_hash(raw) if isinstance(raw, str) else None
        if h is not None and h == self.hash:
            return None
        self.hash, self.first_seen = h, now
        self.decision = decide(raw, self.policy, self.file_sha)
        return self.decision

    def tick(self, now: float):
        """The permit text to publish now, or None.  A permit lives ttl_s; re-issued while the record is current, for at
        most max_life_s after it was first seen (so a dead interlock, or an old record, stops the robot)."""
        d = self.decision
        if d is None or not d.permit or now - self.first_seen > self.max_life_s:
            return None
        return dp.make_permit(d.record_hash, d.run_id, d.station, now, self.ttl_s, self.key)


def summarise_log(path) -> dict:
    """Orchestrator audit: what the interlock decided during a run (JSONL written by the node)."""
    rows = []
    try:
        for line in Path(path).read_text(encoding='utf8').splitlines():
            rows.append(json.loads(line))
    except (OSError, ValueError):
        return {'log': False, 'decisions': 0, 'permits': 0, 'denials': 0}
    dec = [r for r in rows if r.get('event') == 'decision']
    return {'log': True, 'decisions': len(dec), 'permits': sum(1 for r in dec if r.get('permit')),
            'denials': sum(1 for r in dec if not r.get('permit')),
            'last': dec[-1] if dec else None}
