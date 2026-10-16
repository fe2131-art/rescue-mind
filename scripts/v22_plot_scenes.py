#!/usr/bin/env python3
"""Schematic of SDF model placement; NOT a Gazebo screenshot."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'worlds/scenarios/SCENES_MANIFEST.json').read_text())
fig,axes=plt.subplots(1,3,figsize=(11,3.3),sharex=True,sharey=True)
colors={'water':'#3977b7','medicine':'#aa5959','none':'#b0b0b0'}
for ax,scene in zip(axes,['nominal','swapped','empty']):
    ax.set_title(scene+' (schematic)')
    ax.scatter([0],[0],marker='^',s=85,c='black',label='robot start')
    ax.scatter([2.15],[-1.12],marker='*',s=160,c='#518153',label='shelter approach')
    for station,x in [('water',2.),('medicine',-2.)]:
        actual=manifest['scenes'][scene]['labels_by_station'][station]
        ax.scatter([x],[2],marker='s',s=300,c=colors[actual],edgecolors='black',zorder=3)
        ax.text(x,2.45,station+' shelf\n'+actual,ha='center',fontsize=8)
        ax.scatter([1.18 if station=='water' else -1.16],[1.13 if station=='water' else 1.1],marker='o',s=30,c='#333333')
    ax.set_xlim(-3.4,4.1);ax.set_ylim(-2.5,3.5)
    ax.set_aspect('equal',adjustable='box');ax.grid(alpha=.2)
    ax.set_xlabel('sim x [m]')
axes[0].set_ylabel('sim y [m]')
fig.suptitle('Controlled material-placement variants (SDF model positions only; no rendered frames)',fontsize=11)
fig.tight_layout(rect=[0,0,1,.88]); out=ROOT/'docs/V22_SCENE_SCHEMATIC.png'
fig.savefig(out,dpi=155,bbox_inches='tight')
print(out)
