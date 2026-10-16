"""I-05: domain-randomised Gazebo worlds for VLM robustness (dev) and hazard tests.

Built from the three controlled scenes (worlds/scenarios) by changing ONLY:
  * lighting  : sun direction / intensity / ambient (presets below)
  * distractor: a plain cardboard box placed on a supply platform (not a supply)
  * hazard    : visible fire (emissive flame primitives) + smoke next to a station
Robot, sensors, stations and waypoints are untouched.  Labels for scoring come
from the generator, never from the VLM.
"""
from __future__ import annotations
import json
import xml.etree.ElementTree as ET
from pathlib import Path

LIGHTING = {
    'default': None,
    'dim_evening': {'ambient': '0.45 0.42 0.40 1', 'direction': '0.6 -0.2 -0.45', 'intensity': '0.45',
                    'diffuse': '1.0 0.78 0.55 1'},
    'harsh_noon': {'ambient': '0.95 0.95 0.95 1', 'direction': '-0.1 0.05 -1', 'intensity': '1.3',
                   'diffuse': '1 1 1 1'},
}
STATIONS = {'water': (2.0, 2.0), 'medicine': (-2.0, 2.0)}


def _mat(rgb, emissive=None):
    m = ET.Element('material')
    for tag in ('ambient', 'diffuse'):
        ET.SubElement(m, tag).text = rgb
    if emissive:
        ET.SubElement(m, 'emissive').text = emissive
    return m


def _visual(link, name, pose, geom_xml, rgb, emissive=None, transparency=None):
    v = ET.SubElement(link, 'visual', name=name)
    ET.SubElement(v, 'pose').text = pose
    v.append(ET.fromstring(f'<geometry>{geom_xml}</geometry>'))
    v.append(_mat(rgb, emissive))
    if transparency is not None:
        ET.SubElement(v, 'transparency').text = str(transparency)
    return v


def cardboard_box(name, x, y, dx=0.0, dy=0.0):
    """A closed brown shipping box with tape — common at supply points, not a supply itself."""
    m = ET.Element('model', name=name)
    ET.SubElement(m, 'static').text = 'true'
    ET.SubElement(m, 'pose').text = f'{x + dx:g} {y + dy:g} 0 0 0 0.35'
    link = ET.SubElement(m, 'link', name='box')
    _visual(link, 'carton', '0 0 .625 0 0 0', '<box><size>.34 .26 .25</size></box>', '.62 .45 .27 1')
    _visual(link, 'tape', '0 0 .751 0 0 0', '<box><size>.345 .06 .004</size></box>', '.80 .70 .50 1')
    return m


def plastic_crate(name, x, y, z=0.5, yaw=0.0):
    """Open blue plastic crate (held-out distractor: never seen during development)."""
    m = ET.Element('model', name=name)
    ET.SubElement(m, 'static').text = 'true'
    ET.SubElement(m, 'pose').text = f'{x:g} {y:g} {z:g} 0 0 {yaw:g}'
    link = ET.SubElement(m, 'link', name='crate')
    c = '.12 .32 .70 1'
    _visual(link, 'bottom', '0 0 .01 0 0 0', '<box><size>.40 .30 .02</size></box>', c)
    for k, (px, py, sx, sy) in enumerate([(.19, 0, .02, .30), (-.19, 0, .02, .30), (0, .14, .40, .02), (0, -.14, .40, .02)]):
        _visual(link, f'wall{k}', f'{px} {py} .11 0 0 0', f'<box><size>{sx} {sy} .20</size></box>', c)
    return m


def traffic_cone(name, x, y, z=0.0):
    """Orange traffic cone (held-out hazard confuser: orange but not fire)."""
    m = ET.Element('model', name=name)
    ET.SubElement(m, 'static').text = 'true'
    ET.SubElement(m, 'pose').text = f'{x:g} {y:g} {z:g} 0 0 0'
    link = ET.SubElement(m, 'link', name='cone')
    _visual(link, 'base', '0 0 .015 0 0 0', '<box><size>.36 .36 .03</size></box>', '.95 .38 .05 1')
    _visual(link, 'body', '0 0 .30 0 0 0', '<cone><radius>.14</radius><length>.54</length></cone>', '.98 .42 .06 1')
    _visual(link, 'band', '0 0 .34 0 0 0', '<cylinder><radius>.085</radius><length>.07</length></cylinder>', '.95 .95 .95 1')
    return m


