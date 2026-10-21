#!/usr/bin/env bash
# Study JH (experiments/PREREGISTRATION_JH.md): score XD and the closed-loop views with every judge, one at a time (a 8-9B judge does not fit next to the gate's 9B on the 32 GB V100), then analyse.
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
for i in $(seq 1 600); do pgrep -f "[r]un_campaign.py|[j]ev_score.py" >/dev/null || break; sleep 30; done
for j in smolvlm2 internvl3 idefics3 qwen3vl; do
  for s in xd closed_loop; do
    docker exec rm-next rescuemind-entrypoint bash -c "cd $PWD && HF_HUB_OFFLINE=1 python3 scripts/jev_score.py --judge $j --set $s" >> experiments/results/jev_${j}_${s}.log 2>&1 || echo "JH_FAIL $j $s"
  done
done
python3 scripts/jh_analysis.py > experiments/results/jh_stdout.log 2>&1
echo JH_DONE
