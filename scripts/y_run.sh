#!/usr/bin/env bash
# Study Y (continue after a hazard refusal in the four-bay depot; experiments/PREREGISTRATION_Y.md), full sequence.  Run from the MAIN
# checkout ONLY when no other campaign uses Gazebo / the GPU (it drives rm-next) and the depot assets are fetched (scripts/fetch_depot_assets.sh).
#   bash scripts/y_run.sh                     # pilot -> masks -> registration commit -> (wait for the OpenTimestamps attestation) -> campaign -> analysis
#   Y_NO_OTS_WAIT=1 bash scripts/y_run.sh     # skip the wait (only for a rehearsal)
# (a) mechanics pilot (4 runs; STOPS unless scripts/y_analysis.py --pilot passes)
# (b) design masks of the registered protocol, commit of protocol + masks + pilot ledger + registration text (BEFORE the first Y trial)
# (c) OpenTimestamps stamp of that commit's hash; the campaign waits until `ots upgrade` shows a Bitcoin attestation (the proof then
#     bounds the registration from above by a block time that precedes the first run)
# (d) the campaign (51 runs; resumable: a finished trial is skipped)   (e) analysis -> experiments/results/y_summary.json
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
RES=experiments/results
PROTO=experiments/campaign_y_protocol.json
PILOT=experiments/campaign_y_pilot_protocol.json
IN_NEXT=(docker exec rm-next rescuemind-entrypoint)
abort() { echo "Y_ABORT: $*" >&2; exit 1; }
mkdir -p "$RES"
[ -f worlds/assets/aws-wh/models/aws_robomaker_warehouse_WallB_01/model.sdf ] || abort "depot assets missing (scripts/fetch_depot_assets.sh)"
for f in experiments/PREREGISTRATION_Y.md "$PILOT" "$PROTO" scripts/make_protocol_y.py scripts/y_analysis.py rescuemind/hazard_continue.py; do
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || abort "$f is not committed"
  git diff --quiet HEAD -- "$f" || abort "$f differs from the committed version"
done
python3 scripts/make_protocol_y.py >/dev/null && git diff --quiet HEAD -- "$PROTO" || abort "the protocol differs from its generator"
"${IN_NEXT[@]}" true >/dev/null 2>&1 || abort "the container rm-next is not running"
for _ in $(seq 1 60); do curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1 || break; sleep 10; done
if curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; then abort "port 8765 is in use (another VLM server is running)"; fi
python3 scripts/ledger_stack_check.py --protocol "$PILOT" --ledger "$RES/campaign_Y_pilot_ledger.jsonl" || abort "stale pilot ledger (see above)"

# (a) pilot
if [ ! -f "$RES/y_pilot_ok" ]; then
  "${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PILOT" --ledger "$RES/campaign_Y_pilot_ledger.jsonl" 2>&1 | tail -20
  python3 scripts/y_analysis.py --pilot || { echo "Y_ABORT: pilot did not behave as designed; Y NOT started" >&2; exit 1; }
  touch "$RES/y_pilot_ok"
fi
echo "Y_PILOT_OK"

# (b) design masks of the registered protocol, then the registration commit
[ -s experiments/campaign_y_protocol_design_fire_masks.json ] || \
  "${IN_NEXT[@]}" python3 scripts/fire_mask_at_pose.py --protocol "$PROTO" --design --design-sides 0.4 || { echo "Y_ABORT: masks" >&2; exit 1; }
[ -s experiments/campaign_y_protocol_design_fire_masks.json ] || { echo "Y_ABORT: design fire masks missing" >&2; exit 1; }
if ! git log --format=%H -n1 --grep='^study Y: registration' | grep -q .; then
  git add experiments/campaign_y_protocol_design_fire_masks.json "$RES/campaign_Y_pilot_ledger.jsonl" "$RES/y_pilot_ok"
  git commit -q -m "study Y: registration (pilot ledger and design fire masks), before the first Y trial

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- experiments/campaign_y_protocol_design_fire_masks.json \
    "$RES/campaign_Y_pilot_ledger.jsonl" "$RES/y_pilot_ok" && git push -q || echo "Y_NOTE: nothing new to commit or push" >&2
fi
echo "Y_MASKS_DONE"

# (c) external timestamp of the registration commit (hashes only), wait for the Bitcoin attestation
REG=$(git log --format=%H -n1 --grep='^study Y: registration')
mkdir -p docs/timestamps
STAMP=docs/timestamps/study_y_registration.txt
if [ ! -f "$STAMP.ots" ]; then
  { echo "# study Y registration commit and the sha256 of its registered files (hashes only are sent to OpenTimestamps)"; echo "commit $REG";
    sha256sum experiments/PREREGISTRATION_Y.md "$PROTO" experiments/campaign_y_protocol_design_fire_masks.json; } > "$STAMP"
  ots stamp "$STAMP" >/dev/null 2>&1 || echo "Y_NOTE: ots stamp failed (no network?)" >&2
fi
if [ -z "${Y_NO_OTS_WAIT:-}" ]; then
  ATT=0
  if [ -f "$STAMP.ots" ]; then
    for i in $(seq 1 480); do                     # up to 8 h, once a minute
      if ots upgrade "$STAMP.ots" 2>&1 | grep -q "Success"; then ATT=1; echo "Y_OTS_ATTESTED"; break; fi
      sleep 60
    done
  fi
  # no attestation: the proof would not bound the first run from above, so the campaign does not start (rerun resumes here)
  [ "$ATT" -eq 1 ] || abort "Y_OTS_NOT_ATTESTED: no Bitcoin attestation of the registration stamp; the paper may not claim an external ordering for Y"
fi
git add "$STAMP" "$STAMP.ots" 2>/dev/null; git commit -q -m "study Y: OpenTimestamps proof of the registration commit

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$STAMP" "$STAMP.ots" 2>/dev/null && git push -q || true

# (d) campaign (quiet host first)
python3 scripts/ledger_stack_check.py --protocol "$PROTO" --ledger "$RES/campaign_Y_ledger.jsonl" || abort "stale campaign ledger (see above)"
for i in $(seq 1 60); do awk '{exit !($1 < 6)}' /proc/loadavg && break; sleep 60; done
echo "Y_LOAD_AT_START $(cut -d' ' -f1-3 /proc/loadavg)"
"${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PROTO" --ledger "$RES/campaign_Y_ledger.jsonl" \
  2>&1 | tee -a "$RES/campaign_Y_stdout.log" | grep -E "^\[|trial|ERROR" | tail -5
[ "${PIPESTATUS[0]}" -eq 0 ] || { echo "Y_ABORT: run_campaign.py failed (rerun resumes)" >&2; exit 1; }

# (e) analysis
python3 scripts/y_analysis.py > "$RES/y_analysis_stdout.log" || exit 1
echo "Y_DONE"
