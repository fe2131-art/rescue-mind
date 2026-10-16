"""Renders a labeled *offline grid prototype* video. Not ROS/Gazebo footage."""
from __future__ import annotations
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont
from .planner import rescue_grid
from .sim import START, STATIONS, SHELTERS, BLOCKAGE

W, H = 1024, 640
BG, PANEL, GRID, WALL = '#0b1020', '#17233b', '#26334b', '#58627b'
TEAL, AMBER, RED, BLUE, WHITE = '#54d5c4', '#ffbd5e', '#fa6c82', '#6aa5fa', '#edf4ff'


def load_font(size):
    for p in ('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def frame(run, index, history) -> Image.Image:
    img=Image.new('RGB',(W,H),BG)
    d=ImageDraw.Draw(img)
    title,big,normal,small=load_font(29),load_font(22),load_font(17),load_font(14)
    d.text((38,22),'RescueMind  |  OFFLINE GRID PROTOTYPE',font=title,fill=WHITE)
    d.text((38,66),'NOT Gazebo / NOT a physical robot / for algorithm verification only',font=small,fill=AMBER)
    dx,dy,s=36,118,26
    gw=24*s
    d.rounded_rectangle([dx-6,dy-6,dx+gw+6,dy+15*s+6],radius=12,fill=PANEL)
    g=rescue_grid()
    for y in range(g.height):
        for x in range(g.width):
            a,b=dx+x*s,dy+y*s
            d.rectangle([a+1,b+1,a+s-2,b+s-2],fill=WALL if (x,y) in g.walls else GRID)
    cur=history[index]
    active=any(st.event=='dynamic_blockage_added' for st in history[:index+1])
    if active:
        a,b=BLOCKAGE
        d.rectangle([dx+a*s+1,dy+b*s+1,dx+(a+1)*s-2,dy+(b+1)*s-2],fill=RED)
    trail=[st.position for st in history[:index+1] if st.event=='moved']
    if trail:
        points=[(dx+START[0]*s+s//2,dy+START[1]*s+s//2)]+[(dx+x*s+s//2,dy+y*s+s//2) for x,y in trail]
        if len(points)>1:
            d.line(points,fill=TEAL,width=4,joint='curve')
    for name,coord,c in [('W',STATIONS['water'],BLUE),('M',STATIONS['medicine'],AMBER),('A',SHELTERS['A'],TEAL),('B',SHELTERS['B'],TEAL)]:
        x,y=coord
        center=(dx+x*s+s//2,dy+y*s+s//2)
        d.ellipse((center[0]-10,center[1]-10,center[0]+10,center[1]+10),fill=c)
        d.text((center[0]-5,center[1]-10),name,font=small,fill=BG)
    rx,ry=cur.position
    center=(dx+rx*s+s//2,dy+ry*s+s//2)
    d.ellipse([center[0]-11,center[1]-11,center[0]+11,center[1]+11], fill='#ffffff',outline=TEAL,width=4)
    left=710
    d.text((left,134),'MISSION',font=big,fill=TEAL)
    for j,(lab,val) in enumerate([
        ('Supply',run.item.upper()),('Shelter',run.shelter),('Mode','ADAPTIVE' if run.replans else 'ROUTE'),
        ('Stage',cur.stage.upper()),('Event',cur.event),('Moved steps',str(sum(st.event=='moved' for st in history[:index+1]))),
        ('Replans',str(sum(st.event=='route_replanned' for st in history[:index+1]))),
    ]):
        y=185+j*52
        d.text((left,y),lab.upper(),font=small,fill='#9baec7')
        d.text((left,y+19),val,font=normal,fill=WHITE if j!=4 else AMBER)
    d.rectangle([36,584,988,595],fill=GRID)
    d.rectangle([36,584,36+int(952*(index+1)/len(history)),595],fill=TEAL)
    d.text((38,603),'Demonstration only: 4-neighbor A* + learned text classification, no robot dynamics.',font=small,fill='#9baec7')
    return img


def render(run, folder: Path, fps: int = 10, seconds: int = 17):
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    history=run.history
    frame(run,len(history)-1,history).save(folder/'grid_result.png')
    finalvideo=folder/'grid_prototype_preview.mp4'
    num_frames=fps*seconds
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24',
         '-s',f'{W}x{H}','-r',str(fps),'-i','-','-c:v','libx264','-crf','22','-preset','veryfast',
         '-pix_fmt','yuv420p','-movflags','+faststart',str(finalvideo)]
    try:
        p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    except FileNotFoundError as e:
        print('ffmpeg not found; PNG saved, MP4 omitted:',e)
        return
    assert p.stdin is not None
    for k in range(num_frames):
        idx=min(len(history)-1, int(k*len(history)/num_frames))
        p.stdin.write(frame(run,idx,history).tobytes())
    p.stdin.close()
    err=p.stderr.read().decode() if p.stderr else ''
    p.wait()
    if p.returncode != 0:
        raise RuntimeError('Video encoding failed: '+err)
    print('preview:',finalvideo)
