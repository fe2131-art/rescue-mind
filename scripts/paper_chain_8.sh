#!/usr/bin/env bash
# T2 with Clef task wording (the selected I13*), then campaign G (registered).
cd "$(dirname "$0")/.."
pkill -f local_vlm_server; pkill -f clef_server; sleep 3
HF_HUB_OFFLINE=1 python3 scripts/clef_server.py --port 8767 > /tmp/clef_t2b.log 2>&1 &
until curl -s http://127.0.0.1:8767/health | grep -q ready; do sleep 3; done
[ -f experiments/results/devset_t2_clef2.json ] || python3 scripts/clef_devset_eval.py --schema task --devset experiments/vlm_testset_t2 --tag t2_clef2 >/dev/null 2>&1
pkill -f clef_server; sleep 5
python3 scripts/t2_analysis.py > experiments/results/t2_analysis_stdout.log 2>&1
echo T2B_DONE
python3 scripts/run_campaign.py --protocol experiments/campaign_g_protocol.json \
  --ledger experiments/results/campaign_G_ledger.jsonl > experiments/results/campaign_G_stdout.log 2>&1
python3 scripts/g_analysis.py > experiments/results/g_analysis_stdout.log 2>&1
echo CHAIN8_DONE
