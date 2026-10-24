#!/usr/bin/env bash
# Visible background task (I-79, I-83): run this with Bash run_in_background whenever a GPU / campaign job runs, so the harness shows a background task and ITS END IS ANNOUNCED.
# It exits (-> task notification) when (1) scripts/idle_check.sh reports IDLE (the queue has finished), (2) a runner wrote an *_ABORT line into its log after this watcher started,
# or (3) a running job has made no progress for 45 minutes (GL ledger while run_campaign.py runs; QI manifest while qi_generate.py runs; judge scores while jev_score.py runs).
cd "$(dirname "$0")/.."
START=$(date +%s)
RES=experiments/results
stale() { # $1 = process pattern, $2 = progress file glob; stalled if the process runs and the newest progress file is older than 45 min
  pgrep -f "$1" >/dev/null || return 1
  age=$(ps -o etimes= -p "$(pgrep -f "$1" | head -1)" 2>/dev/null | tr -d ' '); [ "${age:-0}" -gt 2700 ] || return 1      # a job that started less than 45 min ago cannot be stalled (a false alarm at the start of QI-extension)
  newest=$(ls -t $2 2>/dev/null | head -1); [ -n "$newest" ] || return 1
  [ $(( $(date +%s) - $(stat -c %Y "$newest") )) -gt 2700 ]
}
declare -A BASE
for f in $RES/gl_run.log $RES/gm_run.log $RES/ji_run.log $RES/jk_run.log $RES/jl_run.log $RES/ih_run.log $RES/qi_run.log $RES/qj_run.log $RES/jh_stdout.log; do BASE[$f]=$(grep -c "_ABORT\|_FAIL" "$f" 2>/dev/null || true); BASE[$f]=${BASE[$f]:-0}; done     # markers already in a log at start are old news
while bash scripts/idle_check.sh >/dev/null 2>&1; do
  sleep 120
  for f in $RES/gl_run.log $RES/gm_run.log $RES/ji_run.log $RES/jk_run.log $RES/jl_run.log $RES/ih_run.log $RES/qi_run.log $RES/qj_run.log $RES/jh_stdout.log; do
    n=$(grep -c "_ABORT\|_FAIL" "$f" 2>/dev/null || true); n=${n:-0}
    if [ "$n" -gt "${BASE[$f]}" ]; then echo "FAILURE MARKER in $f: $(grep -h '_ABORT\|_FAIL' "$f" | tail -1)"; exit 0; fi
  done
  stale '^python3 scripts/run_campaign.py' "$RES/campaign_[GJ][LMK]_ledger.jsonl" && { echo "STALLED: the newest campaign ledger (GL/GM/JK) has not grown for 45 min while run_campaign.py runs"; exit 0; }
  stale 'qi_generate\.py' "$RES/qi_manifest_*.jsonl" && { echo "STALLED: no new Qwen-Image output for 45 min"; exit 0; }
  stale 'qj_generate\.py' "$RES/qj_manifest_*.jsonl" && { echo "STALLED: no new QJ image for 45 min"; exit 0; }
  stale 'jev_score\.py' "$RES/jev_scores_*.jsonl" && { echo "STALLED: no new judge score for 45 min"; exit 0; }
done
echo "QUEUE ENDED $(date '+%F %T'): no campaign or GPU job is running any more"
