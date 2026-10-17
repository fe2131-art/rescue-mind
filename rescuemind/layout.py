"""Study L: per-trial layout randomisation (stations, shelter) with feasibility checks.

The default layout equals the fixed arena (configs/gazebo_waypoints.json and
configs/gazebo_station_centers.json).  A layout moves the two supply platforms
and the shelter B (position + yaw) and carries the matching approach
waypoints.  Everything is geometry only: no ROS, no Gazebo.

Waypoint relation: for a sampled layout the approach waypoint is the centre
moved WAYPOINT_STANDOFF_M toward the start (rounded to cm).  The default layout
keeps the historical hand-tuned waypoints so it stays byte-identical.
"""
from __future__ import annotations
import json
import math
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NAMES = ('water', 'medicine', 'B')
WAYPOINT_STANDOFF_M = 1.2
STATION_SIZE = (0.9, 0.9)         # aid_station_* collision box (x, y), metres
SHELTER_SIZE = (1.0, 0.8)         # shelter_B collision box
FIRE_RADIUS_M = 0.40              # charred base radius at hazard_xy (visual only, kept clear anyway)
DEFAULT_CENTERS = {'water': (2.0, 2.0, 0.0), 'medicine': (-2.0, 2.0, 0.0), 'B': (3.0, -2.0, 0.0)}
DEFAULT_WAYPOINTS = {'water': (1.18, 1.13), 'medicine': (-1.16, 1.10), 'B': (2.15, -1.12)}

# sampling / feasibility limits (Study L design, section 2.4)
R_MIN, R_MAX = 2.2, 4.0           # centre distance from the start
X_MAX, Y_MAX = 4.5, 3.5
MIN_ANGLE_RAD = math.radians(40.0)
MIN_CENTER_SEP_M = 2.5
MIN_WAYPOINT_SEP_M = 1.5
MIN_WAYPOINT_FROM_START_M = 1.0
MIN_LEG_CLEARANCE_M = 0.6         # legs vs. objects they are not heading for
MIN_OWN_CLEARANCE_M = 0.45        # legs vs. their own endpoint object (waypoints stand 1.2 m off the centre)
MIN_WP_FROM_SHELTER_M = 1.0       # ground-truth denial audit: closest_shelter >= 1.0
YAW_MAX_RAD = math.radians(45.0)
VIEW_CLEARANCE_M = 0.3


def _finite(v) -> bool:
    return type(v) in (int, float) and math.isfinite(v)


def _unit_standoff(cx: float, cy: float, d: float = WAYPOINT_STANDOFF_M) -> tuple[float, float]:
    n = math.hypot(cx, cy)
    return round(cx - d * cx / n, 2), round(cy - d * cy / n, 2)


