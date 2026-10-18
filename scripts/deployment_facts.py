#!/usr/bin/env python3
"""Every number that docs/DEPLOYMENT.md prints, read from the result files, the world file and the code defaults (single source).

  python3 scripts/deployment_facts.py            # table: name, the exact string the guide must contain
  python3 scripts/deployment_facts.py --check    # exit 1 if docs/DEPLOYMENT.md misses one of them (also run by check_consistency.py)
  python3 scripts/deployment_facts.py --json     # the facts as JSON

Sources: experiments/results/{campaign_J_vram.csv, vram_*.txt, timing_runs.json, campaign_{D,E,G,H,L,V}_ledger.jsonl, j_summary.json,
p_summary.json, p2_summary.json, k_summary.json, l_summary.json, r_summary.json, w_summary.json, g_summary.json, h_summary.json,
i22_gazebo_check_summary.json, intent_i38_check.json, advice_credit_horizon.json}; worlds/scenarios/rescuemind_nominal.sdf;
the defaults of rescuemind/velocity_relay.py, stationary_gate.py, camera_clock_gate.py, delivery_permit.py.
Every function returns None for a missing source and the guide check then reports it; a number is never invented.
"""
from __future__ import annotations
import csv
import json
import math
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
RES = ROOT / 'experiments/results'
GUIDE = ROOT / 'docs/DEPLOYMENT.md'


def jload(name):
    f = RES / name
    return json.loads(f.read_text(encoding='utf8')) if f.is_file() else None


def ledger(name):
    f = RES / name
    if not f.is_file():
        return []
    return [r for r in (json.loads(x) for x in f.read_text(encoding='utf8').splitlines() if x.strip()) if r.get('final', True)]


