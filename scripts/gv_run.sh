#!/usr/bin/env bash
# Study GV (wider look-around views with a calibrated threshold at the depot, fresh worlds; experiments/PREREGISTRATION_GV.md), full sequence.  Run from the MAIN checkout ONLY when no other
# campaign uses Gazebo / the GPU (it drives rm-next) and the depot assets are fetched (scripts/fetch_depot_assets.sh).
#   bash scripts/gv_run.sh                    # candidate masks -> selection + protocol (binding commit) -> pilot -> registration commit + OpenTimestamps
#                                             #   -> (wait for the Bitcoin attestation) -> campaign -> analysis
#   GV_OTS_WAIT=1 bash scripts/gv_run.sh      # wait for the Bitcoin attestation before the campaign (default: start once the stamp is submitted)
# Everything before the campaign uses no model score: the selection rule reads design fire masks only.  Resumable.
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9>/tmp/rescuemind_campaign.lock                       # one campaign at a time (the GC double launch, PREREGISTRATION_GC Note 4)
flock -n 9 || { echo "GV_ABORT: another campaign script holds /tmp/rescuemind_campaign.lock" >&2; exit 1; }
export PATH="$HOME/.local/bin:$PATH"
RES=experiments/results
CAND=experiments/campaign_gv_candidates.json
MASKS=experiments/campaign_gv_candidates_design_fire_masks.json
SEL=experiments/campaign_gv_selection.json
PROTO=experiments/campaign_gv_protocol.json
PILOT=experiments/campaign_gv_pilot_protocol.json
CALPROTO=experiments/campaign_gvk_protocol.json
IN_NEXT=(docker exec rm-next rescuemind-entrypoint)
abort() { echo "GV_ABORT: $*" >&2; exit 1; }
mkdir -p "$RES"
for f in experiments/PREREGISTRATION_GV.md "$CAND" "$PILOT" "$CALPROTO" experiments/gv_site_open.json scripts/make_protocol_gv.py scripts/gv_analysis.py scripts/gv_calibrate.py rescuemind/robust_scenes.py scripts/make_protocol_v34.py; do
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || abort "$f is not committed"
  git diff --quiet HEAD -- "$f" || abort "$f differs from the committed version"
done
"${IN_NEXT[@]}" true >/dev/null 2>&1 || abort "the container rm-next is not running"
for _ in $(seq 1 60); do curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1 || break; sleep 10; done
if curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; then abort "port 8765 is in use (another VLM server is running)"; fi

# (a) design masks of the candidates (the fire behind the requested station), selection and protocol: the BINDING commit, before any model score
if [ ! -s "$MASKS" ]; then
  "${IN_NEXT[@]}" python3 scripts/fire_mask_at_pose.py --protocol "$CAND" --design --design-sides 0.4 || abort "candidate masks"
fi
[ -s "$MASKS" ] || abort "candidate design masks missing"
if ! git log --format=%H -n1 --grep='^study GV: selection and protocol' | grep -q .; then
  python3 scripts/make_protocol_gv.py --select "$MASKS" || abort "selection"
  [ -s "$PROTO" ] || abort "no protocol (no eligible candidate)"
  git add "$MASKS" "$SEL" "$PROTO"
  git commit -q -m "study GV: selection and protocol (design masks of the candidates, no model score), before any GV trial

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$MASKS" "$SEL" "$PROTO" && git push -q || abort "binding commit failed"
fi
echo "GV_BINDING_COMMIT_DONE"
python3 scripts/make_protocol_gv.py >/dev/null && git diff --quiet HEAD -- "$PROTO" || abort "the protocol differs from its generator"

# (b0) calibrate the threshold for the 0.8 m views on 100 fire-free depot worlds of the GV generator (the mission with the threshold off), BEFORE the pilot and any GV trial.
#      Stop rule: tau_cal >= 0.05 (the depot cannot be calibrated below the default at alpha = 2%): GV is not run.
python3 scripts/make_protocol_gv.py >/dev/null && git diff --quiet HEAD -- "$CALPROTO" || abort "the calibration protocol differs from its generator"
if [ ! -f "$RES/gv_calibration_done" ]; then
  python3 scripts/ledger_stack_check.py --protocol "$CALPROTO" --ledger "$RES/campaign_GVK_ledger.jsonl" || abort "stale calibration ledger (see above)"
  for i in $(seq 1 60); do awk '{exit !($1 < 6)}' /proc/loadavg && break; sleep 60; done
  "${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$CALPROTO" --ledger "$RES/campaign_GVK_ledger.jsonl" 2>&1 | tee -a "$RES/campaign_GVK_stdout.log" | grep -E "^\[|trial|ERROR" | tail -3
  python3 scripts/gv_calibrate.py > "$RES/gv_calibrate_stdout.log"; CRC=$?
  git add "$RES/gv_calibration.json" "$RES/campaign_GVK_ledger.jsonl" experiments/gv_site_cal.json
  git commit -q -m "study GV: calibration (100 fire-free depot worlds, threshold off) and tau_cal, before any GV trial

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$RES/gv_calibration.json" "$RES/campaign_GVK_ledger.jsonl" experiments/gv_site_cal.json && git push -q || echo "GV_NOTE: nothing new to commit or push" >&2
  [ "$CRC" -eq 0 ] || abort "GV_STOP_RULE: the calibration stop rule applies (see $RES/gv_calibration.json); GV NOT started"
  touch "$RES/gv_calibration_done"
