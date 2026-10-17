#!/usr/bin/env python3
"""Study S defence arm OCR-MASK: blank every detected text region of the S images before the usual OURS scoring.

  ~/.cache/rescuemind/venv-ocr/bin/python scripts/s_ocr_mask.py            # CPU only, no GPU, no server
  -> experiments/vlm_testset_s_ocrmask/{images/*.jpg, labels.jsonl (copy), ocr_boxes.json}

Detector: RapidOCR (Apache-2.0) with the PP-OCRv4 text *detection* model only (ONNX, 4.7 MB, CPU, language independent; it
finds CJK and Latin text alike).  Recognition is never run: this is "find the text-like regions and paint them out", not reading.
The package and its model live in a venv outside the repo (python3 -m venv ~/.cache/rescuemind/venv-ocr;
pip install rapidocr-onnxruntime pillow numpy opencv-python-headless).  Nothing here sees the labels or the sign's position.

Detected regions whose short side is more than 8% of the image height are not text lines and are left alone (listed in
`dropped_too_thick`).  Each remaining polygon is replaced by its padded axis-aligned box, filled with the median colour of a ring of pixels around it
(outside all boxes).  The image is detected at 2x upscale (the signs are small in a 640 x 480 frame) and the boxes are scaled back.
`ocr_boxes.json` keeps the boxes per image so that the analysis can report how many attack-sign images had a detected region.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
UPSCALE = 2                 # detect on a 2x image: sign text in the 640 x 480 frame is only 8-20 px high
PAD_FRAC = 0.35             # grow each box by this fraction of its height (min PAD_MIN px) on every side
PAD_MIN = 3
RING = 3                    # px of the surrounding ring that supplies the fill colour
BOX_THRESH = 0.3            # DB box score threshold (library default 0.5; lower = more sensitive, more false regions)
UNCLIP = 1.6                # DB unclip ratio (library default)
MAX_SHORT_SIDE_FRAC = 0.08  # a detected region whose SHORT side exceeds this fraction of the image height is not a text line (a flat
                            # coloured object, e.g. the fire or a red box, also triggers the detector) and is not blanked.  Fixed now,
                            # before any real S image was seen: the sign text lines in a 640 x 480 frame are 8-20 px high (< 38 px).
JPEG_QUALITY = 95
SRC = ROOT / 'experiments/vlm_testset_s'
DST = ROOT / 'experiments/vlm_testset_s_ocrmask'


def poly_to_box(poly, w: int, h: int, upscale: float = 1.0) -> tuple[int, int, int, int]:
    """Detector polygon (in detection-image pixels) -> padded integer box (x0, y0, x1, y1) in the original image, clipped."""
    pts = np.asarray(poly, dtype=float) / upscale
    x0, y0 = pts.min(axis=0)
    x1, y1 = pts.max(axis=0)
    pad = max(PAD_MIN, PAD_FRAC * (y1 - y0))
    return (int(max(0, np.floor(x0 - pad))), int(max(0, np.floor(y0 - pad))),
            int(min(w, np.ceil(x1 + pad))), int(min(h, np.ceil(y1 + pad))))


def fill_boxes(img: np.ndarray, boxes: list, ring: int = RING) -> np.ndarray:
    """Return a copy of img (H, W, 3 uint8) with every box filled by the per-channel median of the ring of pixels around it
    that lies outside ALL boxes (if the ring is empty, of the whole image outside the boxes; if none, mid grey)."""
    out = img.copy()
    h, w = img.shape[:2]
    inside = np.zeros((h, w), bool)
    for x0, y0, x1, y1 in boxes:
        inside[y0:y1, x0:x1] = True
    for x0, y0, x1, y1 in boxes:
        if x1 <= x0 or y1 <= y0:
            continue
        ring_mask = np.zeros((h, w), bool)
        ring_mask[max(0, y0 - ring):min(h, y1 + ring), max(0, x0 - ring):min(w, x1 + ring)] = True
        ring_mask &= ~inside
        px = img[ring_mask]
        if len(px) < 8:
            px = img[~inside]
        colour = np.median(px, axis=0) if len(px) else np.array([128, 128, 128])
        out[y0:y1, x0:x1] = colour.astype(img.dtype)
    return out


class Detector:
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        self.engine = RapidOCR(box_thresh=BOX_THRESH, unclip_ratio=UNCLIP)
        import rapidocr_onnxruntime
        self.version = getattr(rapidocr_onnxruntime, '__version__', 'unknown')
        model = Path(rapidocr_onnxruntime.__file__).parent / 'models/ch_PP-OCRv4_det_infer.onnx'
        self.model_sha256 = hashlib.sha256(model.read_bytes()).hexdigest() if model.is_file() else None

    def boxes(self, pil: Image.Image, with_dropped: bool = False):
        """Padded boxes of the text-line regions; with_dropped also returns the (unpadded) regions rejected as too thick."""
        w, h = pil.size
        big = pil.resize((w * UPSCALE, h * UPSCALE), Image.LANCZOS)
        res, _ = self.engine(np.asarray(big)[:, :, ::-1], use_det=True, use_cls=False, use_rec=False)
        kept, dropped = [], []
        for p in (res or []):
            pts = np.asarray(p, dtype=float) / UPSCALE
            short = float(min(np.ptp(pts[:, 0]), np.ptp(pts[:, 1])))
            if short > MAX_SHORT_SIDE_FRAC * h:
                dropped.append([int(pts[:, 0].min()), int(pts[:, 1].min()), int(pts[:, 0].max()), int(pts[:, 1].max())])
            else:
                kept.append(poly_to_box(p, w, h, UPSCALE))
        return (kept, dropped) if with_dropped else kept


def mask_image(det: Detector, pil: Image.Image) -> tuple[Image.Image, list, list]:
    pil = pil.convert('RGB')
    boxes, dropped = det.boxes(pil, with_dropped=True)
    if not boxes:
        return pil, [], dropped
    return Image.fromarray(fill_boxes(np.asarray(pil), boxes)), boxes, dropped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--src', default=str(SRC))
    ap.add_argument('--dst', default=str(DST))
    a = ap.parse_args(argv)
    src, dst = Path(a.src), Path(a.dst)
    rows = [json.loads(x) for x in (src / 'labels.jsonl').read_text().splitlines() if x.strip()]
    det = Detector()
    (dst / 'images').mkdir(parents=True, exist_ok=True)
    boxes_out, dropped_out, n_new = {}, {}, 0
    meta = {'detector': 'rapidocr-onnxruntime', 'version': det.version, 'det_model': 'ch_PP-OCRv4_det_infer.onnx',
            'det_model_sha256': det.model_sha256, 'upscale': UPSCALE, 'pad_frac': PAD_FRAC, 'pad_min_px': PAD_MIN, 'ring_px': RING,
            'max_short_side_frac': MAX_SHORT_SIDE_FRAC, 'box_thresh': BOX_THRESH, 'unclip_ratio': UNCLIP, 'jpeg_quality': JPEG_QUALITY}
    for r in rows:
        out_path = dst / r['image']
        pil = Image.open(src / r['image'])
        masked, boxes, dropped = mask_image(det, pil)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        masked.save(out_path, quality=JPEG_QUALITY)
        boxes_out[r['image']] = boxes
        if dropped:
            dropped_out[r['image']] = dropped
        n_new += 1
    shutil.copyfile(src / 'labels.jsonl', dst / 'labels.jsonl')      # same rows, same image names: the masked set is a drop-in devset
    (dst / 'ocr_boxes.json').write_text(json.dumps({'meta': meta, 'boxes': boxes_out, 'dropped_too_thick': dropped_out}, indent=1) + '\n')
    n_with = sum(1 for b in boxes_out.values() if b)
    print(f'masked {n_new} images, {n_with} with at least one text region, {sum(len(b) for b in boxes_out.values())} regions in total, '
          f'{sum(len(b) for b in dropped_out.values())} thick regions left alone')


if __name__ == '__main__':
    sys.exit(main())
