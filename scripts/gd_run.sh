#!/usr/bin/env bash
# Study GD (per-site calibrated hazard threshold at the depot, fresh worlds; experiments/PREREGISTRATION_GD.md), full sequence.  Run from the MAIN checkout ONLY when no other
# campaign uses Gazebo / the GPU (it drives rm-next) and the depot assets are fetched (scripts/fetch_depot_assets.sh).
#   bash scripts/gd_run.sh                    # candidate masks -> selection + protocol (binding commit) -> pilot -> registration commit + OpenTimestamps
#                                             #   -> (wait for the Bitcoin attestation) -> campaign -> analysis
#   GD_OTS_WAIT=1 bash scripts/gd_run.sh      # wait for the Bitcoin attestation before the campaign (default: start once the stamp is submitted)
# Everything before the campaign uses no model score: the selection rule reads design fire masks only.  Resumable.
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9>/tmp/rescuemind_campaign.lock                       # one campaign at a time (the GC double launch, PREREGISTRATION_GC Note 4)
flock -n 9 || { echo "GD_ABORT: another campaign script holds /tmp/rescuemind_campaign.lock" >&2; exit 1; }
export PATH="$HOME/.local/bin:$PATH"
RES=experiments/results
CAND=experiments/campaign_gd_candidates.json
MASKS=experiments/campaign_gd_candidates_design_fire_masks.json
SEL=experiments/campaign_gd_selection.json
PROTO=experiments/campaign_gd_protocol.json
PILOT=experiments/campaign_gd_pilot_protocol.json
CALPROTO=experiments/campaign_gdk_protocol.json
IN_NEXT=(docker exec rm-next rescuemind-entrypoint)
abort() { echo "GD_ABORT: $*" >&2; exit 1; }
mkdir -p "$RES"
for f in experiments/PREREGISTRATION_GD.md "$CAND" "$PILOT" "$CALPROTO" experiments/gd_site_open.json scripts/make_protocol_gd.py scripts/gd_analysis.py scripts/gd_calibrate.py rescuemind/robust_scenes.py scripts/make_protocol_v34.py; do
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
if ! git log --format=%H -n1 --grep='^study GD: selection and protocol' | grep -q .; then
  python3 scripts/make_protocol_gd.py --select "$MASKS" || abort "selection"
  [ -s "$PROTO" ] || abort "no protocol (no eligible candidate)"
  git add "$MASKS" "$SEL" "$PROTO"
  git commit -q -m "study GD: selection and protocol (design masks of the candidates, no model score), before any GD trial

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$MASKS" "$SEL" "$PROTO" && git push -q || abort "binding commit failed"
fi
echo "GD_BINDING_COMMIT_DONE"
python3 scripts/make_protocol_gd.py >/dev/null && git diff --quiet HEAD -- "$PROTO" || abort "the protocol differs from its generator"

# (b0) Amendment 1: calibrate the depot threshold on 100 fire-free depot worlds of the GD generator (the mission with the threshold off), BEFORE the pilot and any GD trial.
#      Stop rule: tau_cal >= 0.05 (the depot cannot be calibrated below the default at alpha = 2%): GD is not run.
python3 scripts/make_protocol_gd.py >/dev/null && git diff --quiet HEAD -- "$CALPROTO" || abort "the calibration protocol differs from its generator"
if [ ! -f "$RES/gd_calibration_done" ]; then
  python3 scripts/ledger_stack_check.py --protocol "$CALPROTO" --ledger "$RES/campaign_GDK_ledger.jsonl" || abort "stale calibration ledger (see above)"
  for i in $(seq 1 60); do awk '{exit !($1 < 6)}' /proc/loadavg && break; sleep 60; done
  "${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$CALPROTO" --ledger "$RES/campaign_GDK_ledger.jsonl" 2>&1 | tee -a "$RES/campaign_GDK_stdout.log" | grep -E "^\[|trial|ERROR" | tail -3
  python3 scripts/gd_calibrate.py > "$RES/gd_calibrate_stdout.log"; CRC=$?
  git add "$RES/gd_calibration.json" "$RES/campaign_GDK_ledger.jsonl" experiments/gd_site_cal.json
  git commit -q -m "study GD: calibration (100 fire-free depot worlds, threshold off) and tau_cal, before any GD trial

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$RES/gd_calibration.json" "$RES/campaign_GDK_ledger.jsonl" experiments/gd_site_cal.json && git push -q || echo "GD_NOTE: nothing new to commit or push" >&2
  [ "$CRC" -eq 0 ] || abort "GD_STOP_RULE: the calibration stop rule applies (see $RES/gd_calibration.json); GD NOT started"
  touch "$RES/gd_calibration_done"