PLATFORM_SIDE_M = 0.28


def platform_side_offset(station: str, side: float, dist: float = PLATFORM_SIDE_M) -> tuple[float, float]:
    """Offset across the approach direction (left/right in the checkpoint image) on a platform."""
    x, y = STATIONS[station]
    n = (x * x + y * y) ** .5
    return -y / n * side * dist, x / n * side * dist


def random_lighting(rng) -> dict:
    """Continuous lighting draw (held-out): sun azimuth/elevation, intensity, ambient, colour tint."""
    import math
    az, el = rng.uniform(-math.pi, math.pi), rng.uniform(math.radians(25), math.radians(85))
    warm = rng.uniform(0.0, 1.0)           # 0 = cool daylight, 1 = warm low sun
    amb = rng.uniform(0.35, 0.95)
    tint = (1.0, 1.0 - 0.22 * warm, 1.0 - 0.45 * warm) if warm > 0.5 else (0.88 + 0.24 * warm, 0.92 + 0.16 * warm, 1.0)
    return {'ambient': ' '.join(f'{amb * t:.3f}' for t in tint) + ' 1',
            'direction': f'{math.cos(el) * math.cos(az):.3f} {math.cos(el) * math.sin(az):.3f} {-math.sin(el):.3f}',
            'intensity': f'{rng.uniform(0.35, 1.35):.3f}',
            'diffuse': ' '.join(f'{t:.3f}' for t in tint) + ' 1'}


FIRE_STYLE = 'tongues'   # v2 (I-05): ellipsoid flame tongues; 'cylinders' = first version


def fire_and_smoke(name, x, y, style: str | None = None):
    """A fire behind the supply platform: flames rising above it + smoke column."""
    style = style or FIRE_STYLE
    m = ET.Element('model', name=name)
    ET.SubElement(m, 'static').text = 'true'
    ET.SubElement(m, 'pose').text = f'{x:g} {y:g} 0 0 0 0'
    link = ET.SubElement(m, 'link', name='fire')
    _visual(link, 'charred_base', '0 0 .02 0 0 0', '<cylinder><radius>.40</radius><length>.04</length></cylinder>',
            '.08 .07 .06 1')
    if style == 'cylinders':
        flames = [(0, 0, .45, .20, .90, '1 .30 .03 1'), (.16, .10, .40, .14, .80, '1 .45 .05 1'),
                  (-.15, .08, .38, .14, .76, '1 .40 .04 1'), (.05, -.16, .35, .13, .70, '1 .55 .08 1'),
                  (-.06, -.05, .78, .12, .55, '1 .70 .12 1'), (.08, .06, .95, .08, .45, '1 .85 .25 1'),
                  (0, 0, 1.12, .05, .30, '1 .95 .55 1')]
        for k, (fx, fy, fz, r, h, c) in enumerate(flames):
            _visual(link, f'flame{k}', f'{fx} {fy} {fz} 0 0 0',
                    f'<cylinder><radius>{r}</radius><length>{h}</length></cylinder>', c, emissive=c)
        smoke = [(0, 0, 1.30, .28), (.15, .10, 1.45, .32), (-.12, .06, 1.55, .35)]
        for k, (sx, sy, sz, r) in enumerate(smoke):
            _visual(link, f'smoke{k}', f'{sx} {sy} {sz} 0 0 0', f'<sphere><radius>{r}</radius></sphere>',
                    '.25 .25 .27 1', transparency=0.35)
        return m
    # flame tongues: wide red bases, orange bodies, slender yellow tips, slightly tilted
    import math
    tongues = []
    for k in range(9):
        a = 2 * math.pi * k / 9
        rx, ry = 0.20 * math.cos(a), 0.20 * math.sin(a)
        tongues += [(rx, ry, .30, .14, .14, .30, '.85 .10 .02 1', 0.10 * math.cos(a), 0.10 * math.sin(a)),
                    (rx * .8, ry * .8, .62, .10, .10, .32, '1 .45 .03 1', 0.15 * math.cos(a), 0.15 * math.sin(a)),
                    (rx * .55, ry * .55, .92, .06, .06, .26, '1 .80 .15 1', 0.20 * math.cos(a), 0.20 * math.sin(a))]
    tongues += [(0, 0, .55, .22, .22, .50, '1 .35 .02 1', 0, 0), (0, 0, 1.05, .09, .09, .35, '1 .92 .45 1', 0, 0)]
    for k, (fx, fy, fz, ax, ay, az, c, roll, pitch) in enumerate(tongues):
        _visual(link, f'flame{k}', f'{fx:.3f} {fy:.3f} {fz} {roll:.3f} {pitch:.3f} 0',
                f'<ellipsoid><radii>{ax} {ay} {az}</radii></ellipsoid>', c, emissive=c)
    for k, (sx, sy, sz, rx, rz, shade) in enumerate([(0, 0, 1.35, .30, .22, '.18 .18 .19 1'),
                                                     (.18, .10, 1.55, .38, .26, '.24 .24 .25 1'),
                                                     (-.15, .08, 1.75, .45, .30, '.30 .30 .31 1')]):
        _visual(link, f'smoke{k}', f'{sx} {sy} {sz} 0 0 0', f'<ellipsoid><radii>{rx} {rx} {rz}</radii></ellipsoid>',
                shade, transparency=0.2)
    return m


