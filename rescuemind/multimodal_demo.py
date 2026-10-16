"""Jev + Qwen3.5 preflight perception gate (requires REAL model services)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import hashlib
from . import jev, qwen35
from .safety import decide


def run(image: str, expected: str, qwen_model: str = qwen35.DEFAULT_MODEL,
        endpoint: str = qwen35.DEFAULT_ENDPOINT, corridor_image: str | None = None) -> dict:
    # Jev is a hard prerequisite. No fallback/permission without it.
    # Use two physically distinct observations: supply station and corridor.
    if not corridor_image:
        raise ValueError('Use --corridor-image: supply station and corridor require distinct camera observations')
    # A recycled image is not two independent observations. Compare decoded pixel data,
    # not file bytes, so re-encoding the same frame cannot pass unnoticed.
    from PIL import Image, ImageOps
    def digest(path):
        with Image.open(path) as im:
            a = ImageOps.exif_transpose(im).convert("RGB")
            return hashlib.sha256(str(a.size).encode()+a.tobytes()).hexdigest()
    if Path(image).resolve() == Path(corridor_image).resolve() or digest(image) == digest(corridor_image):
        raise ValueError("Supply and corridor must use different observations (identical decoded images)")
    supply_jev = jev.infer(image)
    supply_qwen = qwen35.infer(image, model=qwen_model, endpoint=endpoint)
    corridor_jev = jev.infer(corridor_image)
    corridor_qwen = qwen35.infer(corridor_image, model=qwen_model, endpoint=endpoint)
    j = {**supply_jev, 'scene': corridor_jev['scene'], 'hazard_probability': corridor_jev['hazard_probability'],
         'corridor_box': corridor_jev.get('box')}
    q = {**supply_qwen, 'scene': corridor_qwen['scene']}
    gate = decide(expected, j, q)
    return {'expected': expected, 'supply': {'jev': supply_jev, 'qwen': supply_qwen},
            'corridor': {'jev': corridor_jev, 'qwen': corridor_qwen}, 'gate': gate.to_dict(),
            'note': 'Two-snapshot preflight classification; no world coordinates, vehicle control or safety guarantee.'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--image", required=True, help="Actual Gazebo camera snapshot or a real photo")
    p.add_argument("--expected", choices=["water", "medicine"], required=True)
    p.add_argument("--corridor-image", required=True, help="Separate photo of the corridor for hazard check")
    p.add_argument("--qwen-model", default=qwen35.DEFAULT_MODEL)
    p.add_argument("--endpoint", default=qwen35.DEFAULT_ENDPOINT)
    p.add_argument("--output", default="outputs/real_multimodal_preflight.json")
    a=p.parse_args()
    try:
        result = run(a.image,a.expected,a.qwen_model,a.endpoint,a.corridor_image)
    except Exception as ex:
        result = {"gate": {"allow": False, "reason": "inference_failure"}, "error": f"{type(ex).__name__}: {ex}"}
    output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result["gate"]["allow"]:
        raise SystemExit(2)

if __name__=="__main__":main()
