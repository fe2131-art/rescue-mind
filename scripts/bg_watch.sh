#!/usr/bin/env bash
# Visible background task (I-79): run this with Bash run_in_background whenever a GPU / campaign job runs, so the harness shows a background task and its end is announced.
# It exits (-> task notification) when scripts/idle_check.sh reports IDLE, i.e. when the whole queue has finished.
cd "$(dirname "$0")/.."
while bash scripts/idle_check.sh >/dev/null 2>&1; do sleep 120; done
echo "QUEUE ENDED $(date '+%F %T'): no campaign or GPU job is running any more"