def hazard_xy(station: str, back: float = 0.75, lateral: float = 0.5) -> tuple[float, float]:
    x, y = STATIONS[station]
    # approach comes from the arena origin side; put the fire on the opposite side
    ux, uy = x / (x * x + y * y) ** .5, y / (x * x + y * y) ** .5
    vx, vy = -uy, ux   # lateral offset: beside the supplies in the image, not hidden behind them
    return x + back * ux + lateral * vx, y + back * uy + lateral * vy


FIRE_HALF_WIDTH_M = 0.40      # charred base radius; flames + smoke stay inside it laterally
CAMERA_HALF_HFOV = 0.525      # horizontal_fov 1.05 rad in the robot SDF


def hazard_visibility(station: str, hazard_at: str | None, pose_xy: tuple[float, float], yaw: float,
                      hazard_pos: tuple[float, float] | None = None) -> str:
    """Three-way label for the paper test set: 'visible' (whole fire inside the image),
    'hidden' (whole fire outside), 'ambiguous' (partly in view; excluded from primary metrics)."""
    import math
    if hazard_at != station:
        return 'hidden'
    fx, fy = hazard_pos or hazard_xy(hazard_at)
    dx, dy = fx - pose_xy[0], fy - pose_xy[1]
    bearing = abs(math.atan2(math.sin(math.atan2(dy, dx) - yaw), math.cos(math.atan2(dy, dx) - yaw)))
    extent = math.atan2(FIRE_HALF_WIDTH_M, math.hypot(dx, dy))
    if bearing + extent < CAMERA_HALF_HFOV:
        return 'visible'
    if bearing - extent > CAMERA_HALF_HFOV:
        return 'hidden'
    return 'ambiguous'


def hazard_visible(station: str, hazard_at: str | None, pose_xy: tuple[float, float], yaw: float,
                   half_fov: float = 0.50) -> bool:
    """Geometric visibility of the fire from a camera pose (bearing inside the horizontal FOV)."""
    import math
    if hazard_at != station:
        return False
    fx, fy = hazard_xy(hazard_at)
    bearing = math.atan2(fy - pose_xy[1], fx - pose_xy[0]) - yaw
    return abs(math.atan2(math.sin(bearing), math.cos(bearing))) < half_fov


def _platform_empty(world, x, y) -> bool:
    for m in world.findall('model'):
        if m.get('name') in ('sealed_water_bottles', 'first_aid_case'):
            px, py = [float(v) for v in m.findtext('pose').split()[:2]]
            if abs(px - x) < 0.01 and abs(py - y) < 0.01:
                return False
    return True


