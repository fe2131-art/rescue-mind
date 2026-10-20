#!/usr/bin/env bash
# Study GR (closed-loop miss rate of the look-around, fresh worlds; experiments/PREREGISTRATION_GR.md), full sequence.  Run from the MAIN checkout ONLY when no other
# campaign uses Gazebo / the GPU (it drives rm-next).
#   bash scripts/gr_run.sh                    # candidate masks -> selection + protocol (binding commit) -> pilot -> registration commit + OpenTimestamps
#                                             #   -> (wait for the Bitcoin attestation) -> campaign -> analysis
#   GR_NO_OTS_WAIT=1 bash scripts/gr_run.sh   # skip the wait (only for a rehearsal)
# Everything before the campaign uses no model score: the selection rule reads design fire masks only.  Resumable.
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
RES=experiments/results
CAND=experiments/campaign_gr_candidates.json
MASKS=experiments/campaign_gr_candidates_design_fire_masks.json
SEL=experiments/campaign_gr_selection.json
PROTO=experiments/campaign_gr_protocol.json
PILOT=experiments/campaign_gr_pilot_protocol.json
IN_NEXT=(docker exec rm-next rescuemind-entrypoint)
abort() { echo "GR_ABORT: $*" >&2; exit 1; }
mkdir -p "$RES"
for f in experiments/PREREGISTRATION_GR.md "$CAND" "$PILOT" scripts/make_protocol_gr.py scripts/gr_analysis.py rescuemind/robust_scenes.py scripts/make_protocol_v34.py; do
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
if ! git log --format=%H -n1 --grep='^study GR: selection and protocol' | grep -q .; then
  python3 scripts/make_protocol_gr.py --select "$MASKS" || abort "selection"
  [ -s "$PROTO" ] || abort "no protocol (no eligible candidate)"
  git add "$MASKS" "$SEL" "$PROTO"
  git commit -q -m "study GR: selection and protocol (design masks of the candidates, no model score), before any GR trial

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$MASKS" "$SEL" "$PROTO" && git push -q || abort "binding commit failed"
fi
echo "GR_BINDING_COMMIT_DONE"
python3 scripts/make_protocol_gr.py >/dev/null && git diff --quiet HEAD -- "$PROTO" || abort "the protocol differs from its generator"
python3 scripts/ledger_stack_check.py --protocol "$PILOT" --ledger "$RES/campaign_GR_pilot_ledger.jsonl" || abort "stale pilot ledger (see above)"

# (b) mechanics pilot (2 runs; STOPS unless the pilot behaves)
if [ ! -f "$RES/gr_pilot_ok" ]; then
  "${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PILOT" --ledger "$RES/campaign_GR_pilot_ledger.jsonl" 2>&1 | tail -20
  python3 scripts/gr_analysis.py --pilot || abort "pilot did not behave as designed; GR NOT started"
  touch "$RES/gr_pilot_ok"
fi
echo "GR_PILOT_OK"
if ! git log --format=%H -n1 --grep='^study GR: registration' | grep -q .; then
  git add "$RES/campaign_GR_pilot_ledger.jsonl" "$RES/gr_pilot_ok"
  git commit -q -m "study GR: registration (pilot ledger), before the first GR trial

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$RES/campaign_GR_pilot_ledger.jsonl" "$RES/gr_pilot_ok" && git push -q || echo "GR_NOTE: nothing new to commit or push" >&2
fi

# (c) external timestamp of the registration commit (hashes only), wait for the Bitcoin attestation
REG=$(git log --format=%H -n1 --grep='^study GR: registration')
mkdir -p docs/timestamps
STAMP=docs/timestamps/study_gr_registration.txt
if [ ! -f "$STAMP.ots" ]; then
  { echo "# study GR registration commit and the sha256 of its registered files (hashes only are sent to OpenTimestamps)"; echo "commit $REG";
    sha256sum experiments/PREREGISTRATION_GR.md "$PROTO" "$SEL" "$MASKS"; } > "$STAMP"
  ots stamp "$STAMP" >/dev/null 2>&1 || echo "GR_NOTE: ots stamp failed (no network?)" >&2
fi
if [ -z "${GR_NO_OTS_WAIT:-}" ]; then
  ATT=0
  if [ -f "$STAMP.ots" ]; then
    for i in $(seq 1 480); do                     # up to 8 h, once a minute
      if ots upgrade "$STAMP.ots" 2>&1 | grep -q "Success"; then ATT=1; echo "GR_OTS_ATTESTED"; break; fi
      sleep 60
    done
  fi
  [ "$ATT" -eq 1 ] || abort "GR_OTS_NOT_ATTESTED: no Bitcoin attestation of the registration stamp; the paper may not claim an external ordering for GR"
fi
git add "$STAMP" "$STAMP.ots" 2>/dev/null; git commit -q -m "study GR: OpenTimestamps proof of the registration commit

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$STAMP" "$STAMP.ots" 2>/dev/null && git push -q || true

# (d) campaign (quiet host first)
python3 scripts/ledger_stack_check.py --protocol "$PROTO" --ledger "$RES/campaign_GR_ledger.jsonl" || abort "stale campaign ledger (see above)"
for i in $(seq 1 60); do awk '{exit !($1 < 6)}' /proc/loadavg && break; sleep 60; done
echo "GR_LOAD_AT_START $(cut -d' ' -f1-3 /proc/loadavg)"
"${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PROTO" --ledger "$RES/campaign_GR_ledger.jsonl" \
  2>&1 | tee -a "$RES/campaign_GR_stdout.log" | grep -E "^\[|trial|ERROR" | tail -5
[ "${PIPESTATUS[0]}" -eq 0 ] || abort "run_campaign.py failed (rerun resumes)"

# (e) analysis
python3 scripts/gr_analysis.py > "$RES/gr_analysis_stdout.log" || exit 1
echo "GR_DONE"
