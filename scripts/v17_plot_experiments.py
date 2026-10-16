#!/usr/bin/env python3
"""Plot OFFLINE SCRIPTED tracks; file labels prevent submission as real robot video."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'verification/v17'
fig,ax=plt.subplots(figsize=(8,5.3))
for title,code in [('Scripted ALLOW (complete)','nominal'),('Scripted DENY (stop at station)','ai_denied')]:
    r=json.loads((OUT/f'closed_loop_{code}.json').read_text())
    pts=r['trace'];ax.plot([0.]+[x['x'] for x in pts],[0.]+[x['y'] for x in pts],label=title,linewidth=2)
ax.scatter([0,1.18,2.15],[0,1.13,-1.12],marker='x',s=75)
for name,x,y in [('Start',0.,0.),('Supply',1.18,1.13),('Shelter B',2.15,-1.12)]:
    ax.annotate(name,(x,y),xytext=(5,5),textcoords='offset points')
ax.set_title('Scripted OFFLINE closed-loop — NOT actual Gazebo / Jev / Qwen')
ax.set_xlabel('Ideal x (m)');ax.set_ylabel('Ideal y (m)')
ax.axis('equal');ax.grid(True);ax.legend(loc='upper left')
fig.tight_layout();fig.savefig(OUT/'v17_scripted_closed_loop.png',dpi=140)
plt.close(fig)
print(OUT/'v17_scripted_closed_loop.png')
