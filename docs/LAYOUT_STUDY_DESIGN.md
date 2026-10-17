# Study L: per-trial layout randomisation (design, read-only analysis)

Fixed geometry: start (0,0) yaw 0; station centres W(2,2), M(-2,2), shelter B(3,-2); waypoints = centre minus 1.2 m toward the origin (W 1.18,1.13; M -1.16,1.10; B 2.15,-1.12). Ground 16x12 (no walls, no other obstacles).

## 1. Fixed-layout assumptions
- configs/gazebo_waypoints.json (water/medicine/B + limits); configs/gazebo_station_centers.json (W/M centres).
- worlds/scenarios/*.sdf: aid_station_water :50, aid_station_medicine :76, shelter_B :102, props sealed_water_bottles :391 and first_aid_case :913 (each sits at its station xy; swapped scene exchanges them), robot :127 (0,0,.16).
- rescuemind/robust_scenes.py: STATIONS :22 drives platform_side_offset :83-87, hazard_xy :182-189 (approach = origin-to-station direction), hazard_visibility :194, hazard_visible :212, _platform_empty :224, build_variant :232-290 (empty_at :250, prop_offsets :251, distractor :258-283 with world-frame offsets, hazard :284-288).
- rescuemind/scene_variants.py: PROPS/STATIONS :16-17; build_scenarios :76-83 and audit_scenarios :123-143 (station/prop pose equality, SHA256 in SCENES_MANIFEST.json). These audit only the base scenario files, so they stay valid if layout is applied only in generated variants.
- rescuemind/camera_aim.py:37-44 station_centers() rejects anything but (2,2)/(-2,2); aim_at_station raises if range < 0.45.
- ros/gazebo_waypoint_mission.py: route_from_config :38-52 (|x|>6 check is "any", effectively weak); centres re-read from ROOT in onsite_check :248 and schedule_look_around :449-450 (look-around L/R = waypoint +/- d perpendicular to waypoint-to-centre, :447-466); recovery waypoint :637 (reads args.config); --config :665 and route :758; start check hypot>1.0 :550; WaypointController :149-150 (peek tol .08).
- scripts/v32_orchestrate.py: WORLD_SPEC_KEYS :39; audits read ROOT config at :218 (memory_trusted_audit), :479 (live audit; used :498/:508/:518), :547 (denial audit; used :566 and classify_negative_run waypoints); make_world :319-335; mission argv in build_plan ~:88 has no --config; audit_scenarios :306-308; scene_sha256 of base SDF.
- Audits take station/shelter as arguments (good): motion_evidence.py:17 (start <0.6 m from origin :64), ground_truth_evidence.py:61 (start <0.3 :66; denial requires closest_shelter >= 1.0 :93, so station and shelter waypoints must be >= ~1.5 m apart), negative_evidence.py:18, causal_evidence.py:19, v24_trial_outcome.py:46. recovery_evidence.py has no coordinates.
- Config readers: rescuemind/v24_run_registry.py:54, v25_projection.py:34-35 (static, default world), stack_contract.py:51-58 (static, default SDF, keep).
- rescuemind/arena_geometry.py:11-17 hard-coded station rectangles (used by scripts/validate_gazebo_world.py:36,47).
- scripts/fire_mask_at_pose.py:28 DESIGN_POSE (-> :104,:107); scripts/make_demo_video.py:278-283 labels and hazard_xy; scripts/build_image_set.py and robust_devset_build.py import STATIONS (offline image sets; leave).
- Lidar/watchdog: min_front 0.26 m, +/-0.52 rad cone; platforms have collision, fire is visual only. Controller is turn-then-straight go-to-goal with no avoidance, so every leg must be clear by construction.

## 2. Minimal change plan
1. robust_scenes: add `layout` = {water:[x,y,yaw], medicine:[...], B:[...]} and `layout_stations(layout)`; give platform_side_offset/hazard_xy/hazard_visible* an optional `stations=` argument (default STATIONS). In build_variant first move the station models, B, and each supply prop (match prop to original station by xy; translate and rotate about the centre; prop/model yaw is local so rotating the model suffices), then compute empty_at/distractor/hazard from the layout. Add 'layout' to WORLD_SPEC_KEYS.
2. New rescuemind/layouts.py: `sample_layout(seed)`, `waypoints_for(layout)` (centre - 1.2 m * unit(centre)), `feasible(layout, look_around=0.4, hazard geometry, distractor)` with rotated-rectangle distance (generalises arena_geometry).
3. Orchestrator: if world_spec has layout, write log_dir/layout_waypoints.json (base config copy with new water/medicine/B) and layout_centers.json; pass `--config` and new `--centers` to the mission (build_plan); replace the three ROOT config reads with `cfg_path`. Mission: read centres from `--centers` in :248 and :449; relax station_centers() with an `expected=` argument (keep the lock by default); registry :54 reads the run-dir file.
4. Layout constraints (rejection sampling from a pre-registered seed, stored in the protocol): centres at radius 2.2-4.0 from start, |x|<=4.5, |y|<=3.5; angular separation >= 40 deg between targets; centre-to-centre >= 2.5 m; waypoint-to-waypoint >= 1.5 m, each waypoint >= 1.0 m from start; every executed segment (start-W/M, W-M for recovery, station-B, look-around L, R points and the L-R-B legs) >= 0.6 m from all footprints (stations 0.9 sq, B 1.0x0.8 rotated, fire disk r 0.4 at hazard_xy, distractor); view line waypoint-to-centre clear of other objects; yaw uniform +/-45 deg. Also check offline with waypoint.simulate_route.
5. Fire masks: fire_mask_at_pose builds the same variant, so logged-pose labelling (--ledger) works unchanged. Replace DESIGN_POSE by a function: point 0.2 m short of the waypoint on the start-waypoint line, yaw = bearing to centre.
6. make_demo_video labels from the run's layout file. Protocol generator make_protocol_l.py with sha-locked layouts; tests for layouts and build_variant.

## 3. Risks and effort
- The running campaign re-reads shared files per trial. Develop in a git worktree, keep defaults byte-identical (no change to default paths/hashes), merge only after it ends.
- Audit false failures (shelter >= 1.0 m rule, start tolerances); any missed ROOT config read silently audits the wrong coordinates, so add a test that greps for the config path.
- Camera aiming and visible-fire fraction vary with layout, so use mask-based labels and pre-register the exclusion rule for ambiguous trials.
- Straight-line drift can clip platforms; margin 0.6 m and a dry run of 3-5 layouts in Gazebo (no VLM) first.
- Memory (I-15) is station-keyed; do not mix with L.
- Effort: ~1 day code and tests, ~0.5 day protocol and Gazebo dry run, then trial time as for campaign J.
