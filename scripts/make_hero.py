#!/usr/bin/env python3
"""Pick a real Gazebo overview frame (robot at the checkpoint) + robot-camera inset as the hero image."""
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
run = ROOT / 'outputs/runs' / sys.argv[1]
m = json.loads((run / 'mission.json').read_text(encoding='utf8'))
t = m['mission_start_unix_ns'] + int(next(e for e in m['events'] if e['stage'] == 'checkpoint_frame')['t_wall_s'] * 1e9)
def nearest(folder):
    files = sorted((run / 'film' / folder).glob('*.jpg'), key=lambda f: abs(int(f.stem.split('_')[0]) - t))
    return Image.open(files[0]).convert('RGB')
film = nearest('film').resize((1440, 810), Image.LANCZOS)
robot = nearest('robot').resize((448, 336), Image.LANCZOS)
d = ImageDraw.Draw(film)
d.rectangle((1440 - 448 - 28, 810 - 336 - 28, 1440 - 20, 810 - 20), fill=(20, 26, 38))
film.paste(robot, (1440 - 448 - 24, 810 - 336 - 24))
out = ROOT / 'docs/figures/hero_gazebo.png'
film.save(out)
print(out)
