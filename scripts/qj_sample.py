#!/usr/bin/env python3
"""Study QJ (Amendment 1): the by-eye sample for the stop rule.  40 images per fire mode (NF, NB), drawn with random.Random('QJ-byeye-<mode>') from the generated images, are laid out on one sheet per mode
(`outputs/qj/byeye_<mode>.jpg`, 8 x 5, numbered 1-40, no gate score anywhere); the keys are in `experiments/results/qj_byeye_sample.json`.  The reader writes `experiments/results/qj_byeye.json`
({"NF": {"n": 40, "present": k, "absent_numbers": [...]}, "NB": {...}}) BEFORE any gate score of QJ is read: present = a fire (flames or fire-coloured glow with smoke) is visible in the frame.
"""
import json
import random
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/qj'
RES = ROOT / 'experiments/results'


def main():
    sample = {}
    for mode in ('NF', 'NB'):
        keys = sorted(json.loads(x)['key'] for x in (RES / f'qj_manifest_{mode}.jsonl').read_text().splitlines() if x.strip())
        pick = random.Random(f'QJ-byeye-{mode}').sample(keys, 40)
        sample[mode] = pick
        W, H = 320, 240
        sheet = Image.new('RGB', (W * 8, H * 5))
        for i, k in enumerate(pick):
            im = Image.open(OUT / mode / f'{k}.jpg').convert('RGB').resize((W, H))
            ImageDraw.Draw(im).text((4, 4), str(i + 1), fill=(255, 255, 0))
            sheet.paste(im, ((i % 8) * W, (i // 8) * H))
        sheet.save(OUT / f'byeye_{mode}.jpg', quality=88)
    (RES / 'qj_byeye_sample.json').write_text(json.dumps(sample, indent=1) + '\n')
    print('sheets written:', [str(OUT / f'byeye_{m}.jpg') for m in sample])


if __name__ == '__main__':
    main()
