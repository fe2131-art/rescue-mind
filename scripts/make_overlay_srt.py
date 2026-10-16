"""Create subtitle draft strictly from logged ROS mission events.

DO NOT treat subtitles as proof of robot motion: edit timing against the actual
recorded screen footage. No synthetic footage is created here.
"""
import argparse
import json
from pathlib import Path


def _clock(seconds):
    ms = max(0, int(round(float(seconds)*1000)))
    h, rest = divmod(ms, 3_600_000)
    m, rest = divmod(rest, 60_000)
    s, milli = divmod(rest, 1000)
    return f'{h:02}:{m:02}:{s:02},{milli:03}'


def from_log(data):
    if data.get('run_type') not in ('jev_qwen_mission', 'jev_qwen_live_mission'):
        raise ValueError('only Jev/Qwen live mission logs can produce evidence captions')
    captions=[]
    for ev in data.get('events', []):
        stage = ev.get('stage')
        label=None
        if stage == 'supply_station' and ev.get('arrived') is True:
            label='ロボットが物資拠点に到着（把持・積載はしていません）'
        elif stage=='checkpoint_frame':
            label='現地カメラ画像を取得しJev＋Qwenで再判定'
        elif stage=='checkpoint_decision':
            label=('Jev＋Qwenが物資を確認：次の移動を許可' if ev.get('allow') is True
                   else 'AI判定が一致せず停止（出発拒否）')
        elif stage == 'shelter_approach' and ev.get('arrived') is True:
            label='避難所への接近完了（物資の物理配送ではありません）'
        elif stage=='error':
            label='停止・実行中断（ログ記録）'
        if label:
            t=ev.get('t_wall_s')
            if not isinstance(t,(int,float)) or not 0<=t<=3600:
                raise ValueError('Missing or invalid event timestamp for '+str(stage))
            captions.append((float(t),label))
    if not captions:
        raise ValueError('no logged events to subtitle')
    if any(b[0]<a[0] for a,b in zip(captions,captions[1:])):
        raise ValueError('non-monotonic event timeline')
    return '\n\n'.join(f'{i}\n{_clock(t)} --> {_clock(t+4)}\n{label}' for i,(t,label) in enumerate(captions,1))+'\n'


def main():
    a=argparse.ArgumentParser()
    a.add_argument('--record',required=True)
    a.add_argument('--output',default='outputs/mission_overlay_draft.srt')
    args=a.parse_args()
    data=json.loads(Path(args.record).read_text(encoding='utf-8'))
    result=from_log(data)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(result,encoding='utf-8')
    print('SRT draft:',output,'(verify alignment with actual screen recording)')
if __name__=='__main__': main()