@dataclass(frozen=True)
class Layout:
    """water / medicine / B = (x, y, yaw).  `waypoints` optionally overrides the derived approach waypoints."""
    water: tuple
    medicine: tuple
    B: tuple
    waypoints: tuple | None = None   # ((wx, wy) x 3 in NAMES order) or None -> derived

    def pose(self, name: str) -> tuple:
        return getattr(self, name)

    def center(self, name: str) -> tuple[float, float]:
        p = self.pose(name)
        return (p[0], p[1])

    def centers(self) -> dict:
        """Supply station centres in the format of configs/gazebo_station_centers.json (tuples)."""
        return {'water': self.center('water'), 'medicine': self.center('medicine')}

    def waypoint(self, name: str) -> tuple[float, float]:
        if self.waypoints is not None:
            return tuple(self.waypoints[NAMES.index(name)])
        return _unit_standoff(*self.center(name))

    def is_default(self) -> bool:
        return all(self.pose(n) == DEFAULT_CENTERS[n] for n in NAMES) and \
            all(self.waypoint(n) == DEFAULT_WAYPOINTS[n] for n in NAMES)

    def to_dict(self) -> dict:
        d = {n: list(self.pose(n)) for n in NAMES}
        d['waypoints'] = {n: list(self.waypoint(n)) for n in NAMES}
        return d

    @staticmethod
    def from_dict(d) -> 'Layout':
        if isinstance(d, Layout):
            return d
        if not isinstance(d, dict) or not set(NAMES) <= set(d) or set(d) - set(NAMES) - {'waypoints'}:
            raise ValueError('layout must have keys water, medicine, B (and optional waypoints)')
        poses = []
        for n in NAMES:
            p = d[n]
            if not isinstance(p, (list, tuple)) or len(p) != 3 or not all(_finite(v) for v in p):
                raise ValueError(f'layout.{n} must be [x, y, yaw] of finite numbers')
            poses.append(tuple(float(v) for v in p))
        wps = None
        if d.get('waypoints') is not None:
            w = d['waypoints']
            if not isinstance(w, dict) or set(w) != set(NAMES):
                raise ValueError('layout.waypoints must have keys water, medicine, B')
            for n in NAMES:
                if not isinstance(w[n], (list, tuple)) or len(w[n]) != 2 or not all(_finite(v) for v in w[n]):
                    raise ValueError(f'layout.waypoints.{n} must be [x, y]')
            wps = tuple(tuple(float(v) for v in w[n]) for n in NAMES)
        lay = Layout(*poses)
        if wps is not None and any(tuple(wps[i]) != lay.waypoint(n) for i, n in enumerate(NAMES)):
            lay = Layout(*poses, waypoints=wps)     # keep only waypoints that differ from the derived relation
        return lay

    def to_configs(self, base: dict | None = None) -> tuple[dict, dict]:
        """(waypoints_config, station_centers_config) in the exact formats of
        configs/gazebo_waypoints.json and configs/gazebo_station_centers.json."""
        if base is None:
            base = json.loads((ROOT / 'configs/gazebo_waypoints.json').read_text(encoding='utf-8'))
        wp = dict(base)
        for n in NAMES:
            wp[n] = [float(v) for v in self.waypoint(n)]
        centers = {n: [float(v) for v in self.center(n)] for n in ('water', 'medicine')}
        return wp, centers

    def write_configs(self, directory: Path) -> tuple[Path, Path]:
        directory = Path(directory)
        wp, centers = self.to_configs()
        a, b = directory / 'waypoints.json', directory / 'station_centers.json'
        a.write_text(json.dumps(wp, indent=2) + '\n', encoding='utf-8')
        b.write_text(json.dumps(centers, indent=2) + '\n', encoding='utf-8')
        return a, b


def default_layout() -> Layout:
    return Layout(DEFAULT_CENTERS['water'], DEFAULT_CENTERS['medicine'], DEFAULT_CENTERS['B'],
                  waypoints=tuple(DEFAULT_WAYPOINTS[n] for n in NAMES))


# ---------------------------------------------------------------- geometry

def _footprint(layout: Layout, name: str) -> tuple:
    x, y, yaw = layout.pose(name)
    sx, sy = SHELTER_SIZE if name == 'B' else STATION_SIZE
    return (x, y, yaw, sx / 2, sy / 2)


def _dist_point_rect(px: float, py: float, rect: tuple) -> float:
    x, y, yaw, hx, hy = rect
    dx, dy = px - x, py - y
    c, s = math.cos(-yaw), math.sin(-yaw)
    lx, ly = dx * c - dy * s, dx * s + dy * c
    return math.hypot(max(abs(lx) - hx, 0.0), max(abs(ly) - hy, 0.0))


def _dist_seg_rect(a: tuple, b: tuple, rect: tuple, step: float = 0.02) -> float:
    n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
    return min(_dist_point_rect(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n, rect)
               for i in range(n + 1))


