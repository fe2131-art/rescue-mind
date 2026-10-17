"""I-22: delivery permits (shared by the interlock node and the velocity guard; deliberately tiny, no decision logic).

Message flow (all std_msgs/String, JSON text):

  mission node  --/rescuemind/approval_record-->  interlock node  --/rescuemind/delivery_permit-->  velocity guard
  mission node  --/rescuemind/phase ('search' | 'deliver')------------------------------------->  velocity guard
  mission node  --/rescuemind/approval_record------------------------------------------------->  velocity guard (hash only)

The guard never parses the record: it hashes the raw text of the latest record and accepts a permit only if the permit
names that hash.  A permit is time limited (`not_after`) and, when a key file is configured, carries an HMAC-SHA256 over
its fields, so a process that cannot read the key cannot mint one.  Without a key the permit only protects against bugs
(a mission node that forgets to ask), not against a node that forges the message.

Fail-closed rules of the gate: a missing, stale or unknown phase counts as 'deliver'; in 'deliver' non-zero velocity is
forwarded only with a valid permit for the latest record; zero is always forwarded.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import math
import os
from pathlib import Path

TOPIC_RECORD = '/rescuemind/approval_record'
TOPIC_PERMIT = '/rescuemind/delivery_permit'
TOPIC_PHASE = '/rescuemind/phase'
TOPIC_DECISION = '/rescuemind/delivery_decision'
PHASE_SEARCH = 'search'
PHASE_DELIVER = 'deliver'
RECORD_VERSION = 1
PERMIT_VERSION = 1
MAX_RECORD_BYTES = 4_000_000
CLOCK_SKEW_S = 2.0          # a permit issued more than this in the future is rejected (clock jump)


def record_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def generate_key(path) -> bytes:
    """Write a fresh 256-bit key (hex) with mode 0600 and return it.  Called once per stack start by the orchestrator."""
    key = os.urandom(32)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(key.hex() + '\n')
    return key


def load_key(path) -> bytes:
    key = bytes.fromhex(Path(path).read_text().strip())
    if len(key) < 16:
        raise ValueError('permit key too short')
    return key


def _mac(key: bytes, fields: dict) -> str:
    body = json.dumps(fields, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
    return hmac.new(key, body, hashlib.sha256).hexdigest()


def make_permit(rhash: str, run_id: str, station: str, now: float, ttl_s: float, key: bytes | None = None) -> str:
    fields = {'v': PERMIT_VERSION, 'record_hash': rhash, 'run_id': run_id, 'station': station,
              'issued_at': round(float(now), 3), 'not_after': round(float(now) + float(ttl_s), 3)}
    out = dict(fields, mac=_mac(key, fields) if key else None)
    return json.dumps(out, sort_keys=True)


def check_permit(raw, *, key: bytes | None, now: float, expected_hash: str | None, max_ttl_s: float = 60.0):
    """(ok, reason).  Never raises."""
    try:
        if not isinstance(raw, str) or len(raw) > 10_000 or expected_hash is None:
            return False, 'no_record' if expected_hash is None else 'malformed_permit'
        p = json.loads(raw)
        if not isinstance(p, dict) or p.get('v') != PERMIT_VERSION:
            return False, 'malformed_permit'
        fields = {k: p.get(k) for k in ('v', 'record_hash', 'run_id', 'station', 'issued_at', 'not_after')}
        if set(p) != set(fields) | {'mac'}:
            return False, 'malformed_permit'
        if key is not None:
            mac = p.get('mac')
            if not isinstance(mac, str) or not hmac.compare_digest(mac, _mac(key, fields)):
                return False, 'bad_mac'
        a, b = fields['issued_at'], fields['not_after']
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in (a, b)):
            return False, 'malformed_permit'
        if not 0 < b - a <= max_ttl_s:
            return False, 'bad_ttl'
        if a > now + CLOCK_SKEW_S:
            return False, 'issued_in_the_future'
        if now > b:
            return False, 'expired'
        if fields['record_hash'] != expected_hash:
            return False, 'record_mismatch'
        return True, 'ok'
    except (ValueError, TypeError):
        return False, 'malformed_permit'


class PermitGate:
    """The guard's whole delivery rule.  One clock (`now`, wall seconds) for phase age and permit expiry."""

    def __init__(self, key: bytes | None = None, phase_max_age_s: float = 1.0, max_ttl_s: float = 60.0):
        self.key = key
        self.phase_max_age_s = phase_max_age_s
        self.max_ttl_s = max_ttl_s
        self.record_hash: str | None = None
        self.permit: str | None = None
        self.phase: str | None = None
        self.phase_at: float | None = None

    def on_record(self, raw: str) -> None:
        if isinstance(raw, str) and len(raw) <= MAX_RECORD_BYTES:
            self.record_hash = record_hash(raw)
        else:
            self.record_hash = None            # an unusable record invalidates every earlier permit

    def on_permit(self, raw: str) -> None:
        self.permit = raw

    def on_phase(self, text: str, now: float) -> None:
        self.phase, self.phase_at = text, now

    def requires_permit(self, now: float) -> bool:
        return not (self.phase == PHASE_SEARCH and self.phase_at is not None and 0 <= now - self.phase_at <= self.phase_max_age_s)

    def permitted(self, now: float):
        return check_permit(self.permit, key=self.key, now=now, expected_hash=self.record_hash, max_ttl_s=self.max_ttl_s)

    def filter(self, linear: float, angular: float, now: float):
        """(linear, angular, reason).  reason is None when the command is passed unchanged."""
        if linear == 0.0 and angular == 0.0:
            return linear, angular, None
        if not self.requires_permit(now):
            return linear, angular, None
        ok, why = self.permitted(now)
        if ok:
            return linear, angular, None
        return 0.0, 0.0, 'delivery_interlock_' + why


def build_record(mission: dict, *, image_dir, front_name: str, look_around: float = 0.0, adaptive_views: float = 0.0) -> str:
    """The approval record the mission node publishes before the delivery leg: everything the interlock needs to redo the
    decision (station, saved model outputs incl. look-around, the applied plan with advice and caution) plus where the
    saved images are.  A snapshot: later changes to `mission` do not alter it."""
    rec = {'v': RECORD_VERSION, 'run_id': mission.get('run_id'), 'station': mission.get('checkpoint_station'),
           'expected': (mission.get('intent') or {}).get('item'), 'checkpoint': mission.get('checkpoint'),
           'plan': mission.get('memory'), 'advice_scrutiny': bool(mission.get('advice_scrutiny')),
           'stations': mission.get('stations'), 'config': {'look_around': float(look_around), 'adaptive_views': float(adaptive_views)},
           'images': {'dir': str(image_dir), 'front': str(front_name)}}
    return json.dumps(json.loads(json.dumps(rec)), sort_keys=True, ensure_ascii=False)
