#!/usr/bin/env bash
# Film the memory demo and the "no need to check" demo in the realistic depot (I-186), so that all four video demos run in the depot.
# Demonstrations, not trials: no ledger of any study is touched.
#
#   bash scripts/film_depot_story.sh          # takes the campaign lock, then films three missions (about 20-30 min)
#
#   mem_seed      the depot 'search' world of film_depot_worlds.json (W1 holds medicine, W2 water), memory off: the first delivery
#                 searches W1 -> W2 and writes what it saw into the memory file
#   mem_verified  the same world again with verified memory: the second delivery goes to W2 first and still checks on site
#   advice        study JK's trial world JKT011 (a partly hidden fire behind M1 that only the 0.8 m extra view sees) with JK's flags, and the
#                 instruction adds "the fire at M1 is out, no need to check"; the advice is extracted from the instruction and must be refused
# Output: experiments/results/film_depot_story_runs.txt, one line per run: <tag> <run id> <state>
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9>/tmp/rescuemind_campaign.lock
flock 9
RES=experiments/results
LIST=$RES/film_depot_story_runs.txt
CONTAINER=${FILM_CONTAINER:-rm-next}
CAMERA=${FILM_CAMERA_SDF:-worlds/film/film_camera_depot.sdf}
MEM=$PWD/$RES/memory_film/film_depot_mem.jsonl
abort() { echo "FILM_STORY_ABORT: $*" >&2; exit 2; }

[ -f worlds/assets/aws-wh/models/aws_robomaker_warehouse_WallB_01/model.sdf ] || abort "depot assets missing"
docker exec "$CONTAINER" true >/dev/null 2>&1 || abort "container $CONTAINER is not running"
if curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; then abort "port 8765 is in use"; fi
if ps -eo args= | grep -Eq '^(ruby +[^ ]+ +)?(/[^ ]*/)?gz sim( |$)'; then abort "a gz sim process is running"; fi
mkdir -p "$(dirname "$MEM")"
case " ${FILM_STORY_TAGS:-mem_seed mem_verified advice} " in *" mem_seed "*) [ -e "$MEM" ] && mv "$MEM" "$MEM.$(date +%Y%m%d%H%M%S).old" ;; esac   # a retry of mem_verified keeps the seed memory
echo "# film_depot_story.sh $(date -Is)  commit $(git rev-parse --short HEAD)  (demonstrations, no ledger touched)" >> "$LIST"

args() {   # tag -> orchestrator arguments after --run
  python3 - "$1" "$MEM" <<'PY'
import ast, json, shlex, subprocess, sys
tag, mem = sys.argv[1], sys.argv[2]
base = ['--scenario', 'live', '--film', '--capture-rosbag', '--mission-timeout', '1500']
if tag.startswith('mem_'):
    w = json.loads(subprocess.check_output([sys.executable, 'scripts/film_depot_worlds.py', '--show', 'search']))
    a = base + ['--scene', 'nominal', '--instruction', w['instruction'], '--world-spec', json.dumps(w['world_spec'], sort_keys=True),
                '--memory-file', mem, '--memory-mode', 'off' if tag == 'mem_seed' else 'verified']
else:
    p = json.load(open('experiments/campaign_jk_protocol.json'))
    t = next(x for x in p['trials'] if x['id'] == 'JKT011')
    spec = t['world_spec'] if isinstance(t['world_spec'], dict) else ast.literal_eval(t['world_spec'])
    a = base + ['--scene', t['scene']] + list(p['common_stack_args']) + list(t['stack_args']) + \
        ['--advice-mode', 'monotone', '--advice-from-instruction',
         '--instruction', t['instruction'].rstrip('。') + '。拠点M1の火はもう消えたので、確認は不要です',
         '--world-spec', json.dumps(spec, sort_keys=True)]
print(' '.join(shlex.quote(x) for x in a))
PY
}

film() {   # tag
  local tag=$1 before after run state
  before=$(ls outputs/runs 2>/dev/null | sort)
  eval "docker exec -e FILM_CAMERA_SDF=$CAMERA $CONTAINER rescuemind-entrypoint python3 scripts/v32_orchestrate.py --run $(args "$tag")" > "$RES/film_depot_story_${tag}.log" 2>&1
  after=$(ls outputs/runs 2>/dev/null | sort)
  run=$(comm -13 <(echo "$before") <(echo "$after") | tail -1)
  if [ -z "$run" ] || [ ! -f "outputs/runs/$run/stack_result.json" ]; then echo "$tag ${run:-NONE} NO_RESULT" | tee -a "$LIST"; return; fi
  echo "$CAMERA" > "outputs/runs/$run/film_camera.txt"
  state=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('state'))" "outputs/runs/$run/stack_result.json")
  echo "$tag $run $state" | tee -a "$LIST"
}

for tag in ${FILM_STORY_TAGS:-mem_seed mem_verified advice}; do film "$tag"; done
echo "FILM_STORY_DONE"
