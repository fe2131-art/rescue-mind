#!/usr/bin/env python3
"""Synthetic source-data figure, emphatically not a Gazebo recording."""
import json,sys,tempfile,math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from test_v19_causal_evidence import fixtures,ST

fig,ax=plt.subplots(figsize=(9.0,3.5))
with tempfile.TemporaryDirectory() as td:
    folder=Path(td)
    for condition,label in [('valid','Valid: stationary until AI permission'),
                            ('premature_movement','Rejected: moves while AI is deciding')]:
        _,trace=fixtures(folder,condition)
        records=[json.loads(s) for s in trace.read_text().splitlines()]
        odom=[r for r in records if r.get('kind')=='odom']
        x=[(r['wall_unix_ns']-1_800_000_000_000_000_000)/1e9 for r in odom]
        y=[math.hypot(r['x']-ST[0],r['y']-ST[1]) for r in odom]
        ax.plot(x,y,label=label)
ax.axvspan(8,12,alpha=.12,label='At station: AI waiting')
ax.axvline(12,linestyle='--',linewidth=1.2,label='Authorization time (12 s)')
ax.set_xlim(7,15);ax.set_ylim(-.05,1.1)
ax.set_title('Synthetic causal-check example — NOT live ROS / Gazebo / Jev / Qwen')
ax.set_xlabel('Time since simulated mission start (s)')
ax.set_ylabel('Distance from supply station (m)')
ax.grid(alpha=.25)
ax.legend(fontsize=8,loc='upper left')
fig.tight_layout()
out=ROOT/'verification/v19/v19_synthetic_causal_timeline.png';out.parent.mkdir(parents=True,exist_ok=True)
fig.savefig(out,dpi=175)
print(out)
