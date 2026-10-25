#!/usr/bin/env bash
# After the memory demo is filmed: re-render the submission video with the memory demo, then sync the description.
cd "$(dirname "$0")/.."
until grep -q FILM_MEMORY_DONE "$1" 2>/dev/null; do sleep 60; done
MEM=$(awk '$1=="mem_verified" && ($3=="COMPLETED"){print $2}' experiments/results/film_memory_runs.txt | tail -1)
ARGS="--deliver dbed92419f88479e --recover b4fcd9d164444db7 --empty 367928c988f34e34 --hidden-fire 9d73663832c94f16"
[ -n "$MEM" ] && ARGS="$ARGS --memory $MEM" || echo "WARN: no completed memory run; rendering without the memory demo"
docker exec rm-dev rescuemind-entrypoint python3 scripts/make_video_plan.py $ARGS > experiments/results/video_plan_stdout.log 2>&1 || { echo PLAN_FAILED; exit 1; }
docker exec rm-dev rescuemind-entrypoint nice -n 19 python3 scripts/make_demo_video.py --plan docs/video_plan.json \
  --out outputs/video/PAI最終課題_141628.mp4 --narrate 2 > outputs/video/render_v4.log 2>&1 || { echo RENDER_FAILED; exit 1; }
python3 scripts/make_youtube_description.py
echo "RENDER_DONE mem=$MEM $(tail -1 outputs/video/render_v4.log)"
