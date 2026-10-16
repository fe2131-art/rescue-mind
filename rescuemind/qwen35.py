"""Qwen3.5 VLM client for local vLLM OpenAI-compatible HTTP endpoint.

Model server is independently started on the user's NVIDIA GPU.
Official model card: https://huggingface.co/Qwen/Qwen3.5-4B
"""
from __future__ import annotations
import base64
import json
import os
from pathlib import Path
import re
import urllib.request
from urllib.parse import urlparse
from typing import Any, Callable
from .jev import prepare_image
from .streaming import accumulate_chat_chunks

DEFAULT_MODEL = "Qwen/Qwen3.5-4B"
DEFAULT_ENDPOINT = "http://127.0.0.1:8000/v1/chat/completions"


def make_request(image_bytes: bytes, model: str) -> dict:
    url = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode("ascii")
    return {"model": model, "max_tokens": 256, "temperature": 0.1,
            "messages": [{"role": "system", "content": "Classify camera observations conservatively. Output one JSON object only; unknown if unclear."},
                         {"role": "user", "content": [
                             {"type": "image_url", "image_url": {"url": url}},
                             {"type": "text", "text": 'Return exactly JSON with keys "supply" and "scene". supply must be water, medicine, or other; scene must be clear, hazard, or unknown. hazard means visible blocked passage, fire, smoke, debris; unknown means passage not visible or ambiguous. No explanations.'}
                         ]}]}


def parse_response(response: dict, requested_model: str) -> dict:
    server_model = response.get("model")
    if server_model not in (requested_model, requested_model.split("/")[-1]):
        raise ValueError(f"Unexpected model from vLLM: {server_model!r}")
    raw = response["choices"][0]["message"]["content"]
    if not isinstance(raw, str):
        raise ValueError("Qwen text response missing")
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I).strip()
    obj = json.loads(cleaned)
    if set(obj) != {"supply", "scene"} or obj["supply"] not in ("water", "medicine", "other") or obj["scene"] not in ("clear", "hazard", "unknown"):
        raise ValueError("Unexpected Qwen JSON schema or labels")
    return {"real_model": True, "model": server_model, **obj, "usage": response.get("usage", {})}


def infer(image_path: str | Path, model: str = DEFAULT_MODEL, endpoint: str = DEFAULT_ENDPOINT,
          transport: Callable[[dict], dict] | None = None) -> dict:
    req = make_request(prepare_image(image_path), model)
    if model == "qwen3.8-omni-flash":
        # Alibaba Cloud Model Studio (not a local downloadable model).
        # Workspace endpoint varies by region. No automatic cloud fallback.
        base_url = os.environ.get("DASHSCOPE_BASE_URL", "").rstrip("/")
        key = os.environ.get("DASHSCOPE_API_KEY", "")
        if not base_url or not key:
            raise RuntimeError("Qwen3.8 needs DASHSCOPE_BASE_URL and DASHSCOPE_API_KEY")
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".aliyuncs.com") or parsed.username or parsed.password:
            raise ValueError("DASHSCOPE_BASE_URL must be a genuine HTTPS *.aliyuncs.com workspace endpoint")
        endpoint = base_url + "/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + key}
        req.pop("temperature", None)
        req["reasoning_effort"] = "low"
        req["modalities"] = ["text"]  # Official Qwen3.8-Omni text-output Chat Completions contract
        req["stream"] = True
        req["stream_options"] = {"include_usage": True}
    else:
        if not endpoint.startswith("http://127.0.0.1:") and not endpoint.startswith("http://localhost:"):
            raise ValueError("Local Qwen API must be on loopback; qwen3.8 model uses DASHSCOPE_BASE_URL")
        headers = {"Content-Type": "application/json"}
        # Qwen3.5 supports non-thinking mode at the vLLM endpoint.
        req["chat_template_kwargs"] = {"enable_thinking": False}
    if transport is not None:
        response = transport(req)
    else:
        request = urllib.request.Request(endpoint, json.dumps(req).encode("utf-8"),
                                        headers, method="POST")
        with urllib.request.urlopen(request, timeout=120) as f:
            if model == "qwen3.8-omni-flash":
                response = accumulate_chat_chunks(f)
            else:
                response = json.loads(f.read().decode("utf-8"))
    return parse_response(response, model)
