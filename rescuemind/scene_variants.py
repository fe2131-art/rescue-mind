"""Controlled Gazebo scenes for on-site VLM counterfactual experiments.

Only the *identity or presence* of the physical-looking props is manipulated;
robot, sensing, waypoint coordinates, lighting, floor and collision stations are
identical across variants. The stations are neutral-grey to avoid label-color
shortcuts. This generates **test inputs**, never claims model accuracy.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

SCENES = ('nominal', 'swapped', 'empty')
PROPS = {'sealed_water_bottles': (2., 2.), 'first_aid_case': (-2., 2.)}
STATIONS = {'aid_station_water': (2., 2.), 'aid_station_medicine': (-2., 2.)}
STATION_COLORS = {'ambient': '.53 .55 .57 1', 'diffuse': '.53 .55 .57 1'}

class SceneContractError(ValueError):
    pass


def _model(world, name):
    matches=[m for m in world.findall('model') if m.get('name')==name]
    if len(matches)!=1:
        raise SceneContractError(f'expected exactly one {name} model')
    return matches[0]


def _xy_pose(model):
    pose=(model.findtext('pose') or '').split()
    if len(pose)!=6:
        raise SceneContractError('model pose must be six numbers')
    return float(pose[0]), float(pose[1])


def _neutralize_station(model):
    visuals=model.findall('./link/visual')
    if len(visuals)!=1:
        raise SceneContractError('station visual structure changed')
    material=visuals[0].find('material')
    if material is None:
        raise SceneContractError('station missing material')
    for tag, color in STATION_COLORS.items():
        node=material.find(tag)
        if node is None:
            raise SceneContractError('station missing '+tag)
        node.text=color


def _world(path):
    root=ET.parse(path).getroot()
    world=root.find('world')
    if root.tag!='sdf' or world is None or world.get('name')!='rescuemind_arena':
        raise SceneContractError('wrong SDF/world')
    return root,world


def _canonical(root):
    copied=copy.deepcopy(root)
    world=copied.find('world')
    for m in list(world.findall('model')):
        if m.get('name') in PROPS:
            world.remove(m)
    for el in copied.iter():
        if el.text is not None and not el.text.strip(): el.text=None
        el.tail=None
    return ET.tostring(copied,encoding='utf-8')


def build_scenarios(source: str | Path, destination: str | Path) -> dict:
    source=Path(source)
    dest=Path(destination)
    original, ref_world=_world(source)
    for name,xy in STATIONS.items():
        if _xy_pose(_model(ref_world,name))!=xy:
            raise SceneContractError('unexpected station pose '+name)
    for name,xy in PROPS.items():
        if _xy_pose(_model(ref_world,name))!=xy:
            raise SceneContractError('unexpected prop pose '+name)
    dest.mkdir(parents=True,exist_ok=True)
    report={'schema':'rescuemind_scene_variants_v1','source':str(source.name),'scenes':{}}
    invariants=[]
    for scenario in SCENES:
        root=copy.deepcopy(original)
        world=root.find('world')
        for name in STATIONS:
            _neutralize_station(_model(world,name))
        if scenario=='swapped':
            positions={'sealed_water_bottles':(-2.,2.), 'first_aid_case':(2.,2.)}
        elif scenario=='empty':
            positions={}
        else:
            positions=PROPS
        for name in PROPS:
            obj=_model(world,name)
            if name not in positions:
                world.remove(obj)
            else:
                old=(obj.findtext('pose') or '').split()
                x,y=positions[name]
                obj.find('pose').text=f'{x:g} {y:g} '+ ' '.join(old[2:])
        tree=ET.ElementTree(root)
        ET.indent(tree,space='  ')
        payload=ET.tostring(root,encoding='utf-8',xml_declaration=True)
        p=dest/f'rescuemind_{scenario}.sdf'
        p.write_bytes(payload)
        # All robot, obstacle and station geometry, sensors, physics, and lighting stay identical.
        invariants.append(hashlib.sha256(_canonical(root)).hexdigest())
        labels={'water':'water','medicine':'medicine'} if scenario=='nominal' else (
            {'water':'medicine','medicine':'water'} if scenario=='swapped' else
            {'water':'none','medicine':'none'})
        report['scenes'][scenario]={'sdf':p.name,'sha256':hashlib.sha256(payload).hexdigest(),
            'labels_by_station':labels,'scope':'SDF_MUTATION_NOT_RENDERING_OR_VLM_VERIFICATION'}
    if len(set(invariants))!=1:
        raise SceneContractError('scene non-prop parts changed across variants')
    report['non_prop_invariant_sha256']=invariants[0]
    (dest/'SCENES_MANIFEST.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    return report


def audit_scenarios(destination: str | Path) -> dict:
    dest=Path(destination)
    report=json.loads((dest/'SCENES_MANIFEST.json').read_text())
    signatures=[]
    for scene in SCENES:
        record=report['scenes'][scene]
        path=dest/record['sdf']
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=record['sha256']:
            raise SceneContractError('SDF hash mismatch '+scene)
        root,world=_world(path)
        for name in STATIONS:
            if _xy_pose(_model(world,name))!=STATIONS[name]:
                raise SceneContractError('station position changed '+scene)
        actual={name:_xy_pose(obj) for name in PROPS if (obj:=next((m for m in world.findall('model') if m.get('name')==name),None)) is not None}
        expected=PROPS if scene=='nominal' else (
            {'sealed_water_bottles':(-2.,2.),'first_aid_case':(2.,2.)} if scene=='swapped' else {})
        if actual!=expected:
            raise SceneContractError('supply prop placement changed '+scene)
        signatures.append(hashlib.sha256(_canonical(root)).hexdigest())
    if len(set(signatures))!=1 or signatures[0]!=report['non_prop_invariant_sha256']:
        raise SceneContractError('non-prop invariant mismatch')
    return {'pass':True,'scenes':len(SCENES),'scope':'SDF_STATIC_NO_GAZEBO_RENDER'}
