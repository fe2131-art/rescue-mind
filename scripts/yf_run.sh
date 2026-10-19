#!/usr/bin/env bash
# Study YF (Y on fresh worlds; experiments/PREREGISTRATION_YF.md), full sequence.  Run from the MAIN checkout.  Part A needs Gazebo (candidate masks) and part B
# (campaign) needs a quiet host: the script waits until no other campaign script runs.
#   bash scripts/yf_run.sh      # candidate masks -> selection + protocol (binding commit) -> OpenTimestamps stamp -> wait for attestation -> campaign -> analysis
# No model score is used before the campaign.  Resumable.
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
RES=experiments/results
CAND=experiments/campaign_yf_candidates.json
MASKS=experiments/campaign_yf_candidates_design_fire_masks.json
CANDB=experiments/campaign_yf_candidates_b.json
MASKSB=experiments/campaign_yf_candidates_b_design_fire_masks.json
SEL=experiments/campaign_yf_selection.json
PROTO=experiments/campaign_yf_protocol.json
IN_NEXT=(docker exec rm-next rescuemind-entrypoint)
abort() { echo "YF_ABORT: $*" >&2; exit 1; }
mkdir -p "$RES"
[ -f worlds/assets/aws-wh/models/aws_robomaker_warehouse_WallB_01/model.sdf ] || abort "depot assets missing"
for f in experiments/PREREGISTRATION_YF.md "$CAND" "$CANDB" scripts/make_protocol_yf.py scripts/yf_analysis.py scripts/y_analysis.py; do
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || abort "$f is not committed"
  git diff --quiet HEAD -- "$f" || abort "$f differs from the committed version"
done
"${IN_NEXT[@]}" true >/dev/null 2>&1 || abort "the container rm-next is not running"

# (a) candidate design masks (Gazebo; no other campaign may be rendering)
if [ ! -s "$MASKS" ]; then
  for _ in $(seq 1 600); do pgrep -f "scripts/run_campaign.py" >/dev/null || break; sleep 30; done
  "${IN_NEXT[@]}" python3 scripts/fire_mask_at_pose.py --protocol "$CAND" --design --design-sides 0.4 || abort "candidate masks"
fi
if [ ! -s "$MASKSB" ]; then
  for _ in $(seq 1 600); do pgrep -f "scripts/run_campaign.py" >/dev/null || break; sleep 30; done
  "${IN_NEXT[@]}" python3 scripts/fire_mask_at_pose.py --protocol "$CANDB" --design --design-sides 0.4 || abort "candidate masks (batch b)"
fi
[ -s "$MASKS" ] && [ -s "$MASKSB" ] || abort "candidate design masks missing"
if ! git log --format=%H -n1 --grep='^study YF: selection and protocol (amendment 1)' | grep -q .; then
  python3 scripts/make_protocol_yf.py --select "$MASKS" "$MASKSB" --force || abort "selection"
  [ -s "$PROTO" ] || abort "no protocol (no eligible candidate)"
  git add "$MASKS" "$MASKSB" "$CANDB" "$SEL" "$PROTO" experiments/advice_YF
  git commit -q -m "study YF: selection and protocol (amendment 1: second candidate batch; design masks only, no model score), before any YF trial

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$MASKS" "$MASKSB" "$CANDB" "$SEL" "$PROTO" experiments/advice_YF && git push -q || abort "binding commit failed"
fi
echo "YF_BINDING_COMMIT_DONE"
python3 scripts/make_protocol_yf.py >/dev/null && git diff --quiet HEAD -- "$PROTO" || abort "the protocol differs from its generator"

# (b) external timestamp (hashes only) of the binding commit, wait for the Bitcoin attestation
REG=$(git log --format=%H -n1 --grep='^study YF: selection and protocol (amendment 1')
mkdir -p docs/timestamps
STAMP=docs/timestamps/study_yf_registration_a1.txt
if [ ! -f "$STAMP.ots" ]; then
  { echo "# study YF binding commit and the sha256 of its registered files (hashes only are sent to OpenTimestamps)"; echo "commit $REG";
    sha256sum experiments/PREREGISTRATION_YF.md "$PROTO" "$SEL" "$MASKS" "$MASKSB"; } > "$STAMP"
  ots stamp "$STAMP" >/dev/null 2>&1 || echo "YF_NOTE: ots stamp failed (no network?)" >&2
fi
if [ -z "${YF_NO_OTS_WAIT:-}" ]; then
  ATT=0
  if [ -f "$STAMP.ots" ]; then
    for i in $(seq 1 480); do
      if ots upgrade "$STAMP.ots" 2>&1 | grep -q "Success"; then ATT=1; echo "YF_OTS_ATTESTED"; break; fi
      sleep 60
    done
  fi
  [ "$ATT" -eq 1 ] || abort "YF_OTS_NOT_ATTESTED: no Bitcoin attestation of the registration stamp; the paper may not claim an external ordering for YF"
fi
git add "$STAMP" "$STAMP.ots" 2>/dev/null; git commit -q -m "study YF: OpenTimestamps proof of the binding commit

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$STAMP" "$STAMP.ots" 2>/dev/null && git push -q || true

# (c) campaign: wait for the host (the YE campaign may still run), then run
for _ in $(seq 1 600); do pgrep -f "scripts/ye_run.sh" >/dev/null || break; sleep 30; done
python3 scripts/ledger_stack_check.py --protocol "$PROTO" --ledger "$RES/campaign_YF_ledger.jsonl" || abort "stale campaign ledger (see above)"
for i in $(seq 1 60); do awk '{exit !($1 < 6)}' /proc/loadavg && break; sleep 60; done
echo "YF_LOAD_AT_START $(cut -d' ' -f1-3 /proc/loadavg)"
"${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PROTO" --ledger "$RES/campaign_YF_ledger.jsonl" \
  2>&1 | tee -a "$RES/campaign_YF_stdout.log" | grep -E "^\[|trial|ERROR" | tail -5
[ "${PIPESTATUS[0]}" -eq 0 ] || abort "run_campaign.py failed (rerun resumes)"

# (d) analysis
python3 scripts/yf_analysis.py > "$RES/yf_analysis_stdout.log" || exit 1
echo "YF_DONE"
