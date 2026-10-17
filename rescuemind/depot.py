"""I-21: dress the arena as a realistic relief depot (AWS RoboMaker small warehouse, MIT-0).

The warehouse models (walls, floor, shelves, desks, clutter, buckets, trash can, pallet jack) are placed AROUND the
operating area of the arena, so the station and shelter coordinates, the waypoints, the audits and the fire masks are
unchanged.  Every camera frame then carries realistic background clutter, shelves and occluders.  Clutter placement is
drawn per world (seed), and an optional pallet jack can block the aisle behind a station (an obstacle the robot sees but
whose corridor it never enters).

I-21 phase 2 (k = 4 supply stations): `K4_*` below place four supply bays (two water, two medicine in the inventory) on
pallets in the open floor between the east rack row and the west rack, enlarge the operating area to hold them and
their routes, and write the per-run configuration (`write_k4_configs`: waypoints.json with a `stations` block +
station_centers.json, the format of rescuemind.stations).  `check_k4_layout` is the pure-geometry feasibility check.

Assets are fetched once into worlds/assets/aws-wh (git-ignored; scripts/fetch_depot_assets.sh).  Models are inlined into
the world with absolute mesh paths, so no GZ_SIM_RESOURCE_PATH is needed.
"""
from __future__ import annotations
import copy
import functools
import math
import random
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'worlds/assets/aws-wh'
P = 'aws_robomaker_warehouse_'

# The fixed shell of the warehouse (origin-centred, ~14 m x 20 m): walls and floor.  No roof, so the overhead film
# camera and the sun still work.
SHELL = [('WallB_01', 0.0, 0.0, 0.0), ('GroundB_01', 0.0, 0.0, 0.0)]
Z = {'GroundB_01': -0.090092}     # as in the original world: the floor slab's top at z = 0
# Furniture of the original world, kept where it does not enter the operating area (see OPERATING_AREA).
FURNITURE = [
    ('ShelfF_01', -5.795, -0.957, 0.0), ('ShelfE_01', 4.732, 0.579, 0.0), ('ShelfE_01', 4.732, -4.827, 0.0),
    ('ShelfE_01', 4.732, -8.665, 0.0),
    # the two ShelfD racks at y = -1.24 / -3.04 reach x = 2.77 and would touch shelter B at (3, -2): left out
    ('ShelfD_01', 4.732, -6.751, 0.0), ('DeskC_01', -0.062, 6.136, 0.0), ('DeskC_01', -0.062, 3.6, 0.0),
    ('DeskC_01', -0.062, -6.649, 0.0), ('Bucket_01', 0.433, 9.632, -1.563), ('Bucket_01', -1.832, -6.375, -1.563),
    ('ClutteringA_01', 5.708, 8.617, 0.0), ('ClutteringA_01', 3.409, 8.617, 0.0), ('ClutteringA_01', -1.491, 5.222, -1.583),
    ('ClutteringC_01', 3.325, 3.822, 1.564), ('ClutteringC_01', 5.542, 3.816, -1.583), ('ClutteringC_01', 5.384, 6.137, 3.15),
    ('ClutteringC_01', 3.236, 6.137, 3.15), ('ClutteringC_01', -1.2196, 9.407, 1.564), ('ClutteringD_01', -1.635, -7.812, 0.0),
    ('TrashCanC_01', -1.592, 7.715, 0.0),
]
# Movable clutter drawn per world near (behind / beside) the stations: in the camera's view, never in a corridor.
CLUTTER_SLOTS = [(-3.2, 3.0), (-2.9, 3.4), (3.2, 3.0), (2.9, 3.4), (-3.4, 1.6), (4.35, 1.9), (0.0, 2.9), (4.2, -2.6)]
CLUTTER_MODELS = ('Bucket_01', 'TrashCanC_01', 'ClutteringC_01')
# The operating area that the robot drives through (origin, the two station waypoints, the side poses, the shelter
# approach and the recovery leg between stations), with clearance.  Furniture whose footprint centre falls inside is
# dropped.
OPERATING_AREA = (-3.0, 4.0, -3.6, 2.6)          # x_min, x_max, y_min, y_max


# ---- I-21 phase 2: four supply bays -----------------------------------------------------------------------------------
# Station id -> (x, y, yaw) of the pallet (the 0.9 m x 0.9 m x 0.5 m platform of the arena).  W1 and M1 keep the arena's
# poses (and hand-tuned waypoints); W2 and M2 are new bays in the south-west and south aisles.  The inventory lists two
# water and two medicine stations; a scene variant may swap or empty any of them (build_variant depot['supply_at']).
K4_IDS = ('W1', 'M1', 'W2', 'M2')
K4_INVENTORY = {'W1': 'water', 'M1': 'medicine', 'W2': 'water', 'M2': 'medicine'}
K4_CENTERS = {'W1': (2.0, 2.0, 0.0), 'M1': (-2.0, 2.0, 0.0), 'W2': (-2.8, -1.4, 0.0), 'M2': (-0.2, -3.0, 0.0)}
K4_SHELTER = (3.0, -2.0, 0.0)
K4_WAYPOINTS = {'W1': (1.18, 1.13), 'M1': (-1.16, 1.10), 'W2': (-1.73, -0.86), 'M2': (-0.12, -1.80), 'B': (2.15, -1.12)}
OPERATING_AREA_K4 = (-4.2, 4.0, -4.4, 2.6)
# movable clutter for the four-bay depot: beside / behind the bays, in the camera's view, never in a corridor
CLUTTER_SLOTS_K4 = [(-3.7, 3.6), (-4.4, 2.6), (3.7, 3.6), (3.0, 4.6), (-4.7, 1.2), (-4.7, -2.4), (-4.5, 3.3), (4.35, 1.9),
                    (4.4, -3.9), (-1.5, -5.0), (1.4, -5.0), (-3.4, -4.9)]
# Collision footprints of the furniture models (half extents x, y at yaw 0, from the collision meshes, metres)
FOOTPRINT = {'ShelfD_01': (1.96, 0.44), 'ShelfE_01': (1.96, 0.44), 'ShelfF_01': (1.05, 9.02), 'DeskC_01': (0.44, 0.78),
             'Bucket_01': (0.47, 0.61), 'ClutteringA_01': (1.08, 1.0), 'ClutteringC_01': (0.89, 1.03),
             'ClutteringD_01': (0.51, 0.76), 'TrashCanC_01': (0.74, 0.45), 'PalletJackB_01': (0.58, 0.27)}


