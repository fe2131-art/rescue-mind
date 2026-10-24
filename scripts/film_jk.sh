#!/usr/bin/env bash
# Film the suspicion-triggered extra views (study JK's configuration) for the video (I-134): one filmed live mission in a JK world in which the submitted
# v3.6 delivered into the fire (GM's run) and the extra views refused (JK's run).  A demonstration, not a trial: no ledger of any study is touched,
# and the video says that the world is one of JK's.
#
#   bash scripts/film_jk.sh            # takes the campaign lock (WAITS for the running campaigns), then films; resumable (a second call films again)
#   FILM_JK_TRIAL=JKT011 (default)      # the JK trial whose world, instruction and flags are reused
#
# Stack: the orchestrator defaults (v3.6) + JK's arm flags (--adaptive-views 0.8 --adaptive-near 0) + --film --capture-rosbag and the depot overview camera.
# Output: experiments/results/film_jk_runs.txt, one line per run:  <trial> <run id> <state> <extra views: triggered:L2,R2 | not_triggered | unknown>
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9>/tmp/rescuemind_campaign.lock
flock 9
RES=experiments/results
LIST=$RES/film_jk_runs.txt
TRIAL=${FILM_JK_TRIAL:-JKT011}
CONTAINER=${FILM_CONTAINER:-rm-next}
CAMERA=${FILM_CAMERA_SDF:-worlds/film/film_camera_depot.sdf}
abort() { echo "FILM_JK_ABORT: $*" >&2; exit 2; }

[ "$(git rev-parse --git-dir)" = "$(git rev-parse --git-common-dir)" ] || abort "not the main checkout"
[ -f worlds/assets/aws-wh/models/aws_robomaker_warehouse_WallB_01/model.sdf ] || abort "depot assets missing (scripts/fetch_depot_assets.sh)"
docker exec "$CONTAINER" true >/dev/null 2>&1 || abort "container $CONTAINER is not running"
if curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; then abort "port 8765 is in use (another VLM server is running)"; fi
if ps -eo args= | grep -Eq '^(ruby +[^ ]+ +)?(/[^ ]*/)?gz sim( |$)'; then abort "a gz sim process is running"; fi

ARGS=$(python3 - "$TRIAL" <<'PY'
import ast, json, shlex, sys
p = json.load(open('experiments/campaign_jk_protocol.json'))
t = next(x for x in p['trials'] if x['id'] == sys.argv[1])
assert t['config'] == 'adapt', t['config']
spec = t['world_spec'] if isinstance(t['world_spec'], dict) else ast.literal_eval(t['world_spec'])
a = ['--scenario', 'live', '--scene', t['scene'], '--film', '--capture-rosbag'] + list(p['common_stack_args']) + list(t['stack_args']) + \
    ['--instruction', t['instruction'], '--world-spec', json.dumps(spec, sort_keys=True)]
print(' '.join(shlex.quote(x) for x in a))
PY
) || abort "trial $TRIAL not found in experiments/campaign_jk_protocol.json"
echo "# film_jk.sh $(date -Is)  commit $(git rev-parse --short HEAD)  trial $TRIAL (a JK world, filmed as a demonstration; no ledger touched)" >> "$LIST"
before=$(ls outputs/runs 2>/dev/null | sort)
eval "docker exec -e FILM_CAMERA_SDF=$CAMERA $CONTAINER rescuemind-entrypoint python3 scripts/v32_orchestrate.py --run $ARGS" > "$RES/film_jk_${TRIAL}.log" 2>&1
after=$(ls outputs/runs 2>/dev/null | sort)
run=$(comm -13 <(echo "$before") <(echo "$after") | tail -1)
if [ -z "$run" ] || [ ! -f "outputs/runs/$run/stack_result.json" ]; then
  echo "$TRIAL ${run:-NONE} NO_RESULT unknown" | tee -a "$LIST"; echo "FILM_JK_DONE"; exit 1
fi
echo "$CAMERA" > "outputs/runs/$run/film_camera.txt"
state=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('state'))" "outputs/runs/$run/stack_result.json")
extra=$(python3 - "$run" <<'PY'
import sys
sys.path.insert(0, 'scripts')
try:
    from jk_analysis import adaptive_record      # the record the JK analysis reads (mission.json look_around.adaptive)
    a = adaptive_record({'run_id': sys.argv[1]})
    print('unknown' if a is None else 'triggered:' + ','.join(a['extras_taken']) if a['triggered'] else 'not_triggered')
except Exception:
    print('unknown')
PY
)
echo "$TRIAL $run $state $extra" | tee -a "$LIST"
echo "FILM_JK_DONE"
