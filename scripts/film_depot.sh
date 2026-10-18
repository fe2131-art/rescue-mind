#!/usr/bin/env bash
# Segment 6 of the final video (docs/design/video_v5_plan.md): filmed live missions in the realistic relief depot (I-21, k = 4 bays).
#
#   bash scripts/film_depot.sh --plan     # print the exact orchestrator commands (v32_orchestrate.py --plan, no side effects) and
#                                         # build + validate the worlds offline; runs anywhere, checks nothing about the host
#   bash scripts/film_depot.sh            # film: run from the MAIN checkout after the GPU queue (study A / X / XD) has finished
#
# Stack: v3.6 = the orchestrator defaults (recovery search, look-around 0.4 m, Qwen3.5-9B, tau_h 0.05), plus --film --capture-rosbag
# and the depot overview camera (worlds/film/film_camera_depot.sdf via FILM_CAMERA_SDF).  Nothing else is switched on.
#
# Missions (worlds: experiments/film_depot_worlds.json, scripts/film_depot_worlds.py):
#   search   the first water bay W1 holds medicine (swapped supply), W2 holds water: check W1, refuse, check W2, side views, deliver.
#   fire1..  a small, partly hidden fire behind W1 with a moving smoke plume (intended: the front check approves, a side view finds
#            the fire, the approval is revoked, the robot stops).  Candidate worlds are tried in order until a run shows exactly that
#            (scripts/film_depot_worlds.py --classify); at most FILM_FIRE_TRIES (default 2), so a session films at most 3 missions.
# These worlds have their OWN seed (FILM-DEPOT-2026).  They are not trial worlds of study X, of XD or of the X pilot, and no
# registered ledger is touched: filming them cannot be read as running (or previewing) a trial.
#
# Output: experiments/results/film_depot_runs.txt, one line per run:  <tag> <run id> <state> <kind> [attempt]
# Refuses to start (exit 2) when: not the main checkout; port 8765 answers (a VLM server of another campaign); a `gz sim` process
# exists; another campaign / orchestrator run is going; the container or the depot assets are missing.
set -uo pipefail
cd "$(dirname "$0")/.."
RES=experiments/results
LIST=$RES/film_depot_runs.txt
TAGS=${FILM_TAGS:-search}                 # missions always filmed, in order
FIRE_TRIES=${FILM_FIRE_TRIES:-2}          # fire candidates tried (fire1, fire2, ...; the first showing a side-view stop ends the search)
CONTAINER=${FILM_CONTAINER:-rm-next}
CAMERA=${FILM_CAMERA_SDF:-worlds/film/film_camera_depot.sdf}
MODE=run; [ "${1:-}" = "--plan" ] && MODE=plan
abort() { echo "FILM_DEPOT_ABORT: $*" >&2; exit 2; }

orchestrator_args() {   # tag -> the arguments after "--run|--plan" (instruction and world spec come from the frozen file)
  python3 - "$1" <<'PY'
import json, shlex, subprocess, sys
w = json.loads(subprocess.check_output([sys.executable, 'scripts/film_depot_worlds.py', '--show', sys.argv[1]]))
a = ['--scenario', 'live', '--scene', 'nominal', '--film', '--capture-rosbag', '--mission-timeout', '1500',
     '--instruction', w['instruction'], '--world-spec', json.dumps(w['world_spec'], sort_keys=True)]
print(' '.join(shlex.quote(x) for x in a))
PY
}

if [ "$MODE" = plan ]; then
  W=$(mktemp -d "${TMPDIR:-/tmp}/film_depot_worlds.XXXXXX")
  python3 scripts/film_depot_worlds.py --check "$W" || exit 1
  for tag in $TAGS $(seq 1 "$FIRE_TRIES" | sed 's/^/fire/'); do
    echo "== $tag: FILM_CAMERA_SDF=$CAMERA docker exec -e FILM_CAMERA_SDF=$CAMERA $CONTAINER rescuemind-entrypoint python3 scripts/v32_orchestrate.py --run $(orchestrator_args "$tag" | cut -c1-160)..."
    eval "nice -n 19 python3 scripts/v32_orchestrate.py --plan $(orchestrator_args "$tag")" | python3 -c "