def operating_area(k: int = 2) -> tuple:
    return OPERATING_AREA_K4 if k == 4 else OPERATING_AREA


def available() -> bool:
    return (ASSETS / 'models' / f'{P}WallB_01' / 'model.sdf').is_file()


def _inside(x, y, area=OPERATING_AREA) -> bool:
    return area[0] <= x <= area[1] and area[2] <= y <= area[3]


def _model(name: str, inst: str, x: float, y: float, yaw: float, z: float = 0.0) -> ET.Element:
    src = ASSETS / 'models' / f'{P}{name}' / 'model.sdf'
    m = copy.deepcopy(ET.parse(src).getroot().find('model'))
    m.set('name', inst)
    pose = m.find('pose')
    if pose is None:
        pose = ET.SubElement(m, 'pose')
    pose.text = f'{x:g} {y:g} {z:g} 0 0 {yaw:g}'
    st = m.find('static')
    if st is None:
        st = ET.SubElement(m, 'static')
    st.text = 'true'
    for link in m.iter('link'):            # static props: drop the (partly invalid) inertia of the original models
        for inertial in link.findall('inertial'):
            link.remove(inertial)
    for el in m.iter():
        el.attrib.pop('frame', None)       # SDF 1.7+: the empty frame attribute is not defined
    for uri in m.iter('uri'):
        t = (uri.text or '').strip()
        if t.startswith('file://models/'):
            uri.text = 'file://' + str(ASSETS / t[len('file://'):])
        elif t.startswith('model://'):
            uri.text = 'file://' + str(ASSETS / 'models' / t[len('model://'):])
    return m


def placements(seed=None, obstacle: bool = False, k: int = 2, clutter: bool = True) -> list[tuple[str, str, float, float, float]]:
    """(model, instance name, x, y, yaw) for one depot world with k = 2 (arena) or 4 supply bays.  Deterministic for a seed.
    clutter=False (realism ablation, study XD) drops the movable clutter only; the random stream is unchanged, so the
    pallet jack and every other model keep their places."""
    area, slots = (OPERATING_AREA_K4, CLUTTER_SLOTS_K4) if k == 4 else (OPERATING_AREA, CLUTTER_SLOTS)
    out = [(n, f'depot_{n.lower()}_{i}', x, y, yaw) for i, (n, x, y, yaw) in enumerate(SHELL)]
    out += [(n, f'depot_{n.lower()}_f{i}', x, y, yaw) for i, (n, x, y, yaw) in enumerate(FURNITURE)
            if not _inside(x, y, area) and not (k == 4 and _blocks_k4(n, x, y, yaw))]
    rng = random.Random(f'depot-{seed}')
    for i, (x, y) in enumerate(rng.sample(slots, 4)):
        n = rng.choice(CLUTTER_MODELS)
        item = (n, f'depot_{n.lower()}_c{i}', round(x + rng.uniform(-.15, .15), 3), round(y + rng.uniform(-.15, .15), 3),
                round(rng.uniform(-math.pi, math.pi), 3))
        if clutter:
            out.append(item)
    if obstacle:
        out.append(('PalletJackB_01', 'depot_palletjack', -0.3, 4.2, round(rng.uniform(-.4, .4), 3)))
    return out


def add_depot(world: ET.Element, seed=None, obstacle: bool = False, k: int = 2, clutter: bool = True) -> list[str]:
    """Insert the depot models into a parsed <world>.  Returns the instance names (for the run record)."""
    if not available():
        raise FileNotFoundError(f'depot assets missing under {ASSETS}: run scripts/fetch_depot_assets.sh')
    names = []
    for n, inst, x, y, yaw in placements(seed, obstacle, k, clutter):
        world.append(_model(n, inst, x, y, yaw, Z.get(n, 0.0)))
        names.append(inst)
    ground = next((m for m in world.findall('model') if m.get('name') == 'ground'), None)
    if ground is not None:                      # the warehouse floor replaces the arena's grey plane (collision kept)
        for link in ground.findall('link'):
            for v in link.findall('visual'):
                link.remove(v)
    return names


# ---- k = 4 geometry ------------------------------------------------------------------------------------------------------
STATION_HALF = 0.45               # platform half side (0.9 m x 0.9 m)
SHELTER_HALF = (0.5, 0.4)         # shelter_B half extents (1.0 m x 0.8 m)
LOOK_AROUND_M = 0.4
CLEAR_PLATFORM_M = 0.5            # furniture / clutter must stay this far from a platform, the shelter and every leg
CLEAR_LEG_M = 0.6
CLUTTER_GAP_M = 0.1               # clutter may stand beside a platform (in the camera's view) but not overlap it


def k4_layout() -> dict:
    """{'centers': {id: (x, y, yaw)}, 'shelter': (x, y, yaw), 'waypoints': {id or 'B': (x, y)}} of the four-bay depot."""
    return {'centers': dict(K4_CENTERS), 'shelter': K4_SHELTER, 'waypoints': dict(K4_WAYPOINTS)}


def k4_station_set():
    from .stations import StationSet
    return StationSet.build(K4_IDS, K4_INVENTORY)


def _rect(x, y, yaw, hx, hy):
    return (x, y, yaw, hx, hy)


def k4_rects(layout: dict | None = None) -> dict:
    """Collision rectangles (x, y, yaw, half_x, half_y) of the four platforms and the shelter."""
    lay = layout or k4_layout()
    out = {i: _rect(*lay['centers'][i], STATION_HALF, STATION_HALF) for i in K4_IDS}
    out['B'] = _rect(*lay['shelter'], *SHELTER_HALF)
    return out


def k4_points(layout: dict | None = None, look_around: float = LOOK_AROUND_M) -> dict:
    """Every point the robot may drive to: start, the five waypoints and the L / R look-around points of each bay."""
    from .layout import look_around_points

    class _L:                                    # the two accessors look_around_points needs
        def __init__(self, lay): self.lay = lay
        def center(self, i): return tuple(self.lay['centers'][i][:2])
        def waypoint(self, i): return tuple(self.lay['waypoints'][i])
    lay = layout or k4_layout()
    pts = {'start': (0.0, 0.0), **{f'wp:{i}': tuple(lay['waypoints'][i]) for i in K4_IDS + ('B',)}}
    if look_around:
        for i in K4_IDS:
            for side, xy in look_around_points(_L(lay), i, look_around).items():
                pts[f'{side}:{i}'] = xy
    return pts


