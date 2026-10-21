#!/usr/bin/env bash
# Study GL (left-only 0.8 m look-around with the front + left threshold at the depot, fresh worlds; experiments/PREREGISTRATION_GL.md), full sequence.  Run from the MAIN checkout ONLY when no other
# campaign uses Gazebo / the GPU (it drives rm-next) and the depot assets are fetched (scripts/fetch_depot_assets.sh).
#   bash scripts/gl_run.sh                    # candidate masks -> selection + protocol (binding commit) -> pilot -> registration commit + OpenTimestamps
#                                             #   -> (wait for the Bitcoin attestation) -> campaign -> analysis
#   GL_OTS_WAIT=1 bash scripts/gl_run.sh      # wait for the Bitcoin attestation before the campaign (default: start once the stamp is submitted)
# Everything before the campaign uses no model score: the selection rule reads design fire masks only.  Resumable.
set -uo pipefail
cd "$(dirname "$0")/.."
for _ in $(seq 1 1440); do pgrep -f "[j]h_run" >/dev/null || break; sleep 60; done          # study JH scoring first (its steps would otherwise queue behind this 15 h campaign)
exec 9>/tmp/rescuemind_campaign.lock                       # one campaign at a time (the GC double launch, PREREGISTRATION_GC Note 4)
flock 9                                                    # GL waits for the lock (study JH scoring steps hold it one at a time), it does not abort
export PATH="$HOME/.local/bin:$PATH"
RES=experiments/results
CAND=experiments/campaign_gl_candidates.json
MASKS=experiments/campaign_gl_candidates_design_fire_masks.json
SEL=experiments/campaign_gl_selection.json
PROTO=experiments/campaign_gl_protocol.json
PILOT=experiments/campaign_gl_pilot_protocol.json
IN_NEXT=(docker exec rm-next rescuemind-entrypoint)
abort() { echo "GL_ABORT: $*" >&2; exit 1; }
mkdir -p "$RES"
for f in experiments/PREREGISTRATION_GL.md "$CAND" "$PILOT" experiments/gl_site_cal.json scripts/make_protocol_gl.py scripts/gl_analysis.py rescuemind/robust_scenes.py scripts/make_protocol_v34.py; do
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
if ! git log --format=%H -n1 --grep='^study GL: selection and protocol' | grep -q .; then
  python3 scripts/make_protocol_gl.py --select "$MASKS" || abort "selection"
  [ -s "$PROTO" ] || abort "no protocol (no eligible candidate)"
  git add "$MASKS" "$SEL" "$PROTO"
  git commit -q -m "study GL: selection and protocol (design masks of the candidates, no model score), before any GL trial

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$MASKS" "$SEL" "$PROTO" && git push -q || abort "binding commit failed"
fi
echo "GL_BINDING_COMMIT_DONE"
python3 scripts/make_protocol_gl.py >/dev/null && git diff --quiet HEAD -- "$PROTO" || abort "the protocol differs from its generator"

python3 scripts/ledger_stack_check.py --protocol "$PILOT" --ledger "$RES/campaign_GL_pilot_ledger.jsonl" || abort "stale pilot ledger (see above)"

# (b) mechanics pilot (2 runs; STOPS unless the pilot behaves)
if [ ! -f "$RES/gl_pilot_ok" ]; then
  "${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PILOT" --ledger "$RES/campaign_GL_pilot_ledger.jsonl" 2>&1 | tail -20
  python3 scripts/gl_analysis.py --pilot || abort "pilot did not behave as designed; GL NOT started"
  touch "$RES/gl_pilot_ok"
fi
echo "GL_PILOT_OK"
if ! git log --format=%H -n1 --grep='^study GL: registration' | grep -q .; then
  git add "$RES/campaign_GL_pilot_ledger.jsonl" "$RES/gl_pilot_ok"
  git commit -q -m "study GL: registration (pilot ledger), before the first GL trial

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$RES/campaign_GL_pilot_ledger.jsonl" "$RES/gl_pilot_ok" && git push -q || echo "GL_NOTE: nothing new to commit or push" >&2
fi

# (c) external timestamp of the registration commit (hashes only), wait for the Bitcoin attestation
REG=$(git log --format=%H -n1 --grep='^study GL: registration')
mkdir -p docs/timestamps
STAMP=docs/timestamps/study_gl_registration.txt
if [ ! -f "$STAMP.ots" ]; then
  { echo "# study GL registration commit and the sha256 of its registered files (hashes only are sent to OpenTimestamps)"; echo "commit $REG";
    sha256sum experiments/PREREGISTRATION_GL.md "$PROTO" "$SEL" "$MASKS"; } > "$STAMP"
  ots stamp "$STAMP" >/dev/null 2>&1 || echo "GL_NOTE: ots stamp failed (no network?)" >&2
fi
if [ -n "${GL_OTS_WAIT:-}" ]; then               # Note (start rule as GC Note 3): the campaign starts once the stamp is submitted; set GL_OTS_WAIT=1 to wait for the attestation first
  ATT=0
  if [ -f "$STAMP.ots" ]; then
    for i in $(seq 1 480); do                     # up to 8 h, once a minute
      if ots upgrade "$STAMP.ots" 2>&1 | grep -q "Success"; then ATT=1; echo "GL_OTS_ATTESTED"; break; fi
      sleep 60
    done
  fi
  [ "$ATT" -eq 1 ] || abort "GL_OTS_NOT_ATTESTED: no Bitcoin attestation of the registration stamp; the paper may not claim an external ordering for GL"
fi
git add "$STAMP" "$STAMP.ots" 2>/dev/null; git commit -q -m "study GL: OpenTimestamps proof of the registration commit

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$STAMP" "$STAMP.ots" 2>/dev/null && git push -q || true

# (d) campaign (quiet host first)
python3 scripts/ledger_stack_check.py --protocol "$PROTO" --ledger "$RES/campaign_GL_ledger.jsonl" || abort "stale campaign ledger (see above)"
for i in $(seq 1 60); do awk '{exit !($1 < 6)}' /proc/loadavg && break; sleep 60; done
echo "GL_LOAD_AT_START $(cut -d' ' -f1-3 /proc/loadavg)"
"${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PROTO" --ledger "$RES/campaign_GL_ledger.jsonl" \
  2>&1 | tee -a "$RES/campaign_GL_stdout.log" | grep -E "^\[|trial|ERROR" | tail -5
[ "${PIPESTATUS[0]}" -eq 0 ] || abort "run_campaign.py failed (rerun resumes)"

# (e) analysis
python3 scripts/gl_analysis.py > "$RES/gl_analysis_stdout.log" || exit 1
echo "GL_DONE"