def med(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return statistics.median(xs) if xs else None


def vram():
    v = [int(r['memory_used_mib']) for r in csv.DictReader((RES / 'campaign_J_vram.csv').open())]
    first_second_model = next(i for i, x in enumerate(v) if x > 20000)      # the second model is loaded at the first sample above 20 GB
    one = lambda n: int(re.search(r'(\d+)\s*MiB', (RES / n).read_text()).group(1))
    return {'qwen9b': one('vram_qwen35_9b.txt'), 'qwen4b': one('vram_qwen35_4b.txt'), 'qwen3vl8b': one('vram_qwen3vl8b.txt'),
            'mission_single_peak': max(v[:first_second_model]), 'two_models_peak': max(v)}


def sensors():
    sdf = (ROOT / 'worlds/scenarios/rescuemind_nominal.sdf').read_text()
    cam = re.search(r'<sensor name="front_camera".*?</sensor>', sdf, re.S).group(0)
    lid = re.search(r'<sensor name="scan_sensor".*?</sensor>', sdf, re.S).group(0)
    g = lambda blk, tag: float(re.search(rf'<{tag}>\s*([-0-9.]+)\s*</{tag}>', blk).group(1))
    w, h, fov = int(g(cam, 'width')), int(g(cam, 'height')), g(cam, 'horizontal_fov')
    base_z = float(re.search(r'<model name="rescue_diffbot">\s*<pose>\s*0 0 ([0-9.]+)', sdf).group(1))
    cam_z = float(re.search(r'<pose>\s*[-0-9.]+ [-0-9.]+ ([-0-9.]+) 0 0 0</pose>', cam).group(1))
    return {'cam_w': w, 'cam_h': h, 'cam_hz': int(g(cam, 'update_rate')), 'cam_fov_rad': fov, 'cam_fov_deg': math.degrees(fov),
            'fx_px': (w / 2) / math.tan(fov / 2), 'cam_height_m': base_z + cam_z,
            'lidar_hz': int(g(lid, 'update_rate')), 'lidar_samples': int(g(lid, 'samples')), 'lidar_min_m': g(lid, 'min'), 'lidar_max_m': g(lid, 'max'),
            'wheel_sep_m': g(sdf, 'wheel_separation'), 'wheel_radius_m': g(sdf, 'wheel_radius'), 'odom_hz': int(g(sdf, 'odom_publish_frequency'))}


def defaults():
    from rescuemind.velocity_relay import VelocityRelay
    from rescuemind.stationary_gate import StationaryGate
    from rescuemind.camera_clock_gate import CameraClockGate
    from rescuemind import delivery_permit as dp
    f = lambda c, n: c.__dataclass_fields__[n].default
    return {'cmd_max_age_s': f(VelocityRelay, 'cmd_max_age_s'), 'odom_max_age_s': f(VelocityRelay, 'odom_max_age_s'),
            'camera_max_age_s': f(VelocityRelay, 'camera_max_age_s'), 'scan_max_age_s': f(VelocityRelay, 'scan_max_age_s'),
            'max_linear': f(VelocityRelay, 'max_linear'), 'max_angular': f(VelocityRelay, 'max_angular'), 'min_front_m': f(VelocityRelay, 'min_front_m'),
            'still_lin': f(StationaryGate, 'max_linear_mps'), 'still_ang': f(StationaryGate, 'max_angular_rps'),
            'still_drift_m': f(StationaryGate, 'max_drift_m'), 'still_s': f(StationaryGate, 'stable_s'),
            'clock_lag_s': f(CameraClockGate, 'max_camera_lag_s'), 'clock_lead_s': f(CameraClockGate, 'max_camera_lead_s'),
            'geofence_m': dp.GEOFENCE_RADIUS_M}


def phases():
    """The rows of docs/paper/tab_timing.tex: delivered, non-recovery missions of D and E (observed_action ALLOW)."""
    timing = jload('timing_runs.json') or {}
    spec = [('drive to station', None, 'supply_station'), ('aim camera', 'supply_station', 'camera_aim_aligned'),
            ('wait until stationary', 'camera_aim_aligned', 'checkpoint_stationary_verified'),
            ('acquire and check frames', 'checkpoint_stationary_verified', 'checkpoint_frame'),
            ('VLM decision', 'checkpoint_frame', 'checkpoint_decision'), ('situation report', 'checkpoint_decision', 'checkpoint_explanation'),
            ('drive to shelter', 'checkpoint_explanation', 'shelter_approach')]
    d = {n: [] for n, _, _ in spec}
    runs = 0
    for r in ledger('campaign_D_ledger.jsonl') + ledger('campaign_E_ledger.jsonl'):
        if r['observed_action'] != 'ALLOW' or r['run_id'] not in timing:
            continue
        ev, runs = timing[r['run_id']], runs + 1
        for n, a, b in spec:
            if b in ev and (a is None or a in ev):
                d[n].append(ev[b] - (ev[a] if a else 0.0))
    return {'n': len(d['drive to shelter']), 'rows': {n: (statistics.median(v), min(v), max(v)) for n, v in d.items() if v}}


def times():
    out = {}
    for tag in ('V', 'H'):
        rows = [r for r in ledger(f'campaign_{tag}_ledger.jsonl') if r.get('config') != 'M1']          # M1 = naive memory (skips the check on purpose)
        for act in ('ALLOW', 'ALLOW_AFTER_SEARCH', 'DENY_HAZARD'):
            rs = [r for r in rows if r['observed_action'] == act]
            out[f'{tag}_{act}'] = {'n': len(rs), 'mission_s': med([r.get('mission_time_s') for r in rs]), 'latency_s': med([r.get('vlm_latency_s') for r in rs])}
        out[f'{tag}_startup_s'] = med([r['wall_s'] - r['mission_time_s'] for r in rows if isinstance(r.get('mission_time_s'), (int, float))])
    lrows = ledger('campaign_L_ledger.jsonl')
    for act in ('ALLOW', 'ALLOW_AFTER_SEARCH', 'DENY_HAZARD'):
        rs = [r for r in lrows if r['observed_action'] == act]
        out[f'L_{act}'] = {'n': len(rs), 'mission_s': med([r.get('mission_time_s') for r in rs]), 'latency_s': med([r.get('vlm_latency_s') for r in rs])}
    e = ledger('campaign_E_ledger.jsonl')
    out['E_latency_s'] = med([r.get('vlm_latency_s') for r in e])
    out['E_wall_ALLOW_s'] = med([r['wall_s'] for r in e if r['observed_action'] == 'ALLOW'])
    out['E_wall_ALLOW_AFTER_SEARCH_s'] = med([r['wall_s'] for r in e if r['observed_action'] == 'ALLOW_AFTER_SEARCH'])
    g = ledger('campaign_G_ledger.jsonl')
    gw = lambda c: med([r['wall_s'] for r in g if r['config'] == c and r['expected_action'] == 'ALLOW'])      # as the README table
    out['G_wall_B_s'], out['G_wall_C_s'] = gw('B'), gw('C')
    return out


def collect():
    F = {'vram': vram(), 'sensors': sensors(), 'defaults': defaults(), 'phases': phases(), 'times': times()}
    for k, f in (('V', 'v_summary.json'), ('J', 'j_summary.json'), ('P', 'p_summary.json'), ('P2', 'p2_summary.json'), ('K', 'k_summary.json'), ('L', 'l_summary.json'),
                 ('R', 'r_summary.json'), ('W', 'w_summary.json'), ('G', 'g_summary.json'), ('H', 'h_summary.json'), ('I22', 'i22_gazebo_check_summary.json')):
        F[k] = jload(f)
    import advice_numbers
    F['A'] = advice_numbers.a_pilot_facts()
    F['XDR'] = advice_numbers.xdr_facts()
    F['credit'] = advice_numbers.credit_facts()
    F['pooled_memory'] = advice_numbers.pooled_memory()
    return F


def s(x, nd=1):
    return f'{x:.{nd}f}'


def needles(F=None):
    """[(name, exact string that docs/DEPLOYMENT.md must contain)].  The guide is written with these strings."""
    F = F or collect()
    v, S, D, T, ph = F['vram'], F['sensors'], F['defaults'], F['times'], F['phases']
    P, P2, K, L, R, W, G, J = F['P'], F['P2'], F['K'], F['L'], F['R'], F['W'], F['G'], F['J']
    A, C, PM = F['A'], F['credit'], F['pooled_memory']
    N = []

    def add(name, text):
        N.append((name, text))
    add('VRAM Qwen3.5-9B server', f"{v['qwen9b']} MiB")
    add('VRAM mission (one model + Gazebo)', f"{v['mission_single_peak']} MiB")
    add('VRAM two models', f"{v['two_models_peak']} MiB")
    add('VRAM Qwen3.5-4B', f"{v['qwen4b']} MiB")
    add('camera resolution', f"{S['cam_w']}x{S['cam_h']}")
    add('camera rate', f"{S['cam_hz']} Hz")
    add('camera fov', f"{S['cam_fov_rad']} rad")
    add('camera fx', f"{S['fx_px']:.0f} px")
    add('camera height', f"{S['cam_height_m']:.2f} m")
    add('lidar', f"{S['lidar_samples']} 本")
    add('lidar rate', f"{S['lidar_hz']} Hz")
    add('lidar range', f"{S['lidar_min_m']:g}〜{S['lidar_max_m']:g} m")
    add('wheel separation', f"{S['wheel_sep_m']:.2f} m")
    add('odom rate', f"{S['odom_hz']} Hz")
    add('guard max linear', f"{D['max_linear']:.2f} m/s")
    add('guard max angular', f"{D['max_angular']:.2f} rad/s")
    add('guard stop distance', f"{D['min_front_m']:.2f} m")
    add('guard cmd age', f"{D['cmd_max_age_s']} s")
    add('guard odom age', f"{D['odom_max_age_s']:.1f} s")
    add('guard camera age', f"{D['camera_max_age_s']:.1f} s")
    add('stationary linear', f"{D['still_lin']} m/s")
    add('stationary angular', f"{D['still_ang']} rad/s")
    add('stationary drift', f"{D['still_drift_m']*100:.0f} cm")
    add('clock lag', f"{D['clock_lag_s']} s")
    add('clock lead', f"{D['clock_lead_s']} s")
    add('geofence radius', f"{D['geofence_m']} m")
    r = ph['rows']
    from rescuemind import layout
    add('layout standoff', f"{layout.WAYPOINT_STANDOFF_M} m")
    add('layout start distance', f"{layout.R_MIN}〜{layout.R_MAX} m")
    add('timing n', f"{ph['n']} 回")
    for key, label in (('drive to station', '拠点まで走る'), ('wait until stationary', '静止を待つ'), ('acquire and check frames', '新しい画像を取って確かめる'),
                       ('VLM decision', 'VLM の判断'), ('situation report', '状況報告'), ('drive to shelter', '避難所まで走る')):
        m, lo, hi = r[key]
        add(f'timing {key}', f"{label} {m:.1f} s（{lo:.1f}〜{hi:.1f}）")
    add('V ALLOW time', f"{T['V_ALLOW']['mission_s']:.0f} s")
    add('V ALLOW_AFTER_SEARCH time', f"{T['V_ALLOW_AFTER_SEARCH']['mission_s']:.0f} s")
    add('V DENY_HAZARD time', f"{T['V_DENY_HAZARD']['mission_s']:.0f} s")
    add('H ALLOW time', f"{T['H_ALLOW']['mission_s']:.0f} s")
    add('H ALLOW_AFTER_SEARCH time', f"{T['H_ALLOW_AFTER_SEARCH']['mission_s']:.0f} s")
    add('H DENY_HAZARD time', f"{T['H_DENY_HAZARD']['mission_s']:.0f} s")
    add('L ALLOW time', f"{T['L_ALLOW']['mission_s']:.0f} s")
    add('L DENY_HAZARD time', f"{T['L_DENY_HAZARD']['mission_s']:.0f} s")
    add('E wall ALLOW', f"{T['E_wall_ALLOW_s']:.0f} s")
    add('V check latency ALLOW', f"{T['V_ALLOW']['latency_s']:.1f} s")
    add('V check latency refusal', f"{T['V_DENY_HAZARD']['latency_s']:.0f} s")
    add('E check latency', f"{T['E_latency_s']:.1f} s")
    add('V startup', f"{T['V_startup_s']:.0f} s")
    add('G look-around cost', f"{T['G_wall_B_s']:.0f} s → {T['G_wall_C_s']:.0f} s")
    la = L['mission_time_vs_path']['ALLOW']
    add('L time vs path', f"{la['slope_s_per_m']:.1f} s/m")
    add('L time intercept', f"{la['intercept_s']:.0f} s")
    add('L expected', f"{L['primary']['expected_behaviour']}")
    add('J peak', f"{J['P1_runs_on_one_v100']['peak_vram_mib']} MiB")
    pr, pc = P['recall'], P['false_alarm']
    add('P frozen', f"{pr['k']}/{pr['n']}")
    add('P false alarms', f"{pc['k']}/{pc['n']}")
    f2 = P2['test_at_frozen_tau_0.05']
    add('P2 h36 frozen FA', f"{f2['h36']['false_alarm']['k']}/{f2['h36']['false_alarm']['n']}")
    add('P2 h35 frozen recall', f"{f2['h35']['recall']['k']}/{f2['h35']['recall']['n']}")
    add('P2 h35 frozen FA', f"{f2['h35']['false_alarm']['k']}/{f2['h35']['false_alarm']['n']}")
    ct = P2['chosen_test']
    add('P2 chosen tau', f"τ = {P2['chosen_tau']:.2f}")
    add('P2 chosen recall', f"{ct['recall']['k']}/{ct['recall']['n']}")
    add('P2 chosen FA', f"{ct['false_alarm']['k']}/{ct['false_alarm']['n']}")
    kp = K['alphas']
    add('K PAC alpha 0.05', f"τ = {kp['0.05']['K_PAC']['tau']}")
    add('K PAC alpha 0.10', f"τ = {kp['0.1']['K_PAC']['tau']}")
    add('R false approvals', f"{R['P1_pooled']['false_approvals']}/{R['P1_pooled']['n']}")
    wa = W['W-a']
    add('W front-only miss', f"{wa['miss_front_only']['k']}/{wa['miss_front_only']['n']}")
    add('W look-around miss', f"{wa['miss_look_around']['k']}/{wa['miss_look_around']['n']}")
    add('G wrong deliveries', f"{G['primary']['wrong_deliveries_B']}/{G['primary']['n_world_pairs_fire_perceivable']} → {G['primary']['wrong_deliveries_C']}/{G['primary']['n_world_pairs_fire_perceivable']}")
    add('H naive memory unsafe', f"{PM['h']['M1']}/32")
    add('pooled naive memory unsafe', f"{PM['unsafe']['M1']}/{PM['n']}")
    add('pooled verified memory unsafe', f"{PM['unsafe']['M2']}/{PM['n']}")
    il = F['I22']['totals']
    add('interlock check', f"{il['missions']} 件の動作確認で許可証 {il['permits']} 件、拒否 {il['expected_refusals']} 件")
    vm = F['V']['arms']['M2']
    add('V M2 unsafe', f"{vm['unsafe']}/{vm['n']}")
    wad = W['W-a_adaptive']
    add('W adaptive miss', f"{wad['perceivable_FLR']['miss_look_around']['k']}/150 → {wad['perceivable_FLR']['miss_adaptive']['k']}/150")
    add('W adaptive trigger twins', f"{wad['twins']['extra_view_trigger_rate']['k']}/{wad['twins']['extra_view_trigger_rate']['n']}")
    add('A pilot i35 exact', f"{A['op_exact']}/{A['op_n']}")
    add('A pilot i35 refused', f"{A['op_refused']}/{A['op_n']}")
    add('A rerun i38 intent', f"{A['rerun_op_intent']}/{A['rerun_op_n']}")
    add('A rerun i38 exact', f"{A['rerun_op_exact']}/{A['rerun_op_n']}")
    add('A rerun file', f"{A['rerun_file_ok']}/{A['rerun_file_n']}")
    add('i38 held out', f"{A['held38']}/{A['held_n']}")
    add('i38 injection', f"{A['inj35']}→{A['inj38']}/{A['inj_n']}")
    add('credit liar', f"+{C['liar_no']:.0f} 秒 → +{C['liar_yes']:.0f} 秒")
    add('credit flood', f"{C['flood_no']} 回 → {C['flood_yes']} 回")
    add('XD-R kept', f"{F['XDR']['kept']}/{F['XDR']['cand']}")
    return N


def check(text=None):
    """[(name, 'ok'|'MISMATCH', detail)] for check_consistency.py."""
    text = text if text is not None else (GUIDE.read_text(encoding='utf8') if GUIDE.is_file() else '')
    try:
        N = needles()
    except Exception as e:      # a missing source file must be visible, not silent
        return [('DEPLOYMENT.md facts readable from the result files', 'MISMATCH', f'{type(e).__name__}: {e}')]
    miss = [f'{n}: {t!r}' for n, t in N if t not in text]
    return [(f'DEPLOYMENT.md prints its {len(N)} measured numbers exactly as the result files give them', 'MISMATCH' if miss else 'ok', '; '.join(miss[:4]))]


if __name__ == '__main__':
    if '--json' in sys.argv:
        print(json.dumps(collect(), indent=1, ensure_ascii=False, default=str))
    elif '--check' in sys.argv:
        res = check()
        for n, st, d in res:
            print(f'{st:<9}{n}' + (f'  [{d}]' if d else ''))
        sys.exit(1 if any(st == 'MISMATCH' for _, st, _ in res) else 0)
    else:
        for n, t in needles():
            print(f'{n:<40}{t}')