import json, sys
d = json.load(sys.stdin)
m = ' '.join(d['mission'])
print('   services:', ' | '.join((s[0] if s[0] != 'bash' else s[-1].split('/')[-1].split(' ')[-1] if len(s) == 2 else 'bash -c ...') for s in d['services']))
print('   film bridge + recorder:', any('film_camera_bridge' in ' '.join(s) for s in d['services']), any('film_recorder' in ' '.join(s) for s in d['services']), ' rosbag:', d['capture_rosbag'])
print('   mission flags:', [t for t in ('--recovery', '--look-around 0.4', '--expected-hazard-threshold 0.05', '--vlm-model Qwen/Qwen3.5-9B', '--local-mode single') if t in m])
"
  done
  echo "(the Gazebo world is written at run time next to the run's evidence; --check above built and validated every world offline in $W)"
  exit 0
fi

# ---------------------------------------------------------------- start gates (all must pass; nothing has been started yet)
[ "$(git rev-parse --git-dir)" = "$(git rev-parse --git-common-dir)" ] || abort "not the main checkout (a linked worktree): run from the main checkout of the repository"
[ -f worlds/assets/aws-wh/models/aws_robomaker_warehouse_WallB_01/model.sdf ] || abort "depot assets missing (scripts/fetch_depot_assets.sh)"
docker exec "$CONTAINER" true >/dev/null 2>&1 || abort "container $CONTAINER is not running"
if curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; then abort "port 8765 is in use (another VLM server is running)"; fi
if ps -eo args= | grep -Eq '^(ruby +[^ ]+ +)?(/[^ ]*/)?gz sim( |$)'; then abort "a gz sim process is running (the GPU queue is not finished)"; fi
if ps -eo args= | grep -Eq '(run_campaign\.py|v32_orchestrate\.py +--run|local_vlm_server\.py)'; then abort "a campaign / orchestrator / VLM server process is running"; fi
python3 scripts/film_depot_worlds.py --check "$(mktemp -d "${TMPDIR:-/tmp}/film_depot_worlds.XXXXXX")" >/dev/null || abort "film worlds stale or invalid (scripts/film_depot_worlds.py --check)"
mkdir -p "$RES"
{ echo "# film_depot.sh $(date -Is)  commit $(git rev-parse --short HEAD)  worlds: experiments/film_depot_worlds.json (seed FILM-DEPOT-2026; not a trial world of X / XD / X pilot)"; } >> "$LIST"

film() {   # tag attempt  -> sets RUN_KIND
  local tag=$1 attempt=$2 before after run state
  before=$(ls outputs/runs 2>/dev/null | sort)
  eval "docker exec -e FILM_CAMERA_SDF=$CAMERA $CONTAINER rescuemind-entrypoint python3 scripts/v32_orchestrate.py --run $(orchestrator_args "$tag")" >"$RES/film_depot_${tag}.log" 2>&1
  after=$(ls outputs/runs 2>/dev/null | sort)
  run=$(comm -13 <(echo "$before") <(echo "$after") | tail -1)
  if [ -z "$run" ] || [ ! -f "outputs/runs/$run/stack_result.json" ]; then
    echo "$tag ${run:-NONE} NO_RESULT unknown $attempt" | tee -a "$LIST"; RUN_KIND=unknown; return
  fi
  echo "$CAMERA" > "outputs/runs/$run/film_camera.txt"      # sidecar: scripts/make_video_plan.py --depot reads the camera pose from it
  state=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('state'))" "outputs/runs/$run/stack_result.json")
  RUN_KIND=$(python3 scripts/film_depot_worlds.py --classify "outputs/runs/$run" 2>/dev/null | python3 -c "import json,sys;print(json.load(sys.stdin)['kind'])" 2>/dev/null || echo unknown)
  echo "$tag $run $state $RUN_KIND $attempt" | tee -a "$LIST"
}

for tag in $TAGS; do film "$tag" 1; done
for i in $(seq 1 "$FIRE_TRIES"); do
  film "fire$i" "$i"
  [ "$RUN_KIND" = side_fire ] && break
done
echo "FILM_DEPOT_DONE (see $LIST; pass the chosen run ids to scripts/make_video_plan.py --depot)"