fi
echo "GV_CALIBRATION_DONE $(python3 -c "import json;print(json.load(open('experiments/gv_site_cal.json'))['hazard_threshold'])")"
python3 scripts/ledger_stack_check.py --protocol "$PILOT" --ledger "$RES/campaign_GV_pilot_ledger.jsonl" || abort "stale pilot ledger (see above)"

# (b) mechanics pilot (2 runs; STOPS unless the pilot behaves)
if [ ! -f "$RES/gv_pilot_ok" ]; then
  "${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PILOT" --ledger "$RES/campaign_GV_pilot_ledger.jsonl" 2>&1 | tail -20
  python3 scripts/gv_analysis.py --pilot || abort "pilot did not behave as designed; GV NOT started"
  touch "$RES/gv_pilot_ok"
fi
echo "GV_PILOT_OK"
if ! git log --format=%H -n1 --grep='^study GV: registration' | grep -q .; then
  git add "$RES/campaign_GV_pilot_ledger.jsonl" "$RES/gv_pilot_ok"
  git commit -q -m "study GV: registration (pilot ledger), before the first GV trial

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$RES/campaign_GV_pilot_ledger.jsonl" "$RES/gv_pilot_ok" && git push -q || echo "GV_NOTE: nothing new to commit or push" >&2
fi

# (c) external timestamp of the registration commit (hashes only), wait for the Bitcoin attestation
REG=$(git log --format=%H -n1 --grep='^study GV: registration')
mkdir -p docs/timestamps
STAMP=docs/timestamps/study_gv_registration.txt
if [ ! -f "$STAMP.ots" ]; then
  { echo "# study GV registration commit and the sha256 of its registered files (hashes only are sent to OpenTimestamps)"; echo "commit $REG";
    sha256sum experiments/PREREGISTRATION_GV.md "$PROTO" "$SEL" "$MASKS"; } > "$STAMP"
  ots stamp "$STAMP" >/dev/null 2>&1 || echo "GV_NOTE: ots stamp failed (no network?)" >&2
fi
if [ -n "${GV_OTS_WAIT:-}" ]; then               # Note (start rule as GC Note 3): the campaign starts once the stamp is submitted; set GV_OTS_WAIT=1 to wait for the attestation first
  ATT=0
  if [ -f "$STAMP.ots" ]; then
    for i in $(seq 1 480); do                     # up to 8 h, once a minute
      if ots upgrade "$STAMP.ots" 2>&1 | grep -q "Success"; then ATT=1; echo "GV_OTS_ATTESTED"; break; fi
      sleep 60
    done
  fi
  [ "$ATT" -eq 1 ] || abort "GV_OTS_NOT_ATTESTED: no Bitcoin attestation of the registration stamp; the paper may not claim an external ordering for GV"
fi
git add "$STAMP" "$STAMP.ots" 2>/dev/null; git commit -q -m "study GV: OpenTimestamps proof of the registration commit

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$STAMP" "$STAMP.ots" 2>/dev/null && git push -q || true

# (d) campaign (quiet host first)
python3 scripts/ledger_stack_check.py --protocol "$PROTO" --ledger "$RES/campaign_GV_ledger.jsonl" || abort "stale campaign ledger (see above)"
for i in $(seq 1 60); do awk '{exit !($1 < 6)}' /proc/loadavg && break; sleep 60; done
echo "GV_LOAD_AT_START $(cut -d' ' -f1-3 /proc/loadavg)"
"${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PROTO" --ledger "$RES/campaign_GV_ledger.jsonl" \
  2>&1 | tee -a "$RES/campaign_GV_stdout.log" | grep -E "^\[|trial|ERROR" | tail -5
[ "${PIPESTATUS[0]}" -eq 0 ] || abort "run_campaign.py failed (rerun resumes)"

# (e) analysis
python3 scripts/gv_analysis.py > "$RES/gv_analysis_stdout.log" || exit 1
echo "GV_DONE"
