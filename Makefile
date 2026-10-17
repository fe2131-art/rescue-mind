# RescueMind: one command per artefact.  `make` or `make help` lists the targets.
# Everything here wraps an existing script; no number is typed by hand (see docs/REPRODUCIBILITY.md).
# Nothing in this file starts a Gazebo/GPU campaign: the study-* targets only PRINT the registered command sequence.
SHELL := bash
.DEFAULT_GOAL := help
.NOTPARALLEL:

ACCOUNT  ?= tetsutetsu
DEV      ?= rm-dev
NEXT     ?= rm-next
LATEX_IMG ?= rescuemind:latex
NICE     ?= nice -n 19
# NB: no nice inside the container (nice drops LD_LIBRARY_PATH in the ROS shell, HANDOFF section 4)
IN_DEV    = docker exec $(DEV) rescuemind-entrypoint
FINAL    ?=

# Video (docs/design/video_v5_plan.md): run ids of the shots; override on the command line, e.g. make video ADVICE=<run_id>
VID_DELIVER ?= dbed92419f88479e
VID_RECOVER ?= b4fcd9d164444db7
VID_HIDDEN  ?= 9d73663832c94f16
VID_MEMORY  ?= b93040decbf04ca4
ADVICE      ?=
VIDEO_ARGS  ?= --deliver $(VID_DELIVER) --recover $(VID_RECOVER) $(if $(ADVICE),--advice $(ADVICE),--hidden-fire $(VID_HIDDEN)) --memory $(VID_MEMORY)
VIDEO_OUT   ?= outputs/video/PAI最終課題_$(ACCOUNT).mp4
NARRATE     ?= 2

# --- prerequisite checks (print a helpful message instead of failing obscurely) ---
define REQ_DOCKER
@command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 || { echo "ERROR: docker is not usable (is it installed, is the daemon running, are you in the docker group?)."; echo "       See docs/REPRODUCIBILITY.md section 1-2."; exit 1; }
endef
define REQ_CONT
$(REQ_DOCKER)
@docker inspect -f '{{.State.Running}}' $(1) 2>/dev/null | grep -q true || { echo "ERROR: container '$(1)' is not running."; echo "       Start it:  $(2)"; echo "       (build the image first if needed: $(3); see docs/REPRODUCIBILITY.md section 2)"; exit 1; }
endef
define REQ_IMG
$(REQ_DOCKER)
@docker image inspect $(1) >/dev/null 2>&1 || { echo "ERROR: docker image '$(1)' not found.  Build it:  $(2)"; exit 1; }
endef
START_DEV  = RESCUEMIND_CONTAINER=$(DEV) bash docker/run.sh sleep infinity
START_NEXT = RESCUEMIND_IMAGE=rescuemind:jazzy-next RESCUEMIND_CONTAINER=$(NEXT) bash docker/run.sh sleep infinity
BUILD_DEV  = docker build --build-arg STACK=v33 -t rescuemind:jazzy docker
BUILD_NEXT = RESCUEMIND_IMAGE=rescuemind:jazzy-next bash docker/build.sh
BUILD_LATEX = docker build -t $(LATEX_IMG) docker/latex
NEED_DEV   = $(call REQ_CONT,$(DEV),$(START_DEV),$(BUILD_DEV))
NEED_LATEX = $(call REQ_IMG,$(LATEX_IMG),$(BUILD_LATEX))

.PHONY: help doctor test check numbers figures paper report readme youtube all-docs finalize assets video-plan video \
        study-D study-E study-F study-G study-H study-J study-V study-L study-A study-X study-W study-S study-XD \
        study-T1 study-T2 study-R study-P2 study-K

help: ## List the targets (default)
	@echo "RescueMind Makefile: one command per artefact (details: docs/REPRODUCIBILITY.md)"
	@echo
	@awk 'BEGIN{FS=":.*## "} /^[a-zA-Z0-9_-]+:.*## /{printf "  make %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo
	@echo "Variables: ACCOUNT=$(ACCOUNT)  FINAL=1 (paper: refuse pending results; otherwise they print a grey \"(pending)\", PENDING_TEXT=0 gives the red TBD)  NICE='$(NICE)'  ADVICE=<run_id> (video: advice-injection shot)"
	@echo "study-* targets never run anything: they print the commands (GPU, quiet host, no other Gazebo stack needed)."