def k4_legs(layout: dict | None = None, look_around: float = LOOK_AROUND_M) -> list:
    """Every straight leg the controller may drive (there is no obstacle avoidance): start -> each bay, and all pairs of
    waypoints / look-around points, which covers a recovery search in ANY candidate order (memory / advice reorder),
    L-R-B ordering and the delivery leg.  (name, a, b, own objects)."""
    pts = k4_points(layout, look_around)
    owner = {k: k.split(':')[1] for k in pts if ':' in k}
    keys = [k for k in pts if k != 'start']
    legs = [(f'start->{k}', pts['start'], pts[k]) for k in keys if k.startswith('wp:')]
    for i, ka in enumerate(keys):
        legs += [(f'{ka}->{kb}', pts[ka], pts[kb]) for kb in keys[i + 1:]]
    return [(n, a, b, {owner.get(x) for x in n.split('->')} - {None}) for n, a, b in legs]


def _rect_radius(name: str) -> float:
    hx, hy = FOOTPRINT.get(name, (0.6, 0.6))
    return math.hypot(hx, hy)


def _min_dist_to_objects(rect, layout=None, look_around: float = LOOK_AROUND_M) -> float:
    """Smallest distance from a furniture rectangle (conservative: its bounding circle) to the platforms, the shelter
    and every leg."""
    from .layout import _dist_seg_rect, _dist_point_rect
    x, y, yaw, hx, hy = rect
    r = math.hypot(hx, hy)
    d = min(_dist_point_rect(x, y, o) for o in k4_rects(layout).values()) - r
    d_leg = min(_dist_seg_rect(a, b, _rect(x, y, yaw, hx, hy)) for _, a, b, _o in k4_legs(layout, look_around))
    return min(d, d_leg)


@functools.lru_cache(maxsize=None)
def _default_legs() -> tuple:
    return tuple(k4_legs())


@functools.lru_cache(maxsize=None)
def _blocks_k4(name: str, x: float, y: float, yaw: float) -> bool:
    """Furniture that comes closer than the clearances to a bay, the shelter or a leg of the four-bay depot is dropped."""
    from .layout import _dist_seg_rect, _dist_point_rect
    hx, hy = FOOTPRINT.get(name, (0.6, 0.6))
    rect = _rect(x, y, yaw, hx, hy)
    for o in k4_rects().values():                # rectangle vs rectangle (corner / edge samples of the platform)
        ox, oy, oyaw, ohx, ohy = o
        corners = [(ox + math.cos(oyaw) * sx * ohx - math.sin(oyaw) * sy * ohy,
                    oy + math.sin(oyaw) * sx * ohx + math.cos(oyaw) * sy * ohy) for sx in (-1, 0, 1) for sy in (-1, 0, 1)]
        if min(_dist_point_rect(cx, cy, rect) for cx, cy in corners) < CLEAR_PLATFORM_M:
            return True
    return min(_dist_seg_rect(a, b, rect) for _, a, b, _o in _default_legs()) < CLEAR_LEG_M


def check_k4_layout(layout: dict | None = None, *, look_around: float = LOOK_AROUND_M, seeds=range(20)) -> list[str]:
    """Violated constraints of the four-bay depot (empty = feasible), by pure geometry:
    * the Study L rules generalised to 4 bays (radius, bearings, separations, waypoint distances, yaw);
    * every leg keeps its clearance from every platform and the shelter (own endpoint 0.45 m, others 0.6 m);
    * the view line of each bay's waypoint to its centre is not blocked by another platform or the shelter;
    * no furniture or clutter placed in any depot world of `seeds` (with and without the aisle obstacle) comes within the
      clearances of a platform, the shelter or a leg."""
    from . import layout as L
    lay = layout or k4_layout()
    bad: list[str] = []
    c = {i: tuple(lay['centers'][i][:2]) for i in K4_IDS}
    wp = {i: tuple(lay['waypoints'][i]) for i in K4_IDS + ('B',)}
    names = list(K4_IDS) + ['B']
    cen = {**c, 'B': tuple(lay['shelter'][:2])}
    for i in K4_IDS:
        x, y = c[i]
        if abs(x) > L.X_MAX or abs(y) > L.Y_MAX:
            bad.append(f'{i}: centre outside the box')
        if not L.R_MIN <= math.hypot(x, y) <= L.R_MAX:
            bad.append(f'{i}: centre radius outside [{L.R_MIN}, {L.R_MAX}]')
        if abs(lay['centers'][i][2]) > L.YAW_MAX_RAD + 1e-9:
            bad.append(f'{i}: yaw beyond 45 deg')
    for n in names:
        if math.hypot(*wp[n]) < L.MIN_WAYPOINT_FROM_START_M:
            bad.append(f'{n}: waypoint closer than 1 m to the start')
    bearings = {n: math.atan2(cen[n][1], cen[n][0]) for n in names}
    for a_i, a in enumerate(names):
        for b in names[a_i + 1:]:
            d = abs(math.atan2(math.sin(bearings[a] - bearings[b]), math.cos(bearings[a] - bearings[b])))
            if d < L.MIN_ANGLE_RAD:
                bad.append(f'{a}/{b}: bearings closer than 40 deg')
            if math.dist(cen[a], cen[b]) < L.MIN_CENTER_SEP_M:
                bad.append(f'{a}/{b}: centres closer than {L.MIN_CENTER_SEP_M} m')
            if math.dist(wp[a], wp[b]) < L.MIN_WAYPOINT_SEP_M:
                bad.append(f'{a}/{b}: waypoints closer than {L.MIN_WAYPOINT_SEP_M} m')
    pts = k4_points(lay, look_around)
    for k, xy in pts.items():
        if k.startswith(('L:', 'R:')) and math.dist(xy, wp['B']) < L.MIN_WP_FROM_SHELTER_M + 0.2:
            bad.append(f'{k}: look-around point too close to the shelter waypoint')
    rects = k4_rects(lay)
    for name, a, b, own in k4_legs(lay, look_around):
        for n, rect in rects.items():
            need = L.MIN_OWN_CLEARANCE_M if n in own else L.MIN_LEG_CLEARANCE_M
            if L._dist_seg_rect(a, b, rect) < need:
                bad.append(f'leg {name}: within {need} m of {n}')
        for k, xy in pts.items():                # a leg must not pass over another waypoint (the audits use "near a waypoint")
            if k.startswith('wp:') and k.split(':')[1] not in own and name.split('->')[0] != k and name.split('->')[1] != k \
                    and L._dist_seg_point(a, b, xy) < 0.5:
                bad.append(f'leg {name}: within 0.5 m of {k}')
    from .robust_scenes import hazard_xy
    fires = {i: hazard_xy(i, stations=c) for i in K4_IDS}     # a fire behind any bay (default geometry) is off every leg
    for name, a, b, _own in k4_legs(lay, look_around):
        for i, xy in fires.items():
            if L._dist_seg_point(a, b, xy) - L.FIRE_RADIUS_M < L.MIN_LEG_CLEARANCE_M:
                bad.append(f'leg {name}: within {L.MIN_LEG_CLEARANCE_M} m of the fire at {i}')
    for i in K4_IDS:
        for n, rect in rects.items():
            if n != i and L._dist_seg_rect(wp[i], c[i], rect) < L.VIEW_CLEARANCE_M:
                bad.append(f'view {i}: line of sight passes within {L.VIEW_CLEARANCE_M} m of {n}')
    # furniture and clutter of the generated worlds
    legs = k4_legs(lay, look_around)
    for obstacle in (False, True):
        for seed in seeds:
            for n, inst, x, y, yaw in placements(seed, obstacle, 4):
                if n in ('WallB_01', 'GroundB_01'):
                    continue
                hx, hy = FOOTPRINT.get(n, (0.6, 0.6))
                if n in CLUTTER_MODELS:
                    hx = hy = max(hx, hy)        # clutter is rotated at random: use the bounding square
                rect = _rect(x, y, yaw, hx, hy)
                if n == 'PalletJackB_01':
                    continue                     # the aisle obstacle: in the north aisle, outside every leg (checked below)
                need = CLUTTER_GAP_M if n in CLUTTER_MODELS else CLEAR_PLATFORM_M
                for o in rects.values():
                    if min(L._dist_point_rect(o[0] + sx * o[3], o[1] + sy * o[4], rect) for sx in (-1, 0, 1) for sy in (-1, 0, 1)) \
                            < need - 1e-9:
                        bad.append(f'{inst}: within {need} m of a platform or the shelter')
                        break
                if min(L._dist_seg_rect(a, b, rect, step=0.05) for _, a, b, _o in legs) < CLEAR_LEG_M - 1e-9:
                    bad.append(f'{inst}: within {CLEAR_LEG_M} m of a leg')
    return sorted(set(bad))


