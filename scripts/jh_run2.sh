#!/usr/bin/env bash
# Study JH, second pass: InternVL3 failed in the first pass (a shard was corrupted by two curl writers and re-downloaded); resumable scoring, then the analysis again.
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
for i in $(seq 1 1440); do pgrep -f "[j]h_run.sh" >/dev/null || break; sleep 60; done
for i in $(seq 1 120); do pgrep -f "[c]url -L -s --retry 5 -o InternVL3" >/dev/null || break; sleep 30; done
for s in xd closed_loop; do
  flock /tmp/rescuemind_campaign.lock docker exec rm-next rescuemind-entrypoint bash -c "cd $PWD && HF_HUB_OFFLINE=1 python3 scripts/jev_score.py --judge internvl3 --set $s" >> experiments/results/jev_internvl3_${s}.log 2>&1 || echo "JH_FAIL internvl3 $s"
done
python3 scripts/jh_analysis.py > experiments/results/jh_stdout.log 2>&1
echo JH2_DONE
