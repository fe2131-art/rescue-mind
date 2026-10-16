"""Offline motion and clearance regression, not ROS or Gazebo."""
from pathlib import Path
import csv
import json
from rescuemind.waypoint import simulate_route
from rescuemind.arena_geometry import check_route
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/release';OUT.mkdir(parents=True,exist_ok=True)
config=json.loads((ROOT/'configs/gazebo_waypoints.json').read_text())
results={}
fig=None
try:
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.patches import Rectangle
 fig,ax=plt.subplots(figsize=(8,6))
 for name,x,y,w,h,c in [('water',2,2,.9,.9,'royalblue'),('medicine',-2,2,.9,.9,'coral'),('shelter B',3,-2,1,.8,'seagreen')]:
  ax.add_patch(Rectangle((x-w/2,y-h/2),w,h,facecolor=c,alpha=.22,edgecolor=c,linewidth=2))
  ax.text(x,y,name,ha='center',va='center',fontsize=9)
except ImportError:
 pass
for item,color in [('water','royalblue'),('medicine','coral')]:
 goals=[config[item],config['B']]
 motion=simulate_route(goals)
 clearance=check_route(goals)
 if not clearance['safe_in_approximation']:
  raise RuntimeError(f'static route clearance failed for {item}: {clearance}')
 results[item]={'motion':motion,'clearance':clearance}
 with (OUT/f'{item}_waypoint_trace.csv').open('w',newline='') as fp:
  writer=csv.DictWriter(fp,fieldnames=['stage','x','y','yaw']);writer.writeheader();writer.writerows(motion['trace'])
 if fig:
  xy=[(0,0)]+[(r['x'],r['y']) for r in motion['trace']]
  plt.plot([t[0] for t in xy],[t[1] for t in xy],label=f'{item}: math only',color=color,linewidth=1.5)
  for x,y in goals: plt.scatter(x,y,c=color,s=25)
(OUT/'v06_waypoint_regression.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
if fig:
 ax.set_aspect('equal');ax.set_xlim(-3.5,4);ax.set_ylim(-3,3.3)
 ax.grid(alpha=.24);ax.set_xlabel('x [m]');ax.set_ylabel('y [m]')
 ax.set_title('RescueMind idealized kinematic regression (NOT Gazebo)')
 ax.legend();fig.tight_layout();fig.savefig(OUT/'v06_waypoint_regression.png',dpi=165)
 plt.close(fig)
print(json.dumps({'math_routes_completed':list(results),'clearances':{k:r['clearance']['minimum_clearance_m'] for k,r in results.items()},'kind':'OFFLINE KINEMATIC ONLY'},indent=2))