def _dist_seg_point(a: tuple, b: tuple, p: tuple) -> float:
    vx, vy = b[0] - a[0], b[1] - a[1]
    L2 = vx * vx + vy * vy
    u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L2))
    return math.hypot(a[0] + u * vx - p[0], a[1] + u * vy - p[1])


def look_around_points(layout: Layout, station: str, offset: float) -> dict:
    """The L / R side poses the mission visits (mirrors ros/gazebo_waypoint_mission.schedule_look_around)."""
    cx, cy = layout.center(station)
    wx, wy = layout.waypoint(station)
    n = math.hypot(cx - wx, cy - wy) or 1.0
    vx, vy = -(cy - wy) / n, (cx - wx) / n
    return {'L': (round(wx - offset * vx, 3), round(wy - offset * vy, 3)),
            'R': (round(wx + offset * vx, 3), round(wy + offset * vy, 3))}


def hazard_positions(layout: Layout, hazard_geom: tuple = (0.75, 0.5)) -> dict:
    from .robust_scenes import hazard_xy
    st = layout.centers()
    return {s: hazard_xy(s, *hazard_geom[:2], stations=st) for s in ('water', 'medicine')}


def executed_legs(layout: Layout, look_around: float) -> list:
    """Every straight leg the controller may drive (no obstacle avoidance exists): start to a station
    waypoint, all pairs among station / look-around / shelter waypoints (covers recovery search,
    L-R-B ordering and the delivery leg).  Each leg is (name, a, b, own_objects)."""
    start = (0.0, 0.0)
    pts = {'start': start, 'wp:water': layout.waypoint('water'), 'wp:medicine': layout.waypoint('medicine'),
           'wp:B': layout.waypoint('B')}
    if look_around:
        for s in ('water', 'medicine'):
            for side, xy in look_around_points(layout, s, look_around).items():
                pts[f'{side}:{s}'] = xy
    owner = {'wp:water': 'water', 'wp:medicine': 'medicine', 'wp:B': 'B'}
    for k in list(pts):
        if ':' in k and k.split(':')[1] in ('water', 'medicine') and k[0] in 'LR':
            owner[k] = k.split(':')[1]
    legs = [('start->wp:water', start, pts['wp:water']), ('start->wp:medicine', start, pts['wp:medicine'])]
    keys = [k for k in pts if k != 'start']
    for i, ka in enumerate(keys):
        for kb in keys[i + 1:]:
            legs.append((f'{ka}->{kb}', pts[ka], pts[kb]))
    out = []
    for name, a, b in legs:
        ka, kb = name.split('->')
        own = {owner.get(ka), owner.get(kb)} - {None}
        out.append((name, a, b, own))
    return out


