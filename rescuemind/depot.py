"""I-21: dress the arena as a realistic relief depot (AWS RoboMaker small warehouse, MIT-0).

The warehouse models (walls, floor, shelves, desks, clutter, buckets, trash can, pallet jack) are placed AROUND the
operating area of the arena, so the station and shelter coordinates, the waypoints, the audits and the fire masks are
unchanged.  Every camera frame then carries realistic background clutter, shelves and occluders.  Clutter placement is
drawn per world (seed), and an optional pallet jack can block the aisle behind a station (an obstacle the robot sees but
whose corridor it never enters).

Assets are fetched once into worlds/assets/aws-wh (git-ignored; scripts/fetch_depot_assets.sh).  Models are inlined into
the world with absolute mesh paths, so no GZ_SIM_RESOURCE_PATH is needed.
"""
from __future__ import annotations
import copy
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
    ('ShelfE_01', 4.732, -8.665, 0.0), ('ShelfD_01', 4.732, -1.243, 0.0), ('ShelfD_01', 4.732, -3.039, 0.0),
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
    for uri in m.iter('uri'):
        t = (uri.text or '').strip()
        if t.startswith('file://models/'):
            uri.text = 'file://' + str(ASSETS / t[len('file://'):])
        elif t.startswith('model://'):
            uri.text = 'file://' + str(ASSETS / 'models' / t[len('model://'):])
    return m


def placements(seed=None, obstacle: bool = False) -> list[tuple[str, str, float, float, float]]:
    """(model, instance name, x, y, yaw) for one depot world.  Deterministic for a given seed."""
    out = [(n, f'depot_{n.lower()}_{k}', x, y, yaw) for k, (n, x, y, yaw) in enumerate(SHELL)]
    out += [(n, f'depot_{n.lower()}_f{k}', x, y, yaw) for k, (n, x, y, yaw) in enumerate(FURNITURE) if not _inside(x, y)]
    rng = random.Random(f'depot-{seed}')
    for k, (x, y) in enumerate(rng.sample(CLUTTER_SLOTS, 4)):
        n = rng.choice(CLUTTER_MODELS)
        out.append((n, f'depot_{n.lower()}_c{k}', round(x + rng.uniform(-.15, .15), 3), round(y + rng.uniform(-.15, .15), 3),
                    round(rng.uniform(-math.pi, math.pi), 3)))
    if obstacle:
        out.append(('PalletJackB_01', 'depot_palletjack', -0.3, 4.2, round(rng.uniform(-.4, .4), 3)))
    return out


def add_depot(world: ET.Element, seed=None, obstacle: bool = False) -> list[str]:
    """Insert the depot models into a parsed <world>.  Returns the instance names (for the run record)."""
    if not available():
        raise FileNotFoundError(f'depot assets missing under {ASSETS}: run scripts/fetch_depot_assets.sh')
    names = []
    for n, inst, x, y, yaw in placements(seed, obstacle):
        world.append(_model(n, inst, x, y, yaw, Z.get(n, 0.0)))
        names.append(inst)
    ground = next((m for m in world.findall('model') if m.get('name') == 'ground'), None)
    if ground is not None:                      # the warehouse floor replaces the arena's grey plane (collision kept)
        for link in ground.findall('link'):
            for v in link.findall('visual'):
                link.remove(v)
    return names


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
