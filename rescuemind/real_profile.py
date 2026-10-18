"""I-26: opt-in real-robot profile (pure Python, no ROS import, so every rule here is unit-testable offline).

Everything in this module is OFF unless a flag asks for it; the default command lines and the default behaviour of the
mission node, the velocity guard, the interlock and the VLM server are unchanged (the registered studies use them).

  * SystemClockGate     the camera-stamp freshness check against the host's system clock instead of Gazebo /clock
                        (`--clock-source system`).  Same tolerances as CameraClockGate (1.2 s lag / 0.25 s lead), fail closed
                        when the stamp is absent, zero, not monotonic, or the system clock itself steps backwards.
  * SiteConfig          one `site.json`: tau_h (+ the caution threshold derived from it, + optionally the prompt wording,
                        the hazard views and the odometry frame names), read by the server, the mission node, the interlock
                        and the orchestrator so that they cannot disagree.
  * frame helpers       `--odom-frame` / `--base-frame` (the suffix the odometry frame names must end with).

NOT safety-certified; a real robot has still never been run (docs/DEPLOYMENT.md).
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

from .camera_clock_gate import CameraClockRejected
from .frame_freshness import frame_stamp_ns
from .mission_memory import CAUTION_TAU_H

SITE_SCHEMA = 'rescuemind-site-1'
CLOCK_SOURCES = ('sim', 'system')
CAMERA_QOS = ('reliable', 'best_effort')
DEFAULT_CAUTION_RATIO = 0.2          # = 0.01 / 0.05: the simulation-calibrated caution threshold relative to tau_h = 0.05
HAZARD_PROMPTS = ('h35', 'h36', 'h36ign')
HAZARD_VIEWS = ('full', 'tiles')
SYSTEM_CLOCK_BASIS = 'system_clock_vs_camera_ROS_stamp'
SYSTEM_CLOCK_STAGE = 'checkpoint_camera_system_clock_verified'
_SITE_KEYS = {'schema', 'hazard_threshold', 'caution_ratio', 'hazard_prompt', 'hazard_views', 'odom_frame', 'base_frame',
              'comment'}


class SiteConfigError(ValueError):
    pass


# ---------------------------------------------------------------------------------------------------------------------
# clock source
# ---------------------------------------------------------------------------------------------------------------------
class SystemClockGate:
    """Camera ROS stamp vs the host's system clock (a real robot has no /clock).

    `check_frame(msg, wall_s, received_ns)` mirrors `CameraClockGate.check_frame`.  `received_ns` is the system time taken in
    the camera callback (so the executor's polling delay is not counted as camera lag); without it the current time is used.
    Fail closed: absent / zero / negative stamp, a stamp that goes backwards (sticky: one regression poisons the gate, the
    mission must be restarted), a system clock that goes backwards, a frame older than `max_camera_lag_s` or ahead of the
    clock by more than `max_camera_lead_s`.  The camera computer's clock must be synchronised with this host (chrony / PTP):
    a skewed camera clock is rejected here, never compensated.
    """

    def __init__(self, max_camera_lag_s: float = 1.2, max_camera_lead_s: float = 0.25, now_ns=time.time_ns):
        for v in (max_camera_lag_s, max_camera_lead_s):
            if type(v) not in (float, int) or not math.isfinite(v) or not 0 < v <= 30:
                raise CameraClockRejected('invalid_camera_clock_parameters')
        if not callable(now_ns):
            raise CameraClockRejected('invalid_camera_clock_parameters')
        self.max_camera_lag_s = max_camera_lag_s
        self.max_camera_lead_s = max_camera_lead_s
        self.now_ns = now_ns
        self.last_frame_ns: int | None = None
        self.last_now_ns: int | None = None
        self.stamp_regressed = False
        self.rejected_count = 0
        self.checked = 0

    def _reject(self, reason: str):
        self.rejected_count += 1
        raise CameraClockRejected(reason)

    def check_frame(self, msg, wall_s=None, received_ns: int | None = None) -> dict:
        if wall_s is not None and (not isinstance(wall_s, (int, float)) or isinstance(wall_s, bool)
                                   or not math.isfinite(wall_s)):
            self._reject('invalid_frame_receive_time')
        frame_ns = frame_stamp_ns(msg)
        if frame_ns is None:
            self._reject('invalid_camera_ros_stamp')            # absent, zero, negative or malformed
        if self.stamp_regressed:
            self._reject('camera_stamp_not_monotonic')
        if self.last_frame_ns is not None and frame_ns < self.last_frame_ns:
            self.stamp_regressed = True
            self._reject('camera_stamp_not_monotonic')
        self.last_frame_ns = frame_ns
        now = self.now_ns() if received_ns is None else received_ns
        if type(now) is not int or now <= 0:
            self._reject('invalid_system_clock')
        if self.last_now_ns is not None and now < self.last_now_ns:
            self._reject('system_clock_rewound')
        self.last_now_ns = now
        delta_s = (now - frame_ns) / 1e9
        if delta_s > self.max_camera_lag_s:
            self._reject('camera_acquisition_too_old_for_system_clock')
        if delta_s < -self.max_camera_lead_s:
            self._reject('camera_acquisition_ahead_of_system_clock')
        self.checked += 1
        return {'basis': SYSTEM_CLOCK_BASIS,
                'camera_lag_to_system_clock_s': round(delta_s, 4),
                'system_clock_ns': now,
                'camera_ros_stamp_ns': frame_ns,
                'checks_passed': self.checked,
                'limits_s': {'max_lag': self.max_camera_lag_s, 'max_lead': self.max_camera_lead_s}}


class SystemClockEvidenceError(ValueError):
    pass


def audit_system_clock_capture(mission: dict) -> dict:
    """Offline consistency audit of the `checkpoint_camera_system_clock_verified` receipt (self-reported, like the Gazebo
    one: it shows the run applied the check with the vetted limits, not that the camera clock is truthful)."""
    try:
        events = mission['events']
        found = [e for e in events if isinstance(e, dict) and e.get('stage') == SYSTEM_CLOCK_STAGE]
        if len(found) != 1:
            raise SystemClockEvidenceError('missing_or_duplicate_receipt')
        proof = found[0]
        if proof.get('basis') != SYSTEM_CLOCK_BASIS:
            raise SystemClockEvidenceError('incorrect_clock_time_basis')
        now_ns, cam_ns = proof.get('system_clock_ns'), proof.get('camera_ros_stamp_ns')
        if type(now_ns) is not int or type(cam_ns) is not int or now_ns <= 0 or cam_ns <= 0:
            raise SystemClockEvidenceError('bad_stamps')
        limits = proof.get('limits_s')
        if not isinstance(limits, dict):
            raise SystemClockEvidenceError('no_clock_limits')
        for k in ('max_lag', 'max_lead'):
            v = limits.get(k)
            if type(v) not in (int, float) or not math.isfinite(v) or v <= 0:
                raise SystemClockEvidenceError('invalid_clock_limit_' + k)
        if limits['max_lag'] > 1.2 or limits['max_lead'] > 0.25:
            raise SystemClockEvidenceError('clock_limits_weakened')
        delta = (now_ns - cam_ns) / 1e9
        if delta > limits['max_lag'] or delta < -limits['max_lead']:
            raise SystemClockEvidenceError('camera_frame_not_near_system_time')
        lag = proof.get('camera_lag_to_system_clock_s')
        if type(lag) not in (int, float) or not math.isfinite(lag) or abs(lag - delta) > 0.00011:
            raise SystemClockEvidenceError('reported_camera_lag_inconsistent')
        frame = [e for e in events if isinstance(e, dict) and e.get('stage') == 'checkpoint_frame']
        if len(frame) != 1 or frame[0].get('ros_acquisition_stamp_ns') != cam_ns:
            raise SystemClockEvidenceError('camera_clock_stamp_disagrees_with_saved_frame')
    except (KeyError, TypeError, AttributeError) as exc:
        raise SystemClockEvidenceError('malformed_mission_record') from exc
    return {'passed': True, 'camera_lag_to_system_clock_s': proof['camera_lag_to_system_clock_s']}


# ---------------------------------------------------------------------------------------------------------------------
# odometry frame names
# ---------------------------------------------------------------------------------------------------------------------
def check_frame_name(name, what: str = 'frame') -> str:
    if (not isinstance(name, str) or not name or len(name) > 64 or name != name.strip()
            or any(c.isspace() or c in '\\"\'' for c in name)):
        raise SiteConfigError(f'{what}: invalid frame name {name!r}')
    return name


def odom_frames_ok(msg, odom_frame: str | None, base_frame: str | None) -> bool:
    """True iff `msg.header.frame_id` ends with `odom_frame` and `msg.child_frame_id` with `base_frame` (a None name is not
    checked here; the guard's own OdomHealth keeps checking the defaults 'odom' / 'base_link')."""
    try:
        if odom_frame is not None and not str(msg.header.frame_id).endswith(odom_frame):
            return False
        if base_frame is not None and not str(msg.child_frame_id).endswith(base_frame):
            return False
    except AttributeError:
        return False
    return True


# ---------------------------------------------------------------------------------------------------------------------
# profile validation
# ---------------------------------------------------------------------------------------------------------------------
def check_profile(clock_source: str = 'sim', camera_qos: str = 'reliable') -> bool:
    """-> True iff the real profile is active.  `best_effort` camera QoS exists only under the real profile: in simulation a
    best-effort image subscriber lost 92 of 102 frames under load (FINDINGS #5), so the simulation stays Reliable."""
    if clock_source not in CLOCK_SOURCES:
        raise SiteConfigError(f'--clock-source must be one of {CLOCK_SOURCES}')
    if camera_qos not in CAMERA_QOS:
        raise SiteConfigError(f'--camera-qos must be one of {CAMERA_QOS}')
    real = clock_source == 'system'
    if camera_qos == 'best_effort' and not real:
        raise SiteConfigError('--camera-qos best_effort is allowed only under the real profile (--clock-source system)')
    return real


def guard_settings(args) -> tuple[str, str | None, str | None]:
    """Velocity guard options -> (camera reliability, odom suffix or None, base suffix or None).  The guard has no clock
    notion; its real profile is the explicit `--real-profile` flag, which `--camera-qos best_effort` needs."""
    rel = getattr(args, 'camera_qos', 'reliable')
    if rel not in CAMERA_QOS:
        raise SiteConfigError(f'--camera-qos must be one of {CAMERA_QOS}')
    if rel == 'best_effort' and not getattr(args, 'real_profile', False):
        raise SiteConfigError('--camera-qos best_effort is allowed only with --real-profile')
    site = load_site_config(args.site_config) if getattr(args, 'site_config', None) else None
    odom = getattr(args, 'odom_frame', None) or (site.odom_frame if site else None)
    base = getattr(args, 'base_frame', None) or (site.base_frame if site else None)
    if odom is not None:
        check_frame_name(odom, '--odom-frame')
    if base is not None:
        check_frame_name(base, '--base-frame')
    return rel, odom, base


# ---------------------------------------------------------------------------------------------------------------------
# site.json
# ---------------------------------------------------------------------------------------------------------------------
def derive_caution(tau_h: float, ratio: float = DEFAULT_CAUTION_RATIO) -> float:
    """The memory / advice caution threshold for a site tau_h: `min(CAUTION_TAU_H, ratio * tau_h)`.

    Scaled DOWN with tau_h (ratio 0.2: tau_h 0.05 -> 0.01, the simulation value; a stricter site tau_h 0.02 -> 0.004) so the
    caution stays below tau_h, but NEVER scaled up beyond 0.01: the audits and the machine-checked monotonicity proofs bound
    the caution by the v3.6 constants (0 < tau_mem < 0.05, scrutiny <= 0.01).  At a site with tau_h = 0.30 the caution stays
    0.01, which is 30x stricter than tau_h: it only fires at stations with a remembered / advised hazard and can only
    refuse more (docs/DEPLOYMENT.md section 3.1: the caution threshold is not calibrated on real photographs)."""
    c = min(CAUTION_TAU_H, round(float(ratio) * float(tau_h), 6))
    if not (0 < c < tau_h):
        raise SiteConfigError(f'derived caution threshold {c} must satisfy 0 < caution < tau_h = {tau_h}')
    return c


@dataclass(frozen=True)
class SiteConfig:
    hazard_threshold: float
    caution_ratio: float
    caution_tau_h: float
    hazard_prompt: str | None
    hazard_views: str | None
    odom_frame: str | None
    base_frame: str | None
    path: str
    sha256: str

    def block(self) -> dict:
        """What the mission records in mission.json (and what the audits read back)."""
        return {'schema': SITE_SCHEMA, 'path': self.path, 'sha256': self.sha256,
                'hazard_threshold': self.hazard_threshold, 'caution_ratio': self.caution_ratio,
                'caution_tau_h': self.caution_tau_h, 'hazard_prompt': self.hazard_prompt,
                'hazard_views': self.hazard_views, 'odom_frame': self.odom_frame, 'base_frame': self.base_frame}


def _strict_pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise SiteConfigError(f'duplicate key {k!r}')
        out[k] = v
    return out


def _no_constant(c):
    raise SiteConfigError(f'non-finite number {c} in site config')


def _number(d: dict, key: str, lo: float, hi: float, *, hi_inclusive: bool):
    v = d[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise SiteConfigError(f'{key} must be a finite number')
    ok = (lo < v <= hi) if hi_inclusive else (lo < v < hi)
    if not ok:
        raise SiteConfigError(f'{key} must be in ({lo}, {hi}{"]" if hi_inclusive else ")"}')
    return float(v)


def parse_site_config(text: str, path: str = '<memory>', raw: bytes | None = None) -> SiteConfig:
    try:
        d = json.loads(text, object_pairs_hook=_strict_pairs, parse_constant=_no_constant)
    except json.JSONDecodeError as exc:
        raise SiteConfigError(f'site config is not valid JSON: {exc}') from exc
    if not isinstance(d, dict):
        raise SiteConfigError('site config must be a JSON object')
    if d.get('schema') != SITE_SCHEMA:
        raise SiteConfigError(f'schema must be {SITE_SCHEMA!r}')
    extra = set(d) - _SITE_KEYS
    if extra:
        raise SiteConfigError(f'unknown site config keys: {sorted(extra)}')
    if 'hazard_threshold' not in d:
        raise SiteConfigError('hazard_threshold is required')
    tau = _number(d, 'hazard_threshold', 0.0, 1.0, hi_inclusive=True)          # the server accepts (0, 1]
    ratio = _number(d, 'caution_ratio', 0.0, 1.0, hi_inclusive=False) if 'caution_ratio' in d else DEFAULT_CAUTION_RATIO
    prompt, views = d.get('hazard_prompt'), d.get('hazard_views')
    if prompt is not None and prompt not in HAZARD_PROMPTS:
        raise SiteConfigError(f'hazard_prompt must be one of {HAZARD_PROMPTS}')
    if views is not None and views not in HAZARD_VIEWS:
        raise SiteConfigError(f'hazard_views must be one of {HAZARD_VIEWS}')
    odom = check_frame_name(d['odom_frame'], 'odom_frame') if d.get('odom_frame') is not None else None
    base = check_frame_name(d['base_frame'], 'base_frame') if d.get('base_frame') is not None else None
    data = raw if raw is not None else text.encode('utf8')
    return SiteConfig(hazard_threshold=tau, caution_ratio=ratio, caution_tau_h=derive_caution(tau, ratio),
                      hazard_prompt=prompt, hazard_views=views, odom_frame=odom, base_frame=base,
                      path=str(path), sha256=hashlib.sha256(data).hexdigest())


def load_site_config(path) -> SiteConfig:
    p = Path(path)
    try:
        raw = p.read_bytes()
        text = raw.decode('utf8')
    except (OSError, UnicodeError) as exc:
        raise SiteConfigError(f'cannot read site config {p}: {exc}') from exc
    return parse_site_config(text, str(p), raw)


def resolve(name: str, explicit, site_value, default):
    """One setting with a site config: explicit flag (None = not given) must agree with the site value, which then wins.
    Without a site value: the explicit flag, else the default.  A conflict is an error, never a silent override."""
    if site_value is None:
        return default if explicit is None else explicit
    if explicit is not None:
        same = (abs(float(explicit) - float(site_value)) <= 1e-12
                if isinstance(site_value, float) else explicit == site_value)
        if not same:
            raise SiteConfigError(f'--{name} {explicit!r} conflicts with the site config value {site_value!r}')
    return site_value


def audit_kwargs(record: dict | None) -> dict:
    """Keyword arguments for `audit_local_checkpoint` taken from a mission record: empty for a normal run (the audit then uses
    the v3.6 tau_h 0.05, exactly as before), the recorded site tau_h (and `require_threshold`) for a run with --site-config."""
    site = (record or {}).get('site_config') if isinstance(record, dict) else None
    if site is None:
        return {}
    tau = site.get('hazard_threshold') if isinstance(site, dict) else None
    if isinstance(tau, bool) or not isinstance(tau, (int, float)) or not math.isfinite(tau) or not 0 < tau <= 1:
        raise ValueError('mission.json site_config has no valid hazard_threshold')
    return {'hazard_threshold': float(tau), 'require_threshold': True}