DESIGN_SHORT_OF_WAYPOINT_M = 0.2     # as scripts/fire_mask_at_pose.py: the robot stops about 0.2 m short of the waypoint


def k4_design_pose(station: str, layout: dict | None = None, short: float = DESIGN_SHORT_OF_WAYPOINT_M) -> tuple:
    """Nominal checkpoint pose (x, y, yaw) of a bay of the four-bay depot: 0.2 m short of its waypoint on the line from the start,
    facing the pallet centre (the generalisation of scripts/fire_mask_at_pose.design_pose to the depot; the arena's
    median checkpoint pose of campaign D is 0.2 m short as well).  A design assumption until the first depot runs."""
    lay = layout or k4_layout()
    wx, wy = lay['waypoints'][station]
    cx, cy = lay['centers'][station][:2]
    n = math.hypot(wx, wy)
    px, py = wx - short * wx / n, wy - short * wy / n
    return (round(px, 3), round(py, 3), round(math.atan2(cy - py, cx - px), 3))


def k4_side_pose(station: str, offset: float, layout: dict | None = None) -> tuple:
    """Pose `offset` m to the side (offset < 0 left, > 0 right of the view direction) of the checkpoint pose, facing the centre
    (look-around views: +-0.4 m; wider views of the I-20 rule: +-0.8 m)."""
    lay = layout or k4_layout()
    x, y, _ = k4_design_pose(station, lay)
    cx, cy = lay['centers'][station][:2]
    n = math.hypot(cx - x, cy - y)
    vx, vy = -(cy - y) / n, (cx - x) / n
    px, py = x + offset * vx, y + offset * vy
    return (round(px, 3), round(py, 3), round(math.atan2(cy - py, cx - px), 3))


def k4_near_pose(station: str, near: float = 0.3, layout: dict | None = None) -> tuple:
    """The checkpoint pose moved `near` m towards the pallet centre (the 'N' view of the I-20 rule)."""
    lay = layout or k4_layout()
    x, y, yaw = k4_design_pose(station, lay)
    cx, cy = lay['centers'][station][:2]
    n = math.hypot(cx - x, cy - y)
    return (round(x + near * (cx - x) / n, 3), round(y + near * (cy - y) / n, 3), yaw)


def k4_configs(layout: dict | None = None) -> tuple[dict, dict]:
    """(waypoints_config, station_centers_config) of the four-bay depot, in the per-run format of rescuemind.stations:
    the arena's waypoint file with the station ids as keys (water / medicine replaced) plus the `stations` block."""
    import json
    lay = layout or k4_layout()
    base = json.loads((ROOT / 'configs/gazebo_waypoints.json').read_text(encoding='utf-8'))
    wp = {k: v for k, v in base.items() if k not in ('water', 'medicine', 'B', 'meaning')}
    for i in K4_IDS + ('B',):
        wp[i] = [float(v) for v in lay['waypoints'][i]]
    wp['meaning'] = base['meaning'] + ' (I-21 depot: four supply stations, the inventory lists the candidates)'
    wp['stations'] = k4_station_set().to_block()
    return wp, {i: [float(v) for v in lay['centers'][i][:2]] for i in K4_IDS}


def write_k4_configs(directory) -> tuple[Path, Path]:
    import json
    directory = Path(directory)
    wp, centers = k4_configs()
    a, b = directory / 'waypoints.json', directory / 'station_centers.json'
    a.write_text(json.dumps(wp, indent=2) + '\n', encoding='utf-8')
    b.write_text(json.dumps(centers, indent=2) + '\n', encoding='utf-8')
    return a, b


_PROP_OF = {'sealed_water_bottles': 'water', 'first_aid_case': 'medicine'}
_PLATFORM_AT = {'aid_station_water': 'W1', 'aid_station_medicine': 'M1'}


