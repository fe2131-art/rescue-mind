#!/usr/bin/env bash
# Study QI (I-82): download Qwen-Image-2.1-Turbo with ONE curl writer per file (resumable) and verify every size against the hub listing.
#   bash scripts/fetch_qwen_image.sh
set -uo pipefail
M=Qwen/Qwen-Image-2.1-Turbo
D=$HOME/.cache/huggingface/jev_models/Qwen-Image-2.1-Turbo
mkdir -p "$D"
curl -s "https://huggingface.co/api/models/$M?blobs=true" | python3 -c "
import sys,json
for s in json.load(sys.stdin)['siblings']:
    if not s['rfilename'].startswith('assets/') and s['rfilename'] not in ('.gitattributes',): print(s['rfilename'], s.get('size') or 0)" > "$D/_files.txt"
while read -r f sz; do
  mkdir -p "$D/$(dirname "$f")"
  have=$(stat -c %s "$D/$f" 2>/dev/null || echo 0)
  if [ "$have" != "$sz" ]; then
    nice curl -L -s --retry 5 -C - -o "$D/$f" "https://huggingface.co/$M/resolve/main/$f"
  fi
  have=$(stat -c %s "$D/$f" 2>/dev/null || echo 0)
  [ "$have" = "$sz" ] && echo "OK $f $sz" || echo "BAD $f have=$have want=$sz"
done < "$D/_files.txt"
echo FETCH_DONE
