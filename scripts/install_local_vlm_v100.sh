#!/usr/bin/env bash
# Run only on Ubuntu 24.04 with NVIDIA V100. Download stage requires internet.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[[ -r "$ROOT/.venv/bin/activate" ]] || { echo 'First run bash scripts/setup_ubuntu_jazzy.sh' >&2; exit 2; }
source "$ROOT/.venv/bin/activate"
python -m pip install -U 'pip>=26.2.2'
# CUDA 12.1 wheel: ensure nvidia-smi driver supports this runtime first.
python -m pip install 'torch==2.5.1' --index-url https://download.pytorch.org/whl/cu121
python -m pip install -e '.[local-v100]'
# The model snapshot is downloaded only here, NOT when a mission starts.
python - <<'PY'
from huggingface_hub import snapshot_download
from rescuemind.local_vision import PRIMARY_MODEL
print('Downloading', PRIMARY_MODEL)
print(snapshot_download(PRIMARY_MODEL))
PY
python scripts/local_gpu_preflight.py --mode single
printf '\nOPTIONAL dual local model: python -c "from huggingface_hub import snapshot_download; snapshot_download(\x27HuggingFaceTB/SmolVLM2-2.2B-Instruct\x27)"\n'