def supply_map(world: ET.Element, supply_at: dict | None = None) -> dict:
    """What each of the four pallets holds in a world built from a scenario SDF: W1 / M1 from the scenario's supply props
    (nominal / swapped / empty), W2 / M2 from the inventory, then `supply_at` ({id: 'water' | 'medicine' | None}) overrides."""
    out = dict(K4_INVENTORY)
    for i in ('W1', 'M1'):
        out[i] = None
    for m in world.findall('model'):
        if m.get('name') in _PROP_OF:
            px, py = [float(v) for v in m.findtext('pose').split()[:2]]
            for i in ('W1', 'M1'):
                if abs(px - K4_CENTERS[i][0]) < 0.01 and abs(py - K4_CENTERS[i][1]) < 0.01:
                    out[i] = _PROP_OF[m.get('name')]
    for i, v in (supply_at or {}).items():
        if i not in K4_IDS or v not in ('water', 'medicine', None):
            raise ValueError(f'bad supply_at entry {i!r}: {v!r}')
        out[i] = v
    return out


def add_k4_stations(world: ET.Element, supply_at: dict | None = None) -> tuple[dict, dict]:
    """Turn the arena scene into the four-bay depot scene: platforms W1 / M1 keep their place, platforms W2 / M2 are added,
    and the supply props are re-placed so that every pallet holds `supply_map(...)` (a pallet holding None stays empty).
    Returns ({id: (x, y)} centres, {id: supply or None})."""
    supply = supply_map(world, supply_at)
    props = {}
    for m in list(world.findall('model')):
        if m.get('name') in _PROP_OF:
            props[_PROP_OF[m.get('name')]] = (m.get('name'), copy.deepcopy(m))
            world.remove(m)
    plat = {_PLATFORM_AT[m.get('name')]: m for m in world.findall('model') if m.get('name') in _PLATFORM_AT}
    for i in ('W2', 'M2'):
        proto = plat['W1' if K4_INVENTORY[i] == 'water' else 'M1']
        new = copy.deepcopy(proto)
        new.set('name', f'aid_station_{i}')
        plat[i] = new
        world.append(new)
    used = set()
    for i in K4_IDS:
        x, y, yaw = K4_CENTERS[i]
        pose = plat[i].find('pose')
        pose.text = f'{x:g} {y:g} 0 0 0 {yaw:g}'
        if supply[i] is not None:
            name, proto = props[supply[i]]
            m = copy.deepcopy(proto)
            m.set('name', name if supply[i] not in used else f'{name}_{i}')
            used.add(supply[i])
            v = [float(t) for t in m.findtext('pose').split()]
            m.find('pose').text = f'{x:g} {y:g} {v[2]:g} {v[3]:g} {v[4]:g} {v[5] + yaw:g}'
            world.append(m)
    return {i: (K4_CENTERS[i][0], K4_CENTERS[i][1]) for i in K4_IDS}, supply


SMOKE_PNG = ROOT / 'worlds/assets/smoke_particle.png'


def smoke_texture() -> Path:
    """A soft grey puff (radial alpha falloff) used by the particle emitter; generated once."""
    if not SMOKE_PNG.is_file():
        from PIL import Image
        n = 128
        img = Image.new('RGBA', (n, n))
        px = img.load()
        for i in range(n):
            for j in range(n):
                r = math.hypot(i - n / 2, j - n / 2) / (n / 2)
                a = max(0.0, 1.0 - r) ** 1.6
                px[i, j] = (170, 170, 175, int(255 * a))
        SMOKE_PNG.parent.mkdir(parents=True, exist_ok=True)
        img.save(SMOKE_PNG)
    return SMOKE_PNG


def ensure_particle_plugin(world: ET.Element) -> None:
    if not any(p.get('filename') == 'gz-sim-particle-emitter-system' for p in world.findall('plugin')):
        world.insert(0, ET.Element('plugin', filename='gz-sim-particle-emitter-system',
                                   name='gz::sim::systems::ParticleEmitter'))


def particle_smoke(name: str, x: float, y: float, z: float = 0.9, rate: float = 12.0, scale: float = 1.0) -> ET.Element:
    """A rising, drifting smoke plume (Gazebo particle emitter).  Visual only: no collision, not in the fire masks."""
    m = ET.Element('model', name=name)
    ET.SubElement(m, 'static').text = 'true'
    ET.SubElement(m, 'pose').text = f'{x:g} {y:g} {z:g} 0 0 0'
    link = ET.SubElement(m, 'link', name='emitter_link')
    e = ET.SubElement(link, 'particle_emitter', name='smoke', type='box')
    for tag, val in (('emitting', 'true'), ('size', f'{.25 * scale:g} {.25 * scale:g} .05'),
                     ('particle_size', f'{.35 * scale:g} {.35 * scale:g} {.35 * scale:g}'), ('lifetime', '5'),
                     ('rate', f'{rate:g}'), ('min_velocity', '0.08'), ('max_velocity', '0.25'), ('scale_rate', '0.6'),
                     ('color_start', '0.35 0.35 0.37 0.75'), ('color_end', '0.55 0.55 0.57 0.0'),
                     ('pose', '0 0 0 0 -1.5708 0')):          # emit along +z (the emitter's +x points up)
        ET.SubElement(e, tag).text = val
    mat = ET.SubElement(e, 'material')
    ET.SubElement(mat, 'diffuse').text = '0.7 0.7 0.7 1'
    ET.SubElement(mat, 'specular').text = '0 0 0 1'
    metal = ET.SubElement(ET.SubElement(mat, 'pbr'), 'metal')
    ET.SubElement(metal, 'albedo_map').text = str(smoke_texture())
    return m


# ---- I-21 polish (study XD): pallets with wrapped cartons, smoke-only hazard, alternative flame appearances ----------------
# World-spec options (all default off; with them off, build_variant output is byte-identical to before):
#   depot = {'pallets': 'wood_cartons'}     the supply platforms look like wooden pallets carrying stretch-wrapped carton stacks;
#                                           VISUAL ONLY: the collision element and the xy footprint (0.9 m x 0.9 m) are unchanged
#   depot = {'clutter': False}              no movable clutter (realism ablation)
#   depot = {'hazard_style': ...}           how a world's hazard looks: None / 'tongues' = our ellipsoid flames + smoke (default),
#                                           'smoke_only' = smoke without flames (smouldering: static plume; a particle plume on
#                                           top if particle_smoke is on), 'mesh_flame' = jagged lofted flame meshes (not
#                                           ellipsoids), 'billboard' = crossed alpha-textured sprites (procedural texture)
PALLET_STYLES = (None, 'wood_cartons')
HAZARD_STYLES = (None, 'tongues', 'smoke_only', 'mesh_flame', 'billboard')
ASSET_DIR = ROOT / 'worlds/assets/generated'      # generated meshes / textures (git-ignored with the other assets)
PALLET_H = 0.14                    # wooden pallet height; the wrapped carton plinth fills the rest up to the platform top
PLATFORM_TOP = 0.5
MASK_RGB = '1 0 1 1'               # flat magenta label colour (robust_scenes.MASK_RGB)


