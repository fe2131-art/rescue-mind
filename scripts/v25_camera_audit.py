#!/usr/bin/env python3
"""Static camera-pose/FOV self check; NO Gazebo or live VLM claim."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rescuemind.v25_projection import estimate_projection
from rescuemind.scene_variants import audit_scenarios
out={'static_scene_audit':audit_scenarios(ROOT/'worlds/scenarios'),
     'ideal_pinhole_projection':{s:estimate_projection(ROOT,s) for s in ('nominal','swapped','empty')},
     'scope':'STATIC_GEOMETRY_ONLY_NOT_GAZEBO_RENDERING_OR_VLM'}
for s in ('nominal','swapped'):
    for item in ('water','medicine'):
        assert out['ideal_pinhole_projection'][s]['objects'][item]['center_inside_fov_with_margin'], (s,item)
for item in ('water','medicine'):
    assert out['ideal_pinhole_projection']['empty']['objects'][item]['present'] is False
path=ROOT/'verification/v25/camera_projection.json';path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASS','path':str(path),'scope':out['scope']},ensure_ascii=False))
