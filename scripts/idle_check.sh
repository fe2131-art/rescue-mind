#!/usr/bin/env bash
# Idle guard (I-71): run this FIRST in every cron tick and before every report.  Exit 1 = nothing is running -> launch the next job of docs/GPU_QUEUE.md in this same turn.
#   bash scripts/idle_check.sh
pat='jev_score|jh_run|gl_run|qi_run|qi_generate|qj_run|qj_generate|fire_mask_at_pose|gm_run|ji_run|ig_run|ih_run|build_testset_ji|make_protocol_ji|ji_analysis|vlm_devset_eval|run_campaign\.py|gv[dk]?_run\.sh|gd_run\.sh|gc_run\.sh|local_vlm_server|gv_dev_prompts|v32_orchestrate'
procs=$(pgrep -fa "$pat" | grep -v -e pgrep -e idle_check | cut -c1-110)
gpu=$(nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader 2>/dev/null)
echo "load: $(cut -d' ' -f1-3 /proc/loadavg)   gpu: ${gpu:-n/a}"
if [ -n "$procs" ]; then echo "RUNNING:"; echo "$procs"; exit 0; fi
echo "IDLE: no campaign or GPU job is running. Launch the next job of docs/GPU_QUEUE.md NOW (same turn); small document fixes do not count as work."
exit 1
