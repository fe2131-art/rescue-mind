"""Create a simple static obstacle in an existing Gazebo Harmonic world.

This script uses the documented Gazebo /world/<name>/create service; no ROS imports.
Coordinates are Gazebo WORLD coordinates, not necessarily Nav2 MAP coordinates.
"""
import argparse
from pathlib import Path
import re
import subprocess
import uuid


def available_worlds(service_listing: str) -> list[str]:
    return sorted(set(re.findall(r'/world/([^\s/]+)/create(?:\s|$)', service_listing)))


def write_obstacle(path: Path, x: float, y: float, width: float = 0.7) -> Path:
    # Static non-movable box; center at z=width/2 to rest on ground.
    name = 'rescue_block_'+uuid.uuid4().hex[:10]
    contents=f'''<?xml version="1.0"?>
<sdf version="1.8">
  <model name="{name}">
    <static>true</static>
    <pose>{x:.6f} {y:.6f} {width/2:.6f} 0 0 0</pose>
    <link name="box">
      <collision name="collision"><geometry><box><size>{width} {width} {width}</size></box></geometry></collision>
      <visual name="visual">
        <geometry><box><size>{width} {width} {width}</size></box></geometry>
        <material><ambient>0.95 0.22 0.19 1</ambient><diffuse>0.95 0.22 0.19 1</diffuse></material>
      </visual>
    </link>
  </model>
</sdf>
'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents,encoding='utf-8')
    return path


def spawn(x: float, y: float, world: str = 'auto', width: float = 0.7,
          output_dir: str = 'outputs/obstacles') -> dict:
    listing=subprocess.run(['gz','service','-l'],capture_output=True,text=True,timeout=15,check=True)
    worlds=available_worlds(listing.stdout)
    if world=='auto':
        if len(worlds)!=1:
            raise RuntimeError(f'Expected exactly 1 running Gazebo world, found {worlds}; pass --world explicitly.')
        world=worlds[0]
    if world not in worlds:
        raise RuntimeError(f'World {world!r} does not offer /create. Available: {worlds}')
    path=Path(output_dir)/('block_'+uuid.uuid4().hex[:8]+'.sdf')
    write_obstacle(path,x,y,width)
    req=f'sdf_filename: "{path.resolve()}", name: "{path.stem}", allow_renaming: true'
    cmd=['gz','service','-s',f'/world/{world}/create',
         '--reqtype','gz.msgs.EntityFactory','--reptype','gz.msgs.Boolean',
         '--timeout','5000','--req',req]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=12)
    text=(r.stdout+' '+r.stderr).strip()
    if r.returncode!=0 or not re.search(r'\bdata:\s*true\b', text, flags=re.I):
        raise RuntimeError(f'Gazebo creation failed (exit {r.returncode}): {text}')
    return {'world':world, 'x':x, 'y':y, 'file':str(path), 'response':text}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--x',type=float,required=True)
    p.add_argument('--y',type=float,required=True)
    p.add_argument('--world',default='auto')
    p.add_argument('--width',type=float,default=0.7)
    a=p.parse_args()
    print(spawn(a.x,a.y,a.world,a.width))

if __name__=='__main__':
    main()
