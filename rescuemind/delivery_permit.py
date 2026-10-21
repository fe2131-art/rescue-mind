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

Shelter geofence (the phase is no longer trusted).  The mission node reports the phase itself, so a node that says
'search' during the shelter leg would skip the permit.  The guard therefore also derives the protected zone from
geometry: a disc around the shelter approach point B, read from the per-run waypoints file the guard is launched with
(not from the mission), and the guard's own odometry.  Non-zero velocity whose predicted path (commanded velocity over a
short horizon) is inside or enters the disc needs a valid permit, whatever phase is claimed.  Missing, stale or
non-finite odometry counts as 'inside'.  The phase stays as an additional, stricter signal ('deliver' needs a permit
anywhere).
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


GEOFENCE_RADIUS_M = 0.5     # disc around the shelter approach point B (see tests: all other waypoints / look-around poses >= 1.0 m away)
GEOFENCE_HORIZON_S = 1.0    # the commanded velocity is extrapolated this far (waypoint speed .19 m/s -> about .2 m look-ahead)
GEOFENCE_STEP_S = 0.1
ODOM_MAX_AGE_S = 1.0


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


def load_geofence_centre(path) -> tuple[float, float]:
    """The shelter approach point 'B' of a per-run waypoints file (x, y).  Raises ValueError when absent or malformed
    (the guard then refuses to start: fail closed)."""
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    b = d.get('B') if isinstance(d, dict) else None
    if not (isinstance(b, (list, tuple)) and len(b) == 2
            and all(type(v) in (int, float) and math.isfinite(v) and abs(v) <= 50 for v in b)):
        raise ValueError('geofence: waypoints file has no valid B')
    return float(b[0]), float(b[1])


class ShelterGeofence:
    """Disc around the shelter approach point; `hits` says whether a command drives the robot inside or into it."""

    def __init__(self, centre, radius: float = GEOFENCE_RADIUS_M, horizon_s: float = GEOFENCE_HORIZON_S,
                 odom_max_age_s: float = ODOM_MAX_AGE_S):
        if not (len(centre) == 2 and all(math.isfinite(v) for v in centre)):
            raise ValueError('geofence centre must be finite')
        if not (math.isfinite(radius) and 0 < radius <= 2.0):
            raise ValueError('geofence radius must be in (0, 2] m')
        self.centre = (float(centre[0]), float(centre[1]))
        self.radius, self.horizon_s, self.odom_max_age_s = float(radius), float(horizon_s), float(odom_max_age_s)
        self.pose: tuple | None = None
        self.pose_at: float | None = None

    @classmethod
    def from_waypoints_file(cls, path, radius: float = GEOFENCE_RADIUS_M, **kw) -> 'ShelterGeofence':
        d = json.loads(Path(path).read_text(encoding='utf-8'))
        g = cls(load_geofence_centre(path), radius, **kw)
        init = d.get('initial') if isinstance(d, dict) else None
        if isinstance(init, (list, tuple)) and len(init) == 2 and all(type(v) in (int, float) for v in init) \
                and math.dist(init, g.centre) <= g.radius:
            raise ValueError('geofence contains the start position')
        return g

    def on_odom(self, x, y, yaw, now: float) -> None:
        if all(isinstance(v, (int, float)) and math.isfinite(v) for v in (x, y, yaw)):
            self.pose, self.pose_at = (float(x), float(y), float(yaw)), now

    def odom_ok(self, now: float) -> bool:
        return self.pose is not None and self.pose_at is not None and 0 <= now - self.pose_at <= self.odom_max_age_s

    def hits(self, linear: float, angular: float, now: float) -> bool:
        """True when the robot is inside, or the command would take it inside within the horizon.  No usable odometry or
        a non-finite command counts as a hit."""
        if not self.odom_ok(now) or not (math.isfinite(linear) and math.isfinite(angular)):
            return True
        x, y, th = self.pose
        cx, cy = self.centre
        t = 0.0
        while True:
            if math.hypot(x - cx, y - cy) <= self.radius:
                return True
            if t >= self.horizon_s - 1e-9:
                return False
            dt = min(GEOFENCE_STEP_S, self.horizon_s - t)
            x += linear * math.cos(th + angular * dt / 2) * dt
            y += linear * math.sin(th + angular * dt / 2) * dt
            th += angular * dt
            t += dt


class PermitGate:
    """The guard's whole delivery rule.  One clock (`now`, wall seconds) for phase age and permit expiry."""

    def __init__(self, key: bytes | None = None, phase_max_age_s: float = 1.0, max_ttl_s: float = 60.0,
                 fence: 'ShelterGeofence | None' = None):
        self.fence = fence
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

    def on_odom(self, x, y, yaw, now: float) -> None:
        if self.fence is not None:
            self.fence.on_odom(x, y, yaw, now)

    def filter(self, linear: float, angular: float, now: float):
        """(linear, angular, reason).  reason is None when the command is passed unchanged."""
        if linear == 0.0 and angular == 0.0:
            return linear, angular, None
        if self.requires_permit(now):
            prefix = 'delivery_interlock_'
        elif self.fence is not None and self.fence.hits(linear, angular, now):
            prefix = 'delivery_interlock_geofence_'      # the claimed phase says 'search', the geometry disagrees
        else:
            return linear, angular, None
        ok, why = self.permitted(now)
        if ok:
            return linear, angular, None
        return 0.0, 0.0, prefix + why


def build_record(mission: dict, *, image_dir, front_name: str, look_around: float = 0.0, adaptive_views: float = 0.0, look_around_sides: str = 'LR') -> str:
    """The approval record the mission node publishes before the delivery leg: everything the interlock needs to redo the
    decision (station, saved model outputs incl. look-around, the applied plan with advice and caution) plus where the
    saved images are.  A snapshot: later changes to `mission` do not alter it."""
    rec = {'v': RECORD_VERSION, 'run_id': mission.get('run_id'), 'station': mission.get('checkpoint_station'),
           'expected': (mission.get('intent') or {}).get('item'), 'checkpoint': mission.get('checkpoint'),
           'plan': mission.get('memory'), 'advice_scrutiny': bool(mission.get('advice_scrutiny')),
           'stations': mission.get('stations'), 'config': {'look_around': float(look_around), 'adaptive_views': float(adaptive_views), 'look_around_sides': str(look_around_sides)},
           'images': {'dir': str(image_dir), 'front': str(front_name)}}
    return json.dumps(json.loads(json.dumps(rec)), sort_keys=True, ensure_ascii=False)