def depot_options(depot: dict | None) -> dict:
    """Validated realism options of a depot spec (ValueError on an unknown value)."""
    d = depot or {}
    if d.get('pallets') not in PALLET_STYLES:
        raise ValueError(f"depot['pallets'] must be one of {PALLET_STYLES}")
    if d.get('hazard_style') not in HAZARD_STYLES:
        raise ValueError(f"depot['hazard_style'] must be one of {HAZARD_STYLES}")
    return {'pallets': d.get('pallets'), 'clutter': bool(d.get('clutter', True)), 'hazard_style': d.get('hazard_style')}


def _hash(s: str) -> int:
    import hashlib
    return int(hashlib.sha256(s.encode()).hexdigest()[:12], 16) % 10 ** 8


def _pose_text(x, y, z, yaw=0.0) -> str:
    return f'{x:.4f} {y:.4f} {z:.4f} 0 0 {yaw:.4f}'


def _rgb(c, jitter=0.0, rng=None) -> str:
    return ' '.join(f'{min(1.0, max(0.0, v + (rng.uniform(-jitter, jitter) if (rng and jitter) else 0.0))):.3f}' for v in c) + ' 1'


def _box(link, name, x, y, z, sx, sy, sz, rgb, yaw=0.0, transparency=None, specular=None):
    from .robust_scenes import _visual
    v = _visual(link, name, _pose_text(x, y, z, yaw), f'<box><size>{sx:g} {sy:g} {sz:g}</size></box>', rgb,
                transparency=transparency)
    if specular:
        ET.SubElement(v.find('material'), 'specular').text = specular
    return v


def pallet_visuals(link: ET.Element, back: tuple, rng: random.Random, avoid=()) -> None:
    """Add the visuals of a wooden pallet carrying a stretch-wrapped carton plinth (top at 0.5 m) and two small carton stacks
    standing on the top beside the supply, to `link` (the platform's link; platform-local frame; `back` = unit vector from the
    pallet to the wall behind it; `avoid` = local xy of objects standing on the top).  Everything stays inside the
    platform's 0.9 m x 0.9 m footprint."""
    wood = (0.72, 0.56, 0.34)
    for i, x in enumerate((-0.39, -0.195, 0.0, 0.195, 0.39)):            # deck boards
        _box(link, f'pallet_deck{i}', x, 0.0, PALLET_H - 0.01, 0.12, 0.90, 0.02, _rgb(wood, 0.04, rng))
    for i, x in enumerate((-0.39, 0.0, 0.39)):                           # bottom boards
        _box(link, f'pallet_bottom{i}', x, 0.0, 0.01, 0.12, 0.90, 0.02, _rgb(wood, 0.04, rng))
    for i, y in enumerate((-0.40, 0.0, 0.40)):                           # stringers
        _box(link, f'pallet_stringer{i}', 0.0, y, 0.075, 0.90, 0.09, 0.10, _rgb((0.60, 0.45, 0.27), 0.03, rng))
    layer_h = (PLATFORM_TOP - PALLET_H - 0.004) / 2
    for layer in range(2):                                               # two layers of 2 x 2 cartons
        for k, (cx, cy) in enumerate(((-0.22, -0.22), (0.22, -0.22), (-0.22, 0.22), (0.22, 0.22))):
            _box(link, f'plinth_carton{layer}{k}', cx, cy, PALLET_H + layer_h * (layer + 0.5), 0.43, 0.43, layer_h - 0.004,
                 _rgb((0.64, 0.47, 0.28), 0.05, rng))
    _box(link, 'stretch_wrap', 0.0, 0.0, PALLET_H + (PLATFORM_TOP - PALLET_H) / 2, 0.90, 0.90, PLATFORM_TOP - PALLET_H,
         '0.88 0.92 0.96 1', transparency=0.7, specular='0.9 0.9 0.9 1')
    spots = sorted(((sx * 0.30, sy * 0.30) for sx in (-1, 1) for sy in (-1, 1)), key=lambda c: -(c[0] * back[0] + c[1] * back[1]))
    spots = [c for c in spots if all(math.dist(c, a) >= 0.36 for a in avoid)][:2]      # corners nearest the wall, off a distractor
    for i, (cx, cy) in enumerate(spots):             # a 0.22 m carton turned by up to 0.4 rad still lies inside the footprint
        h = 0.20 if i == 0 else 0.17
        _box(link, f'top_carton{i}', cx, cy, PLATFORM_TOP + h / 2 + 0.002, 0.22, 0.22, h, _rgb((0.66, 0.49, 0.30), 0.05, rng),
             yaw=rng.uniform(-0.4, 0.4))
        _box(link, f'top_tape{i}', cx, cy, PLATFORM_TOP + h + 0.004, 0.05, 0.22, 0.004, '0.80 0.70 0.50 1')


def dress_platforms(world: ET.Element, depot: dict | None = None) -> list:
    """Replace the grey box visual of every supply platform (`aid_station_*`) by a wooden pallet with wrapped cartons.  The
    collision element is not touched, so footprints, audits and lidar behaviour are as before.  Returns the dressed names."""
    if not depot_options(depot)['pallets']:
        return []
    seed = (depot or {}).get('seed')
    done = []
    for m in world.findall('model'):
        name = m.get('name', '')
        link = m.find('link')
        if not name.startswith('aid_station_') or link is None or link.find("visual[@name='v']") is None:
            continue
        link.remove(link.find("visual[@name='v']"))
        v = [float(t) for t in m.findtext('pose').split()]
        x, y, yaw = v[0], v[1], v[5]
        n = math.hypot(x, y) or 1.0
        ux, uy = x / n, y / n                                            # 'behind the station' as seen from the start
        back = (ux * math.cos(yaw) + uy * math.sin(yaw), -ux * math.sin(yaw) + uy * math.cos(yaw))
        avoid = []
        for d in world.findall('model'):                                  # a distractor standing on this platform
            if d.get('name', '').startswith('distractor_'):
                dx, dy = [float(t) for t in d.findtext('pose').split()[:2]]
                lx, ly = dx - x, dy - y
                if abs(lx) < 0.8 and abs(ly) < 0.8:
                    avoid.append((lx * math.cos(yaw) + ly * math.sin(yaw), -lx * math.sin(yaw) + ly * math.cos(yaw)))
        pallet_visuals(link, back, random.Random(f'pallet-{seed}-{name}'), avoid)
        done.append(name)
    return done


