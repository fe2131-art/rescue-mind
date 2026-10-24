#!/usr/bin/env bash
# Study JM (a paired smoke-plume ablation of v3.6 and the extra views at the depot, FRESH worlds; experiments/PREREGISTRATION_JM.md), full sequence.  Run from the MAIN checkout ONLY when no other campaign uses
# Gazebo / the GPU (it drives rm-next; it takes the campaign lock and WAITS for it) and the depot assets are fetched.
#   bash scripts/jm_run.sh      # candidate masks -> selection + protocol (BINDING commit, no model score) -> OpenTimestamps -> campaign (240 runs, about 11 h) -> analysis
# No new pilot: the mechanics (flags, the near pose dropped, the completion audit) are those of the JK pilot and campaign; this script refuses to start if the code or the JK/JL results differ from HEAD.  Resumable.
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9>/tmp/rescuemind_campaign.lock
flock 9
export PATH="$HOME/.local/bin:$PATH"
RES=experiments/results
CAND=experiments/campaign_jm_candidates.json
MASKS=experiments/campaign_jm_candidates_design_fire_masks.json
SEL=experiments/campaign_jm_selection.json
PROTO=experiments/campaign_jm_protocol.json
IN_NEXT=(docker exec rm-next rescuemind-entrypoint)
abort() { echo "JM_ABORT: $*" >&2; exit 1; }
mkdir -p "$RES"
for f in experiments/PREREGISTRATION_JM.md "$CAND" scripts/make_protocol_jm.py scripts/jm_analysis.py scripts/jm_run.sh scripts/make_protocol_gm.py scripts/make_protocol_jk.py scripts/jk_analysis.py scripts/gm_analysis.py \
         ros/gazebo_waypoint_mission.py rescuemind/adaptive_views.py rescuemind/local_run_audit.py scripts/v32_orchestrate.py scripts/run_campaign.py rescuemind/robust_scenes.py scripts/make_protocol_v34.py \
         $RES/jk_summary.json $RES/campaign_JK_ledger.jsonl scripts/make_protocol_jl.py scripts/jl_analysis.py; do
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
if ! git log --format=%H -n1 --grep='^study JM: selection and protocol' | grep -q .; then
  python3 scripts/make_protocol_jm.py --select "$MASKS" || abort "selection"
  [ -s "$PROTO" ] || abort "no protocol (no eligible candidate)"
  git add "$MASKS" "$SEL" "$PROTO"
  git commit -q -m "study JM: selection and protocol (design masks of the candidates, no model score), before any JM trial

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$MASKS" "$SEL" "$PROTO" && git push -q || abort "binding commit failed"
fi
echo "JM_BINDING_COMMIT_DONE"
python3 scripts/make_protocol_jm.py >/dev/null && git diff --quiet HEAD -- "$PROTO" || abort "the protocol differs from its generator"

# (b) external timestamp of the binding commit (hashes only); the campaign starts once the stamp is submitted
REG=$(git log --format=%H -n1 --grep='^study JM: selection and protocol')
mkdir -p docs/timestamps
STAMP=docs/timestamps/study_jm_registration.txt
if [ ! -f "$STAMP.ots" ]; then
  { echo "# study JM registration commit and the sha256 of its registered files (hashes only are sent to OpenTimestamps)"; echo "commit $REG";
    sha256sum experiments/PREREGISTRATION_JM.md "$PROTO" "$SEL" "$MASKS" scripts/jm_analysis.py scripts/make_protocol_jm.py; } > "$STAMP"
  ots stamp "$STAMP" >/dev/null 2>&1 || echo "JM_NOTE: ots stamp failed (no network?)" >&2
fi
git add "$STAMP" "$STAMP.ots" 2>/dev/null; git commit -q -m "study JM: OpenTimestamps proof of the registration commit

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$STAMP" "$STAMP.ots" 2>/dev/null && git push -q || true

# (c) campaign (quiet host first)
python3 scripts/ledger_stack_check.py --protocol "$PROTO" --ledger "$RES/campaign_JM_ledger.jsonl" || abort "stale campaign ledger (see above)"
for i in $(seq 1 60); do awk '{exit !($1 < 6)}' /proc/loadavg && break; sleep 60; done
echo "JM_LOAD_AT_START $(cut -d' ' -f1-3 /proc/loadavg)"
"${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PROTO" --ledger "$RES/campaign_JM_ledger.jsonl" \
  2>&1 | tee -a "$RES/campaign_JM_stdout.log" | grep -E "^\[|trial|ERROR" | tail -5
[ "${PIPESTATUS[0]}" -eq 0 ] || abort "run_campaign.py failed (rerun resumes)"

# (d) analysis
python3 scripts/jm_analysis.py > "$RES/jm_analysis_stdout.log" || exit 1
echo "JM_DONE"