doctor: ## Check docker, containers (rm-dev, rm-next), images and the latex image; print what is missing
	@command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 && echo "ok   docker" || echo "MISS docker (install; add yourself to the docker group)"
	@for c in $(DEV) $(NEXT); do docker inspect -f '{{.State.Running}}' $$c 2>/dev/null | grep -q true && echo "ok   container $$c running" || echo "MISS container $$c not running"; done
	@for i in rescuemind:jazzy rescuemind:jazzy-next $(LATEX_IMG); do docker image inspect $$i >/dev/null 2>&1 && echo "ok   image $$i" || echo "MISS image $$i"; done
	@echo "start rm-dev:   $(START_DEV)"
	@echo "start rm-next:  $(START_NEXT)"
	@echo "build images:   $(BUILD_DEV)   |   $(BUILD_NEXT)   |   $(BUILD_LATEX)"

test: ## Unit tests (in rm-dev; falls back to the host python3 where ROS parts are skipped/fail)
	@if docker inspect -f '{{.State.Running}}' $(DEV) 2>/dev/null | grep -q true; then \
	  $(IN_DEV) python3 -m unittest discover -s tests -q; \
	else \
	  echo "WARN: container $(DEV) is not running ($(START_DEV)); running on the host (tests that need ROS/reportlab may fail)."; \
	  $(NICE) python3 -m unittest discover -s tests -q; \
	fi

check: ## Consistency check: README, YouTube text, paper macros and report agree with experiments/results (exit 1 on mismatch; needs docker only for the PDF text)
	$(NICE) python3 scripts/check_consistency.py

verify: ## Re-check Proposition 2 on the implementation (z3 proof + model-vs-code differential + mutants, host python3; pip install -r requirements-verify.txt); compares the verdicts with the committed record
	$(NICE) python3 scripts/verify_advice_smt.py --out /tmp/rescuemind_smt_fresh.json
	$(NICE) python3 scripts/verify_compare.py /tmp/rescuemind_smt_fresh.json
	$(NICE) python3 -m pytest -q tests/test_i23_smt_refinement.py tests/test_advice_independent.py tests/test_i24_advice_credit.py

numbers: ## Regenerate docs/paper/numbers.tex and tab_*.tex from experiments/results (host python3, no docker)
	$(NICE) python3 scripts/paper_numbers.py

figures: ## Paper figures + graphical abstract + memory/advice diagrams (in rm-dev)
	$(NEED_DEV)
	$(IN_DEV) python3 scripts/make_paper_figures.py
	$(IN_DEV) python3 scripts/make_graphical_abstract.py
	$(IN_DEV) python3 scripts/make_memory_diagram.py
	$(IN_DEV) python3 scripts/make_advice_diagram.py

paper: ## Build docs/paper/main.pdf and supplement.pdf (rm-dev + latex image); FINAL=1 refuses pending TBD results
	$(NEED_DEV)
	$(NEED_LATEX)
ifneq ($(FINAL),)
	$(NICE) python3 scripts/paper_numbers.py --final
endif
	$(NICE) bash scripts/build_paper.sh

report: ## Build the explanation PDF docs/report/ (make_report.py in rm-dev; ACCOUNT=...)
	$(NEED_DEV)
	$(IN_DEV) python3 scripts/make_report.py --account $(ACCOUNT)

readme: ## Rewrite the generated result blocks of README.md (update_readme_results.py)
	$(NICE) python3 scripts/update_readme_results.py

youtube: ## Regenerate docs/YOUTUBE_DESCRIPTION.md (make_youtube_description.py)
	$(NICE) python3 scripts/make_youtube_description.py

all-docs: numbers figures paper report readme youtube ## numbers, figures, paper, report, readme, youtube (in this order)
	@echo "all-docs done."

finalize: ## After the campaigns: every result-dependent analysis (V/W/Q/A/S/X/XD gated on complete inputs), figures, paper, report, README, YouTube text, tests, consistency check (scripts/finalize_results.sh; commits nothing)
	$(NEED_DEV)
	$(NEED_LATEX)
	ACCOUNT=$(ACCOUNT) $(NICE) bash scripts/finalize_results.sh

assets: ## Fetch the AWS RoboMaker warehouse models (MIT-0) into worlds/assets/aws-wh (needed for the depot studies XD, X)
	@command -v git >/dev/null 2>&1 || { echo "ERROR: git is required to fetch the assets."; exit 1; }
	bash scripts/fetch_depot_assets.sh

video-plan: ## Write docs/video_plan.json from existing run ids (make_video_plan.py; VID_*/ADVICE override)
	$(NEED_DEV)
	$(IN_DEV) python3 scripts/make_video_plan.py $(VIDEO_ARGS)

