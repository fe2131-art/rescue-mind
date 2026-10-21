#!/usr/bin/env bash
# Development pass GVD (I-70): one wide-view (0.8 m, threshold off) mission on each of GD's 40 fire worlds.  Not a study; nothing here is claimed.
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9>/tmp/rescuemind_campaign.lock
flock -n 9 || { echo "GVD_ABORT: another campaign script holds /tmp/rescuemind_campaign.lock" >&2; exit 1; }
export PATH="$HOME/.local/bin:$PATH"
RES=experiments/results
PROTO=experiments/campaign_gvd_protocol.json
python3 scripts/make_protocol_gvd.py >/dev/null && git diff --quiet HEAD -- "$PROTO" || { echo "GVD_ABORT: protocol differs from the committed one" >&2; exit 1; }
python3 scripts/ledger_stack_check.py --protocol "$PROTO" --ledger "$RES/campaign_GVD_ledger.jsonl" || exit 1
for i in $(seq 1 60); do awk '{exit !($1 < 6)}' /proc/loadavg && break; sleep 60; done
docker exec rm-next rescuemind-entrypoint python3 scripts/run_campaign.py --protocol "$PROTO" --ledger "$RES/campaign_GVD_ledger.jsonl" 2>&1 | tee -a "$RES/campaign_GVD_stdout.log" | grep -E "^\[|trial|ERROR" | tail -3
echo GVD_DONE
