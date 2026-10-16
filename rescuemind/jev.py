"""TypeSafe Jev 1.14.0 image inference via documented System One HTTP API.

An API key and working network are mandatory. No simulated response is substituted.
References: https://docs.typesafe.ai/images ; https://docs.typesafe.ai/primitives/box
"""
from __future__ import annotations
import base64
import json
import os
from pathlib import Path
import urllib.request
import uuid
from typing import Any, Callable
from PIL import Image, ImageOps
from io import BytesIO
from math import isfinite

API_URL = "https://api.typesafe.ai/v1/systemone"
MODEL_ID = "jev-1.14.0" # Pinned; 'jev-latest' is not this version as of 2026-10-16.


def build_request(image_bytes: bytes, fmt: str = "jpeg", *, include_box: bool = True) -> dict:
    if fmt not in ("jpeg", "jpg", "png"):
        raise ValueError("unsupported Jev image type")
    reference = str(uuid.uuid4())
    request = {
        "model": MODEL_ID,
        "state": {"camera": reference, "task": "An indoor emergency aid supply station and its corridor"},
        "assets": {reference: {"type": "image", "format": fmt, "data_base64": base64.b64encode(image_bytes).decode("ascii")}},
        "questions": {
            "supply": {"type": "choice", "instructions": "Identify the clearest supply category present in `camera`. If absent or ambiguous choose other.",
                       "criteria": {"water": "Sealed bottled drinking water", "medicine": "First aid kit, medications or medical supplies", "other": "Neither supply visible or unsure"}},
            "visible_supply": {"type": "noul", "instructions": "Does `camera` clearly contain a real sealed water bottle or an identifiable first aid kit?"},
            "hazard": {"type": "noul", "instructions": "Does `camera` clearly show an unsafe passage with fire, smoke, debris, or an obstructed walkway?"},
            "scene": {"type": "choice", "instructions": "Is the visible passage blocked, apparently clear or impossible to determine from `camera`?",
                      "criteria": {"clear": "Clearly visible and unobstructed corridor", "hazard": "Visible blockage, flame, smoke or fallen rubble", "unknown": "Corridor not visible, occluded or uncertain"}},
        },
    }
    if include_box:
        request['questions']['location'] = {
            'type': 'box',
            'instructions': 'the most clearly visible water bottle or first aid kit in `camera`',
        }
    return request


def prepare_image(path: str | Path) -> bytes:
    with Image.open(path) as im:
        rgb = ImageOps.exif_transpose(im).convert("RGB")
        rgb.thumbnail((1024, 1024))
        if min(rgb.size) < 280 or rgb.width*rgb.height < 78_400:
            raise ValueError("Jev requires width and height >= 256 and area >= 78,400 px; use a larger frame")
        stream = BytesIO()
        rgb.save(stream, format="JPEG", quality=85)
        return stream.getvalue()


def parse_response(payload: dict, *, require_box: bool = True) -> dict:
    if payload.get("model") != MODEL_ID:
        raise ValueError(f"Unexpected Jev model version: {payload.get('model')}")
    answers = payload["answers"]
    supply = answers["supply"]
    scene = answers["scene"]
    hazard = answers["hazard"]
    visible_supply = answers["visible_supply"]
    location = answers.get("location") if require_box else None
    if (supply.get("type") != "choice" or scene.get("type") != "choice"
            or hazard.get("type") != "noul" or visible_supply.get("type") != "noul"
            or (require_box and (not isinstance(location, dict) or location.get("type") != "box"))):
        raise ValueError("Invalid Jev response types")
    label = supply["choice"]
    scene_label = scene["choice"]
    if label not in ("water", "medicine", "other") or scene_label not in ("clear", "hazard", "unknown"):
        raise ValueError("Out-of-vocabulary Jev decision")
    probability = float(hazard["noul"])
    confidence = float(supply["confidence"])
    supply_visible = float(visible_supply["noul"])
    if not isfinite(supply_visible) or not (0.0 <= supply_visible <= 1.0):
        raise ValueError("Invalid Jev visibility probability")
    if not all(isfinite(x) and 0 <= x <= 1 for x in (probability, confidence)):
        raise ValueError("Invalid Jev confidence/probability")
    coords = None
    box_conf = None
    if require_box:
        coords = location.get("box")
        if not isinstance(coords, dict) or not all(k in coords for k in ("left", "right", "top", "bottom")):
            raise ValueError("Malformed Jev bounding box")
        if (not all(isfinite(float(coords[k])) for k in ("left", "right", "top", "bottom"))
                or not (0 <= float(coords["left"]) < float(coords["right"]) <= 1
                        and 0 <= float(coords["top"]) < float(coords["bottom"]) <= 1)):
            raise ValueError("Invalid box coordinates")
        box_conf = float(location.get('confidence',0))
        if not isfinite(box_conf) or not 0 <= box_conf <= 1:
            raise ValueError('Invalid Jev Box confidence')
    return {"real_model": True, "model": MODEL_ID, "supply": label, "supply_confidence": confidence, "supply_present_probability": supply_visible,
            "scene": scene_label, "hazard_probability": probability,
            "box": ({k: float(coords[k]) for k in ("left", "top", "right", "bottom")}
                    if require_box and supply_visible >= 0.8 else None),
            "box_confidence": box_conf, "box_requested": require_box,
            "usage": payload.get("usage", {})}


def infer(image_path: str | Path, api_key: str | None = None,
          transport: Callable[[dict, dict], dict] | None = None,
          *, include_box: bool = True) -> dict:
    """Transport injection is for unit tests; default calls REAL Jev 1.14 endpoint."""
    key = api_key or os.environ.get("TYPESAFE_API_KEY")
    if not key:
        raise RuntimeError("TYPESAFE_API_KEY missing: Jev is mandatory; execution blocked")
    body = build_request(prepare_image(image_path), "jpeg", include_box=include_box)
    headers = {"Authorization": "Bearer " + key, "TypeSafe-Danger-Zone-Images": "true", "Content-Type": "application/json"}
    if transport is not None:
        result = transport(body, headers)
    else:
        request = urllib.request.Request(API_URL, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=35) as response:
            result = json.loads(response.read().decode("utf-8"))
    return parse_response(result, require_box=include_box)


def infer_checkpoint(image_path: str | Path, api_key: str | None = None,
                     transport: Callable[[dict, dict], dict] | None = None) -> dict:
    """Jev 1.14 image classification for positive AND missing-object scenes.

    Do not ask the experimental Box question until an object is established:
    a missing object has no valid bounding coordinates. The checkpoint gate
    remains fail-closed and Jev mandatory; localization is not proof of pickup
    or corridor safety. `infer` retains the separate optional Box diagnostic.
    """
    return infer(image_path, api_key=api_key, transport=transport, include_box=False)