def build_variant(src: Path, *, lighting: str = 'default', distractor_at: str | None = None,
                  hazard_at: str | None = None, lighting_params: dict | None = None,
                  prop_offsets: dict | None = None, hazard_geom: tuple[float, float] | None = None,
                  distractor_kind: str = 'box', distractor_side: float = 1.0,
                  distractor_layout: str = 'world') -> bytes:
    """Controlled variants (dev sets, campaigns) and, with the extra keyword arguments,
    the continuously randomised held-out test worlds (T1)."""
    tree = ET.parse(src)
    world = tree.getroot().find('world')
    preset = lighting_params or LIGHTING[lighting]
    if preset:
        world.find('scene/ambient').text = preset['ambient']
        sun = world.find("light[@name='sun']")
        sun.find('direction').text = preset['direction']
        sun.find('intensity').text = preset['intensity']
        sun.find('diffuse').text = preset['diffuse']
    # which platforms are empty is decided from the scene definition, BEFORE any prop is moved
    # (T1 amendment 1: checking after the move made every platform with a moved supply look empty)
    empty_at = {st: _platform_empty(world, *xy) for st, xy in STATIONS.items()}
    if prop_offsets:
        # held-out: move/rotate each supply prop on its platform (dx, dy, yaw)
        for m in world.findall('model'):
            if m.get('name') in prop_offsets:
                dx, dy, dyaw = prop_offsets[m.get('name')]
                v = [float(t) for t in m.findtext('pose').split()]
                m.find('pose').text = f'{v[0] + dx:g} {v[1] + dy:g} {v[2]:g} {v[3]:g} {v[4]:g} {v[5] + dyaw:g}'
    if distractor_at:
        x, y = STATIONS[distractor_at]
        empty_platform = empty_at[distractor_at]
        if distractor_layout == 'platform':
            # campaign E: the distractor stands ON the supply platform (beside the supply when one is
            # there, centred when the platform is empty) so it is always in the checkpoint view and
            # never in the robot's corridor; the generator keeps the supply on the other half.
            ox, oy = (0.0, 0.0) if empty_platform else platform_side_offset(distractor_at, distractor_side)
            fx, fy = x + ox, y + oy
            obj = {'cone': lambda: traffic_cone(f'distractor_cone_{distractor_at}', fx, fy, 0.5),
                   'crate': lambda: plastic_crate(f'distractor_crate_{distractor_at}', fx, fy, 0.5, 0.4),
                   'box': lambda: cardboard_box(f'distractor_box_{distractor_at}', fx, fy)}[distractor_kind]()
            world.append(obj)
        elif distractor_kind == 'cone':
            world.append(traffic_cone(f'distractor_cone_{distractor_at}', x + 0.70 * distractor_side, y - 0.55))
        elif distractor_kind == 'crate':
            world.append(plastic_crate(f'distractor_crate_{distractor_at}', x, y, 0.5, 0.4) if empty_platform else
                         plastic_crate(f'distractor_crate_{distractor_at}', x + 0.70 * distractor_side, y - 0.45, 0.0, 0.4))
        else:
            box = cardboard_box(f'distractor_box_{distractor_at}', x, y)
            if not empty_platform:
                # beside the platform on the floor (never overlapping a supply prop)
                box.find('pose').text = f'{x + 0.05:g} {y - 0.80:g} -0.5 0 0 0.35'
            world.append(box)
    if hazard_at:
        # behind the platform on the far side from the approach: flames rise above the
        # platform into the checkpoint view, off the path and outside the lidar front zone
        world.append(fire_and_smoke(f'hazard_fire_{hazard_at}', *hazard_xy(hazard_at, *(hazard_geom or (0.75, 0.5)))))
    ET.indent(tree, space='  ')
    return ET.tostring(tree.getroot(), encoding='utf-8', xml_declaration=True)


def write_variant(scene_dir: Path, out_dir: Path, scene: str, **kw) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = '_'.join([scene, 'random' if kw.get('lighting_params') else kw.get('lighting', 'default')] +
                   ([f"box-{kw['distractor_at']}"] if kw.get('distractor_at') else []) +
                   ([f"fire-{kw['hazard_at']}"] if kw.get('hazard_at') else []))
    path = out_dir / f'rescuemind_{tag}.sdf'
    path.write_bytes(build_variant(scene_dir / f'rescuemind_{scene}.sdf', **kw))
    return path


def truth_for(scene: str, station: str, *, hazard_at: str | None = None) -> dict:
    supply = {'nominal': {'water': 'water', 'medicine': 'medicine'},
              'swapped': {'water': 'medicine', 'medicine': 'water'},
              'empty': {'water': 'other', 'medicine': 'other'}}[scene][station]
    return {'truth_supply': supply, 'truth_hazard': hazard_at == station}


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    p = write_variant(root / 'worlds/scenarios', root / 'worlds/robustness', 'nominal', hazard_at='water')
    print(json.dumps({'example': str(p)}))
