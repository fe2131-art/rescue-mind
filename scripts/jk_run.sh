#!/usr/bin/env bash
# Study JK (suspicion-triggered extra views in the closed loop at the depot, on GM's worlds; experiments/PREREGISTRATION_JK.md), full sequence.  Run from the MAIN checkout ONLY when no other campaign uses
# Gazebo / the GPU (it drives rm-next; it takes the campaign lock and WAITS for it) and the depot assets are fetched.
#   bash scripts/jk_run.sh      # pilot (3 runs; STOPS unless the pilot behaves) -> registration commit + OpenTimestamps -> campaign (132 runs, about 7 h) -> analysis
# Resumable.  The worlds, their specs and the comparator arms are GM's: this script refuses to start if the GM ledger, the GM summary, the GM protocol or the GM selection differ from HEAD.
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9>/tmp/rescuemind_campaign.lock
flock 9
export PATH="$HOME/.local/bin:$PATH"
RES=experiments/results
PROTO=experiments/campaign_jk_protocol.json
PILOT=experiments/campaign_jk_pilot_protocol.json
IN_NEXT=(docker exec rm-next rescuemind-entrypoint)
abort() { echo "JK_ABORT: $*" >&2; exit 1; }
mkdir -p "$RES"
for f in experiments/PREREGISTRATION_JK.md "$PROTO" "$PILOT" scripts/make_protocol_jk.py scripts/jk_analysis.py scripts/jk_run.sh scripts/make_protocol_gm.py scripts/gm_analysis.py \
         experiments/campaign_gm_protocol.json experiments/campaign_gm_selection.json $RES/campaign_GM_ledger.jsonl $RES/gm_summary.json ros/gazebo_waypoint_mission.py rescuemind/adaptive_views.py; do
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || abort "$f is not committed"
  git diff --quiet HEAD -- "$f" || abort "$f differs from the committed version"
done
"${IN_NEXT[@]}" true >/dev/null 2>&1 || abort "the container rm-next is not running"
for _ in $(seq 1 60); do curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1 || break; sleep 10; done
if curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; then abort "port 8765 is in use (another VLM server is running)"; fi
python3 scripts/make_protocol_jk.py >/dev/null && git diff --quiet HEAD -- "$PROTO" "$PILOT" || abort "a protocol differs from its generator"
python3 scripts/ledger_stack_check.py --protocol "$PILOT" --ledger "$RES/campaign_JK_pilot_ledger.jsonl" || abort "stale pilot ledger (see above)"

# (a) mechanics pilot (3 runs: the large fire under the real arm; two fire-free worlds with the extra views FORCED, tau_sus 0)
if [ ! -f "$RES/jk_pilot_ok" ]; then
  "${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PILOT" --ledger "$RES/campaign_JK_pilot_ledger.jsonl" 2>&1 | tail -20
  python3 scripts/jk_analysis.py --pilot || abort "pilot did not behave as designed; JK NOT started"
  touch "$RES/jk_pilot_ok"
fi
echo "JK_PILOT_OK"
if ! git log --format=%H -n1 --grep='^study JK: registration' | grep -q .; then
  git add "$RES/campaign_JK_pilot_ledger.jsonl" "$RES/jk_pilot_ok"
  git commit -q -m "study JK: registration (pilot ledger), before the first JK trial

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$RES/campaign_JK_pilot_ledger.jsonl" "$RES/jk_pilot_ok" && git push -q || echo "JK_NOTE: nothing new to commit or push" >&2
fi

# (b) external timestamp of the registration commit (hashes only); the campaign starts once the stamp is submitted
REG=$(git log --format=%H -n1 --grep='^study JK: registration')
STAMP=docs/timestamps/study_jk_registration.txt
if [ ! -f "$STAMP.ots" ]; then
  { echo "# study JK registration commit and the sha256 of its registered files (hashes only are sent to OpenTimestamps)"; echo "commit $REG";
    sha256sum experiments/PREREGISTRATION_JK.md "$PROTO" "$PILOT" scripts/jk_analysis.py scripts/make_protocol_jk.py; } > "$STAMP"
  ots stamp "$STAMP" >/dev/null 2>&1 || echo "JK_NOTE: ots stamp failed (no network?)" >&2
fi
git add "$STAMP" "$STAMP.ots" 2>/dev/null; git commit -q -m "study JK: OpenTimestamps proof of the registration commit

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$STAMP" "$STAMP.ots" 2>/dev/null && git push -q || true

# (c) campaign (quiet host first)
python3 scripts/ledger_stack_check.py --protocol "$PROTO" --ledger "$RES/campaign_JK_ledger.jsonl" || abort "stale campaign ledger (see above)"
for i in $(seq 1 60); do awk '{exit !($1 < 6)}' /proc/loadavg && break; sleep 60; done
echo "JK_LOAD_AT_START $(cut -d' ' -f1-3 /proc/loadavg)"
"${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PROTO" --ledger "$RES/campaign_JK_ledger.jsonl" \
  2>&1 | tee -a "$RES/campaign_JK_stdout.log" | grep -E "^\[|trial|ERROR" | tail -5
[ "${PIPESTATUS[0]}" -eq 0 ] || abort "run_campaign.py failed (rerun resumes)"

# (d) analysis
python3 scripts/jk_analysis.py > "$RES/jk_analysis_stdout.log" || exit 1
echo "JK_DONE"