# hazard styles --------------------------------------------------------------------------------------------------------
def _flatten_to_mask(link: ET.Element, only=None) -> None:
    """Label masks: the hazard visuals (all, or those whose name starts with `only`) flat emissive magenta, opaque, no shadows.
    The burnt-ground patch is not hazard and keeps its colour (as in robust_scenes masks)."""
    for v in list(link.findall('visual')):
        if v.get('name') == 'charred_base':
            continue                                                      # burnt ground stays as it is (not hazard)
        if only and not v.get('name', '').startswith(only):
            continue
        mat = v.find('material')
        if mat is None:
            mat = ET.SubElement(v, 'material')
        for child in list(mat):
            if child.tag in ('pbr', 'specular', 'double_sided'):
                mat.remove(child)
        for tag in ('ambient', 'diffuse', 'emissive'):
            el = mat.find(tag)
            if el is None:
                el = ET.SubElement(mat, tag)
            el.text = MASK_RGB
        if v.find('transparency') is not None:
            v.remove(v.find('transparency'))
        if v.find('cast_shadows') is None:
            ET.SubElement(v, 'cast_shadows').text = 'false'


def _hazard_shell(name: str, x: float, y: float, scale: float):
    from .robust_scenes import _visual
    m = ET.Element('model', name=name)
    ET.SubElement(m, 'static').text = 'true'
    ET.SubElement(m, 'pose').text = f'{x:g} {y:g} 0 0 0 0'
    link = ET.SubElement(m, 'link', name='fire')
    _visual(link, 'charred_base', f'0 0 {.02 * scale:.4f} 0 0 0',
            f'<cylinder><radius>{.40 * scale:.4f}</radius><length>.04</length></cylinder>', '.08 .07 .06 1')
    return m, link


def _puffs(link, scale, specs, prefix='smoke'):
    from .robust_scenes import _visual
    for k, (px, py, pz, r, rz, shade, tr) in enumerate(specs):
        _visual(link, f'{prefix}{k}', f'{px * scale:.4f} {py * scale:.4f} {pz * scale:.4f} 0 0 0',
                f'<ellipsoid><radii>{r * scale:.4f} {r * scale:.4f} {rz * scale:.4f}</radii></ellipsoid>', shade, transparency=tr)


def smoke_only_model(name: str, x: float, y: float, scale: float = 1.0, mask: bool = False) -> ET.Element:
    """A smouldering hazard: a rising grey plume of static puffs, thinner towards the top, and no flames (a dark burnt patch
    on the floor, which is not part of the label).  The static puffs are what the label masks count; the particle plume of
    the depot option `particle_smoke` is visual only on top."""
    m, link = _hazard_shell(name, x, y, scale)
    _puffs(link, scale, [(0.00, 0.00, 0.35, .26, .20, '.22 .22 .23 1', .30), (.05, .03, 0.62, .30, .24, '.27 .27 .28 1', .35),
                         (-.06, .02, 0.92, .36, .28, '.32 .32 .33 1', .40), (.08, -.04, 1.25, .42, .32, '.38 .38 .39 1', .48),
                         (-.05, .05, 1.60, .50, .36, '.45 .45 .46 1', .56), (.04, 0.0, 1.98, .58, .40, '.52 .52 .53 1', .66)])
    if mask:
        _flatten_to_mask(link)
    return m


def flame_mesh_path(seed, variant: int = 0) -> Path:
    """Write (once) and return a jagged flame mesh (OBJ with normals): 5-8 lofted tongues, each a tapering tube that leans and
    ends in a tip, so the silhouette is a ragged flame rather than an ellipsoid.  Deterministic for (seed, variant)."""
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = ASSET_DIR / f'flame_{_hash(f"{seed}-{variant}"):08d}.obj'
    if path.is_file():
        return path
    rng = random.Random(f'flame-mesh-{seed}-{variant}')
    verts, faces = [], []
    n_t, rings, segs = rng.randint(5, 8), 9, 10
    for t in range(n_t):
        a = 2 * math.pi * t / n_t + rng.uniform(-.3, .3)
        r0 = rng.uniform(.10, .17)
        height = 1.15 if t == 0 else rng.uniform(.75, 1.15)
        base = (0.0, 0.0) if t == 0 else (0.18 * math.cos(a), 0.18 * math.sin(a))
        lean = (0.0, 0.0) if t == 0 else (0.28 * math.cos(a) + rng.uniform(-.06, .06), 0.28 * math.sin(a) + rng.uniform(-.06, .06))
        phase = rng.uniform(0, 6.28)
        first = len(verts)
        for i in range(rings + 1):
            u = i / rings
            r = r0 * (1 - u) ** 0.9 * (1 + .25 * math.sin(5 * u + phase))
            cx, cy = base[0] + lean[0] * u * u + .05 * math.sin(7 * u + phase), base[1] + lean[1] * u * u
            for j in range(segs):
                th = 2 * math.pi * j / segs
                verts.append((cx + r * math.cos(th), cy + r * math.sin(th), height * u))
        for i in range(rings):
            for j in range(segs):
                a0, a1 = first + i * segs + j, first + i * segs + (j + 1) % segs
                faces += [(a0, a1, a1 + segs), (a0, a1 + segs, a0 + segs)]
    normals = [[0.0, 0.0, 0.0] for _ in verts]
    for f in faces:
        p = [verts[i] for i in f]
        u = [p[1][k] - p[0][k] for k in range(3)]
        w = [p[2][k] - p[0][k] for k in range(3)]
        nrm = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
        for i in f:
            for k in range(3):
                normals[i][k] += nrm[k]
    lines = ['# procedural flame (rescuemind.depot.flame_mesh_path)']
    lines += [f'v {x:.4f} {y:.4f} {z:.4f}' for x, y, z in verts]
    for nx, ny, nz in normals:
        d = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        lines.append(f'vn {nx / d:.4f} {ny / d:.4f} {nz / d:.4f}')
    lines += [f'f {a + 1}//{a + 1} {b + 1}//{b + 1} {c + 1}//{c + 1}' for a, b, c in faces]
    path.write_text('\n'.join(lines) + '\n')
    return path


_FLAME_SMOKE = [(0, 0, 1.35, .30, .22, '.18 .18 .19 1', .25), (.18, .10, 1.55, .38, .26, '.24 .24 .25 1', .25)]


