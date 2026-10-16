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


def hazard_xy(station: str) -> tuple[float, float]:
    x, y = STATIONS[station]
    # approach comes from the arena origin side; put the fire on the opposite side
    ux, uy = x / (x * x + y * y) ** .5, y / (x * x + y * y) ** .5
    vx, vy = -uy, ux   # lateral offset: beside the supplies in the image, not hidden behind them
    return x + 0.75 * ux + 0.5 * vx, y + 0.75 * uy + 0.5 * vy


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
                  hazard_at: str | None = None) -> bytes:
    tree = ET.parse(src)
    world = tree.getroot().find('world')
    preset = LIGHTING[lighting]
    if preset:
        world.find('scene/ambient').text = preset['ambient']
        sun = world.find("light[@name='sun']")
        sun.find('direction').text = preset['direction']
        sun.find('intensity').text = preset['intensity']
        sun.find('diffuse').text = preset['diffuse']
    if distractor_at:
        x, y = STATIONS[distractor_at]
        names = {m.get('name') for m in world.findall('model')}
        empty_platform = not ({'sealed_water_bottles', 'first_aid_case'} & names) or _platform_empty(world, x, y)
        box = cardboard_box(f'distractor_box_{distractor_at}', x, y)
        if not empty_platform:
            # beside the platform on the floor (never overlapping a supply prop)
            box.find('pose').text = f'{x + 0.05:g} {y - 0.80:g} -0.5 0 0 0.35'
        world.append(box)
    if hazard_at:
        x, y = STATIONS[hazard_at]
        # behind the platform on the far side from the approach: flames rise above the
        # platform into the checkpoint view, off the path and outside the lidar front zone
        world.append(fire_and_smoke(f'hazard_fire_{hazard_at}', *hazard_xy(hazard_at)))
    ET.indent(tree, space='  ')
    return ET.tostring(tree.getroot(), encoding='utf-8', xml_declaration=True)


def write_variant(scene_dir: Path, out_dir: Path, scene: str, **kw) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = '_'.join([scene, kw.get('lighting', 'default')] +
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