fi
echo "GD_CALIBRATION_DONE $(python3 -c "import json;print(json.load(open('experiments/gd_site_cal.json'))['hazard_threshold'])")"
python3 scripts/ledger_stack_check.py --protocol "$PILOT" --ledger "$RES/campaign_GD_pilot_ledger.jsonl" || abort "stale pilot ledger (see above)"

# (b) mechanics pilot (2 runs; STOPS unless the pilot behaves)
if [ ! -f "$RES/gd_pilot_ok" ]; then
  "${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PILOT" --ledger "$RES/campaign_GD_pilot_ledger.jsonl" 2>&1 | tail -20
  python3 scripts/gd_analysis.py --pilot || abort "pilot did not behave as designed; GD NOT started"
  touch "$RES/gd_pilot_ok"
fi
echo "GD_PILOT_OK"
if ! git log --format=%H -n1 --grep='^study GD: registration' | grep -q .; then
  git add "$RES/campaign_GD_pilot_ledger.jsonl" "$RES/gd_pilot_ok"
  git commit -q -m "study GD: registration (pilot ledger), before the first GD trial

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$RES/campaign_GD_pilot_ledger.jsonl" "$RES/gd_pilot_ok" && git push -q || echo "GD_NOTE: nothing new to commit or push" >&2
fi

# (c) external timestamp of the registration commit (hashes only), wait for the Bitcoin attestation
REG=$(git log --format=%H -n1 --grep='^study GD: registration')
mkdir -p docs/timestamps
STAMP=docs/timestamps/study_gd_registration.txt
if [ ! -f "$STAMP.ots" ]; then
  { echo "# study GD registration commit and the sha256 of its registered files (hashes only are sent to OpenTimestamps)"; echo "commit $REG";
    sha256sum experiments/PREREGISTRATION_GD.md "$PROTO" "$SEL" "$MASKS"; } > "$STAMP"
  ots stamp "$STAMP" >/dev/null 2>&1 || echo "GD_NOTE: ots stamp failed (no network?)" >&2
fi
if [ -n "${GD_OTS_WAIT:-}" ]; then               # Note (start rule as GC Note 3): the campaign starts once the stamp is submitted; set GD_OTS_WAIT=1 to wait for the attestation first
  ATT=0
  if [ -f "$STAMP.ots" ]; then
    for i in $(seq 1 480); do                     # up to 8 h, once a minute
      if ots upgrade "$STAMP.ots" 2>&1 | grep -q "Success"; then ATT=1; echo "GD_OTS_ATTESTED"; break; fi
      sleep 60
    done
  fi
  [ "$ATT" -eq 1 ] || abort "GD_OTS_NOT_ATTESTED: no Bitcoin attestation of the registration stamp; the paper may not claim an external ordering for GD"
fi
git add "$STAMP" "$STAMP.ots" 2>/dev/null; git commit -q -m "study GD: OpenTimestamps proof of the registration commit

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$STAMP" "$STAMP.ots" 2>/dev/null && git push -q || true

# (d) campaign (quiet host first)
python3 scripts/ledger_stack_check.py --protocol "$PROTO" --ledger "$RES/campaign_GD_ledger.jsonl" || abort "stale campaign ledger (see above)"
for i in $(seq 1 60); do awk '{exit !($1 < 6)}' /proc/loadavg && break; sleep 60; done
echo "GD_LOAD_AT_START $(cut -d' ' -f1-3 /proc/loadavg)"
"${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PROTO" --ledger "$RES/campaign_GD_ledger.jsonl" \
  2>&1 | tee -a "$RES/campaign_GD_stdout.log" | grep -E "^\[|trial|ERROR" | tail -5
[ "${PIPESTATUS[0]}" -eq 0 ] || abort "run_campaign.py failed (rerun resumes)"

# (e) analysis
python3 scripts/gd_analysis.py > "$RES/gd_analysis_stdout.log" || exit 1
echo "GD_DONE"