video: video-plan ## Render the submission video from docs/video_plan.json and existing runs (narration needs rm-voicevox)
	@mkdir -p $(dir $(VIDEO_OUT))
	@for r in $(VID_DELIVER) $(VID_RECOVER) $(VID_MEMORY); do [ -d outputs/runs/$$r ] || [ -d experiments/evidence/runs/$$r ] || echo "WARN: no evidence for run $$r (outputs/runs/ is git-ignored; the shots need it or experiments/evidence/runs/)"; done
	@if docker inspect -f '{{.State.Running}}' rm-voicevox 2>/dev/null | grep -q true; then N="--narrate $(NARRATE)"; else N=""; echo "WARN: rm-voicevox is not running; rendering without narration."; fi; \
	  $(IN_DEV) python3 scripts/make_demo_video.py --plan docs/video_plan.json --out "$(VIDEO_OUT)" $$N

# --- registered studies: PRINT ONLY.  They need the GPU and a quiet host (no other Gazebo stack, no edits to rescuemind/ or scripts/). ---
define STUDY_WARN
@echo "WARNING: this target only PRINTS the registered command sequence (nothing is started)."
@echo "         Running it needs a V100-class GPU, container $(NEXT) ($(START_NEXT)), and a quiet host:"
@echo "         no other Gazebo/GPU job, port 8765 free, no edits to rescuemind/ or scripts/ meanwhile. Read the PREREGISTRATION first."
endef
CAMP = docker exec $(NEXT) rescuemind-entrypoint python3 scripts/run_campaign.py
FLAGS_D = --model Qwen/Qwen3.5-9B --prompt-set v35 --intent-backend llm --intent-prompt i35 --recovery --explain

study-D: ## (print) Study D: 42 closed-loop trials
	$(STUDY_WARN)
	@echo "[experiments/PREREGISTRATION_v34.md]  ~1.2 h"
	@echo '$(CAMP) --protocol experiments/v34_protocol.json --ledger experiments/results/campaign_D_ledger.jsonl -- $(FLAGS_D)'
	@echo '$(IN_DEV) python3 scripts/export_evidence.py experiments/results/campaign_D_ledger.jsonl'
study-E: ## (print) Study E: 60 closed-loop trials
	$(STUDY_WARN)
	@echo "[experiments/PREREGISTRATION_E.md]  ~1.7 h"
	@echo '$(CAMP) --protocol experiments/campaign_e_protocol.json --ledger experiments/results/campaign_E_ledger.jsonl -- $(FLAGS_D) --hazard-threshold 0.05'
	@echo '$(IN_DEV) python3 scripts/export_evidence.py experiments/results/campaign_E_ledger.jsonl'
study-F: ## (print) Study F: 48 paired trials (look-around)
	$(STUDY_WARN)
	@echo "[experiments/PREREGISTRATION_F.md]  ~1.4 h"
	@echo '$(CAMP) --protocol experiments/campaign_f_protocol.json --ledger experiments/results/campaign_F_ledger.jsonl'
	@echo 'docker exec $(NEXT) rescuemind-entrypoint python3 scripts/fire_mask_at_pose.py --protocol experiments/campaign_f_protocol.json --ledger experiments/results/campaign_F_ledger.jsonl'
	@echo '$(IN_DEV) python3 scripts/f_analysis.py'
study-G: ## (print) Study G: 48 paired trials (side views)
	$(STUDY_WARN)
	@echo "[experiments/PREREGISTRATION_G.md]  ~1.4 h"
	@echo '$(CAMP) --protocol experiments/campaign_g_protocol.json --ledger experiments/results/campaign_G_ledger.jsonl'
	@echo '$(IN_DEV) python3 scripts/g_analysis.py'
study-H: ## (print) Study H: 112 trials (mission memory)
	$(STUDY_WARN)
	@echo "[experiments/PREREGISTRATION_H.md]  ~3-6 h"
	@echo '$(CAMP) --protocol experiments/campaign_h_protocol.json --ledger experiments/results/campaign_H_ledger.jsonl'
	@echo '$(IN_DEV) python3 scripts/h_analysis.py && $(IN_DEV) python3 scripts/h_change_rate_model.py'
study-J: ## (print) Study J: 48 paired trials (two models; ~28 GiB VRAM)
	$(STUDY_WARN)
	@echo "[experiments/PREREGISTRATION_J.md]  ~1.5-2.5 h; log VRAM: nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -l 1 > experiments/results/campaign_J_vram.csv"
	@echo '$(CAMP) --protocol experiments/campaign_j_protocol.json --ledger experiments/results/campaign_J_ledger.jsonl'
	@echo '$(IN_DEV) python3 scripts/j_analysis.py'