def check_layout(layout: Layout, *, look_around: float = 0.4, hazard_geom: tuple = (0.75, 0.5),
                 hazard_at: str | None = None, distractor_world_frame: bool = False) -> list[str]:
    """Return a list of violated constraints (empty = feasible).  Fire/distractor positions are checked
    for both stations unless hazard_at is given, because the world spec decides them later."""
    bad: list[str] = []
    c = {n: layout.center(n) for n in NAMES}
    wp = {n: layout.waypoint(n) for n in NAMES}
    for n in NAMES:
        x, y = c[n]
        if abs(x) > X_MAX or abs(y) > Y_MAX:
            bad.append(f'{n}: centre outside arena box')
        if not R_MIN <= math.hypot(x, y) <= R_MAX:
            bad.append(f'{n}: centre radius from start outside [{R_MIN}, {R_MAX}]')
        if math.hypot(*wp[n]) < MIN_WAYPOINT_FROM_START_M:
            bad.append(f'{n}: waypoint closer than {MIN_WAYPOINT_FROM_START_M} m to the start')
        if abs(layout.pose(n)[2]) > YAW_MAX_RAD + 1e-9:
            bad.append(f'{n}: yaw beyond +/-45 deg')
    bearings = {n: math.atan2(c[n][1], c[n][0]) for n in NAMES}
    for i, a in enumerate(NAMES):
        for b in NAMES[i + 1:]:
            d = abs(math.atan2(math.sin(bearings[a] - bearings[b]), math.cos(bearings[a] - bearings[b])))
            if d < MIN_ANGLE_RAD:
                bad.append(f'{a}/{b}: bearings closer than 40 deg')
            if math.dist(c[a], c[b]) < MIN_CENTER_SEP_M:
                bad.append(f'{a}/{b}: centres closer than {MIN_CENTER_SEP_M} m')
            if math.dist(wp[a], wp[b]) < MIN_WAYPOINT_SEP_M:
                bad.append(f'{a}/{b}: waypoints closer than {MIN_WAYPOINT_SEP_M} m')
    shelter = wp['B']
    for s in ('water', 'medicine'):
        if math.dist(wp[s], shelter) < MIN_WP_FROM_SHELTER_M:
            bad.append(f'{s}: station waypoint closer than 1 m to the shelter waypoint')
        if look_around:
            for side, xy in look_around_points(layout, s, look_around).items():
                if math.dist(xy, shelter) < MIN_WP_FROM_SHELTER_M + 0.2:
                    bad.append(f'{s}:{side}: look-around point too close to the shelter waypoint')
    # obstacles the straight legs must clear
    rects = {n: _footprint(layout, n) for n in NAMES}
    fires = {}
    if hazard_at is None or hazard_at in ('water', 'medicine'):
        hz = hazard_positions(layout, hazard_geom)
        fires = {s: hz[s] for s in hz if hazard_at in (None, s)}
    disks = {f'fire:{s}': (xy, FIRE_RADIUS_M) for s, xy in fires.items()}
    if distractor_world_frame:
        for s in ('water', 'medicine'):
            x, y = c[s]
            for k, (dx, dy) in enumerate(((0.70, -0.55), (-0.70, -0.55), (0.70, -0.45), (-0.70, -0.45), (0.05, -0.80))):
                disks[f'distractor{k}:{s}'] = ((x + dx, y + dy), 0.25)
    for name, a, b, own in executed_legs(layout, look_around):
        for n in NAMES:
            need = MIN_OWN_CLEARANCE_M if n in own else MIN_LEG_CLEARANCE_M
            if _dist_seg_rect(a, b, rects[n]) < need:
                bad.append(f'leg {name}: within {need} m of {n}')
        for k, (xy, r) in disks.items():
            if _dist_seg_point(a, b, xy) - r < MIN_LEG_CLEARANCE_M:
                bad.append(f'leg {name}: within {MIN_LEG_CLEARANCE_M} m of {k}')
    # the camera view line (waypoint -> own centre) must not pass near another object
    for s in ('water', 'medicine'):
        for n in NAMES:
            if n != s and _dist_seg_rect(wp[s], c[s], rects[n]) < VIEW_CLEARANCE_M:
                bad.append(f'view {s}: line of sight passes within {VIEW_CLEARANCE_M} m of {n}')
    return bad


def feasible(layout: Layout, **kw) -> bool:
    return not check_layout(layout, **kw)


def sample_layout(rng, *, look_around: float = 0.4, max_tries: int = 5000, **check_kw) -> Layout:
    """Rejection-sample a feasible layout from `rng` (random.Random-like with .uniform).
    Positions are rounded to cm and yaw to mrad so the JSON round-trips exactly."""
    for _ in range(max_tries):
        poses = []
        for _n in NAMES:
            r = rng.uniform(R_MIN, R_MAX)
            th = rng.uniform(-math.pi, math.pi)
            poses.append((round(r * math.cos(th), 2), round(r * math.sin(th), 2),
                          round(rng.uniform(-YAW_MAX_RAD, YAW_MAX_RAD), 3)))
        lay = Layout(*poses)
        if feasible(lay, look_around=look_around, **check_kw):
            return lay
    raise RuntimeError('no feasible layout found')