def mesh_flame_model(name: str, x: float, y: float, scale: float = 1.0, mask: bool = False, seed=None) -> ET.Element:
    """Alternative flame (not our ellipsoid tongues): the jagged mesh three times, nested (translucent red outer shell, orange
    mid shell, bright core), plus two puffs of static smoke above it."""
    from .robust_scenes import _visual
    m, link = _hazard_shell(name, x, y, scale)
    uri = 'file://' + str(flame_mesh_path(seed))
    for k, (s, rgb, tr) in enumerate(((1.0, '.90 .12 .02 1', .35), (.72, '1 .50 .04 1', .10), (.42, '1 .90 .40 1', None))):
        _visual(link, f'flame{k}', '0 0 .03 0 0 0',
                f'<mesh><uri>{uri}</uri><scale>{s * scale:.4f} {s * scale:.4f} {s * scale:.4f}</scale></mesh>', rgb,
                emissive=rgb, transparency=tr)
    _puffs(link, scale, _FLAME_SMOKE)
    if mask:
        _flatten_to_mask(link)
    return m


def flame_sprite_path(seed, mask: bool = False, texture=None) -> Path:
    """The billboard texture: `texture` (a third-party PNG used as is; for the label sprite its alpha is the silhouette) or a
    procedural flame sprite with hard-edged alpha, so the magenta label sprite has exactly the same silhouette."""
    if texture and not mask:
        return Path(texture)
    import numpy as np
    from PIL import Image
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = ASSET_DIR / f'flame_sprite_{_hash(f"sprite-{seed}-{texture}"):08d}{"_mask" if mask else ""}.png'
    if path.is_file():
        return path
    if texture:
        alpha = np.asarray(Image.open(texture).convert('RGBA'))[..., 3] > 127
        h, w = alpha.shape
        v = 1 - np.mgrid[0:h, 0:w][0] / h
    else:
        rng = random.Random(f'flame-sprite-{seed}')
        w, h = 256, 384
        ph = [rng.uniform(0, 6.28) for _ in range(4)]
        yy, xx = np.mgrid[0:h, 0:w]
        v = 1 - yy / h                                                   # 0 at the bottom, 1 at the tip
        halfw = (0.46 * (1 - v) ** 0.7 + 0.04) * w / 2 * (1 + .30 * np.sin(9 * v + ph[0]) * v + .18 * np.sin(23 * v + ph[1]))
        centre = w / 2 + 0.16 * w * np.sin(3.2 * v + ph[2]) * v ** 1.3
        tongues = (np.abs(np.sin(5.5 * (xx - w / 2) / w * np.pi + ph[3])) > 0.56 * v) | (v < 0.35)
        alpha = (np.abs(xx - centre) < halfw) & (v < 0.97) & tongues
    rgba = np.zeros(alpha.shape + (4,), np.uint8)
    if mask:
        rgba[..., 0], rgba[..., 2] = 255, 255
    else:
        rgba[..., 0] = 255
        rgba[..., 1] = (70 + 185 * np.clip(v * 1.5, 0, 1) ** 1.2).astype(np.uint8)
        rgba[..., 2] = (10 + 140 * np.clip(v * 2.0 - .6, 0, 1)).astype(np.uint8)
    rgba[..., 3] = np.where(alpha, 255, 0)
    Image.fromarray(rgba, 'RGBA').save(path)
    return path


def billboard_flame_model(name: str, x: float, y: float, scale: float = 1.0, mask: bool = False, seed=None,
                          texture=None) -> ET.Element:
    """Alternative flame: three crossed double-sided planes with an alpha-textured, emissive flame sprite, plus two puffs of
    static smoke.  Needs the Gazebo smoke test (alpha textures), see docs/design/I21_realistic_depot.md."""
    m, link = _hazard_shell(name, x, y, scale)
    tex = flame_sprite_path(seed, mask, texture)
    w, h = 0.80 * scale, 1.20 * scale
    for k in range(3):
        v = ET.SubElement(link, 'visual', name=f'flame{k}')
        ET.SubElement(v, 'pose').text = _pose_text(0, 0, h / 2 + .03, k * math.pi / 3)
        v.append(ET.fromstring(f'<geometry><plane><normal>0 1 0</normal><size>{w:.4f} {h:.4f}</size></plane></geometry>'))
        mat = ET.SubElement(v, 'material')
        for tag in ('ambient', 'diffuse', 'emissive'):
            ET.SubElement(mat, tag).text = '1 1 1 1'
        ET.SubElement(mat, 'double_sided').text = 'true'
        metal = ET.SubElement(ET.SubElement(mat, 'pbr'), 'metal')
        ET.SubElement(metal, 'albedo_map').text = str(tex)
        ET.SubElement(metal, 'emissive_map').text = str(tex)
        ET.SubElement(v, 'cast_shadows').text = 'false'
    _puffs(link, scale, [(0, 0, 1.45, .30, .22, '.18 .18 .19 1', .25), (.18, .10, 1.65, .38, .26, '.24 .24 .25 1', .25)])
    if mask:                                  # sprites keep the magenta texture (same silhouette); the smoke puffs go flat
        _flatten_to_mask(link, only='smoke')
        for v in link.findall('visual'):
            if v.get('name', '').startswith('flame'):
                for tag in ('ambient', 'diffuse', 'emissive'):
                    v.find('material').find(tag).text = MASK_RGB
    return m


def restyle_hazard(world: ET.Element, name: str, style, scale: float = 1.0, mask: bool = False, seed=None, texture=None) -> bool:
    """Replace the default fire model `name` (already in `world`) by another look at the same place.  style None / 'tongues'
    leaves it alone.  Returns True if replaced."""
    if style in (None, 'tongues'):
        return False
    if style not in HAZARD_STYLES:
        raise ValueError(f'unknown hazard style {style!r}')
    old = next((m for m in world.findall('model') if m.get('name') == name), None)
    if old is None:
        raise KeyError(f'no hazard model {name!r} in the world')
    px, py = [float(t) for t in old.findtext('pose').split()[:2]]
    build = {'smoke_only': lambda: smoke_only_model(name, px, py, scale, mask),
             'mesh_flame': lambda: mesh_flame_model(name, px, py, scale, mask, seed),
             'billboard': lambda: billboard_flame_model(name, px, py, scale, mask, seed, texture)}[style]
    idx = list(world).index(old)
    world.remove(old)
    world.insert(idx, build())
    return True