study-V: ## (print) Study V: closed-loop check of H's model (160 runs; pilot, masks, predictions, campaign, analysis)
	$(STUDY_WARN)
	@echo "[experiments/PREREGISTRATION_V.md]  ~5 h.  Commit v_predictions.json BEFORE the first V trial (the script stops for it)."
	@echo 'bash scripts/v_run.sh        # run on the host from the main checkout; it drives $(NEXT)'
study-L: ## (print) Study L: randomised station layout (24 worlds)
	$(STUDY_WARN)
	@echo "[experiments/PREREGISTRATION_L.md]  (branch worktree-agent-ac85b5ba081cc1f61 until merged)"
	@echo 'bash scripts/l_run.sh        # design masks -> smoke (stops unless complete) -> campaign -> l_summary.json'
study-A: ## (print) Study A (I-19): untrusted advice, pilot + 226 runs
	$(STUDY_WARN)
	@echo "[experiments/PREREGISTRATION_A.md]  The pilot stops the script unless it behaves as designed (A_ABORT)."
	@echo 'bash scripts/a_run.sh        # pilot -> design masks -> campaign -> a_summary.json'
study-X: ## (print) Study X (I-21, DRAFT): four-bay depot closed loop (needs `make assets`)
	$(STUDY_WARN)
	@echo "[experiments/PREREGISTRATION_X.md]  needs: make assets"
	@echo 'bash scripts/x_run.sh        # X_PARTS="a m" for the core 44 runs only; use each part once'
study-W: ## (print) Study W: 675 hidden-fire images (render, score, analyse)
	$(STUDY_WARN)
	@echo "[experiments/PREREGISTRATION_W.md]  render ~2 h, score ~3 h"
	@echo 'docker exec $(NEXT) rescuemind-entrypoint bash scripts/w_render.sh'
	@echo 'bash scripts/w_eval.sh       # W_STAGES="a" or "b" to split; runs w_analysis.py -> w_summary.json'
study-S: ## (print) Study S: text-in-image attacks (276 images)
	$(STUDY_WARN)
	@echo "[experiments/PREREGISTRATION_S.md]  ~1.3 h"
	@echo 'docker exec $(NEXT) rescuemind-entrypoint bash scripts/s_render.sh'
	@echo 'bash scripts/s_eval.sh       # S_STAGES="a".."d"; analysis -> s_summary.json'
study-XD: ## (print) Study XD (DRAFT): depot image set (1932 images; needs `make assets`)
	$(STUDY_WARN)
	@echo "[experiments/PREREGISTRATION_XD.md]  render, then a person checks the smoke sheet and creates experiments/results/xd_smoke_ok"
	@echo 'docker exec $(NEXT) rescuemind-entrypoint bash scripts/xd_render.sh'
	@echo 'bash scripts/xd_eval.sh      # XD_STAGES="a" (depot) / "r" (real photographs)'
study-T1: ## (print) Study T1: 600 unused images, 6 configurations
	$(STUDY_WARN)
	@echo "[experiments/PREREGISTRATION_T1.md]"
	@echo 'docker exec $(NEXT) rescuemind-entrypoint bash scripts/t1_eval_all.sh'
	@echo '$(IN_DEV) python3 scripts/t1_analysis.py'
study-T2: ## (print) Study T2: 600 unused images, I-13 candidates
	$(STUDY_WARN)
	@echo "[experiments/PREREGISTRATION_T2.md]"
	@echo 'docker exec $(NEXT) rescuemind-entrypoint bash scripts/t2_eval.sh'
study-R: ## (print) Study R: 12 camera degradations
	$(STUDY_WARN)
	@echo "[experiments/PREREGISTRATION_R.md]  resumable; stop with scripts/stop_r.sh"
	@echo 'docker exec $(NEXT) rescuemind-entrypoint bash scripts/r_eval.sh'
	@echo '$(IN_DEV) python3 scripts/r_analysis.py'
study-P2: ## (print) Study P2: threshold calibration on real photographs
	$(STUDY_WARN)
	@echo "[experiments/PREREGISTRATION_P2.md]  host python with pyarrow (P2_PYTHON), D-Fire under ~/.cache/rescuemind/dfire; the server runs in $(NEXT)"
	@echo 'bash scripts/p2_eval.sh'
study-K: ## (print) Study K: conformal thresholds (no GPU; stored scores only)
	@echo "[experiments/PREREGISTRATION_K.md]  no GPU needed, safe to run:"
	@echo 'python3 scripts/k_conformal.py'
