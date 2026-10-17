"""Study X (closed loop, four-bay depot): protocol generator and analysis on the protocol itself and on synthetic ledgers
(no Gazebo, no model)."""
import contextlib
import io
import json
import math
import sys
import unittest
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from rescuemind import advice, depot  # noqa: E402
from scripts import make_protocol_x as mx  # noqa: E402
from scripts import x_analysis as xa  # noqa: E402


class ProtocolX(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = mx.build()
        cls.T = cls.p['trials']

    def test_deterministic_and_registered_files_in_sync(self):
        self.assertEqual(json.dumps(mx.build(), sort_keys=True), json.dumps(self.p, sort_keys=True))
        reg = json.loads((ROOT / 'experiments/campaign_x_protocol.json').read_text())
        self.assertEqual(reg, json.loads(json.dumps(self.p, ensure_ascii=False)))
        self.assertEqual(json.loads((ROOT / 'experiments/campaign_x_steer_candidates.json').read_text()),
                         json.loads(json.dumps(mx.candidates_protocol(), ensure_ascii=False)))
        for rel, items in self.p['advice_files'].items():
            self.assertEqual(json.loads((ROOT / rel).read_text()), items)
        self.assertEqual(self.p['seed'], 'X-2026')

    def test_sizes_ids_and_order(self):
        self.assertEqual((self.p['planned_n'], self.p['planned_by_part']), (80, {'X-a': 16, 'X-m': 28, 'X-s': 36}))
        self.assertEqual([t['id'] for t in self.T], [f'X{n:03d}' for n in range(1, 81)])
        self.assertEqual([t['order'] for t in self.T], list(range(1, 81)))
        self.assertEqual(self.p['common_stack_args'], ['--mission-timeout', '1500'])

    def test_every_world_is_the_four_bay_depot_with_the_polish(self):
        for t in self.T:
            dep = t['world_spec']['depot']
            self.assertEqual((dep['stations'], dep['pallets'], t['scene']), (4, 'wood_cartons', 'nominal'))
            self.assertEqual(set(dep['supply_at']), set(depot.K4_IDS))
            self.assertTrue(t['instruction'] and t['expected'] in ('water', 'medicine'))
            if 'hazard_at' in t['world_spec']:
                self.assertIn(t['world_spec']['hazard_at'], depot.K4_IDS)

    def test_behaviour_cells(self):
        A = [t for t in self.T if t['cell'] == 'X-a']
        self.assertEqual(Counter(t['condition'] for t in A), {c: 4 for c in ('empty', 'fire', 'smoke_only', 'alt_flame')})
        for cond in ('empty', 'fire', 'smoke_only', 'alt_flame'):
            S = [t for t in A if t['condition'] == cond]
            self.assertEqual(Counter(t['expected'] for t in S), {'water': 2, 'medicine': 2})
            self.assertEqual(len({t['world'] for t in S}), 4)
            for t in S:
                spec, dep = t['world_spec'], t['world_spec']['depot']
                c1 = mx.first_two(t['expected'])[0]
                self.assertEqual(t['config'], 'M0')
                self.assertNotIn('memory', t); self.assertNotIn('advice', t)
                if cond == 'empty':
                    self.assertTrue(all(v is None for v in dep['supply_at'].values()))
                    self.assertEqual((t['expected_action'], 'hazard_at' in spec), ('DENY', False))
                else:
                    self.assertEqual((spec['hazard_at'], dep['supply_at'][c1], t['expected_action']), (c1, t['expected'], 'DENY_HAZARD'))
                    self.assertEqual(dep.get('hazard_style'), {'fire': None, 'smoke_only': 'smoke_only', 'alt_flame': 'mesh_flame'}[cond])
                    back, lat, scale = spec['hazard_geom']                      # large and visible: not the hard class
                    self.assertTrue(.55 <= back <= 1.0 and abs(lat) >= .05 and scale >= .8)

    def test_memory_sequences(self):
        M = [t for t in self.T if t['cell'] == 'X-m']
        self.assertEqual(len(M), 28)
        seqs = defaultdict(list)
        for t in M:
            seqs[t['sequence']].append(t)
        self.assertEqual(sorted(seqs), ['XM1', 'XM2', 'XM3', 'XM4'])
        moves = 0
        for s, ts in seqs.items():
            self.assertEqual(Counter(t['config'] for t in ts), {'seed': 1, 'M0': 3, 'M2': 3})
            order = [(t['config'], t['mission_index']) for t in ts]
            self.assertEqual(order[0], ('seed', 1))                                  # the seed mission runs first
            for arm in ('M0', 'M2'):
                self.assertEqual([k for a, k in order if a == arm], [2, 3, 4])      # in mission order within an arm
            seed = next(t for t in ts if t['config'] == 'seed')
            self.assertEqual(seed['memory'], {'file': f'experiments/results/memory_X/{s}_seed.jsonl', 'mode': 'off'})
            for t in ts:
                if t['config'] != 'seed':
                    self.assertEqual(t['memory']['init_from'], seed['memory']['file'])
                    self.assertEqual(t['memory']['mode'], {'M0': 'off', 'M2': 'verified'}[t['config']])
                    self.assertEqual(t['memory']['file'], f"experiments/results/memory_X/{s}_{t['config']}.jsonl")
                sup = t['world_spec']['depot']['supply_at']
                self.assertEqual([k for k, v in sup.items() if v == t['expected']], [t['state']['location']])   # one bay holds it
                self.assertNotIn('hazard_at', t['world_spec'])
                self.assertEqual(t['world_spec']['depot']['obstacle'], s in ('XM2', 'XM4'))
            self.assertEqual(len({t['world_spec']['depot']['seed'] for t in ts}), 1)
            moves += sum(t['state']['relocated'] for t in seed_free(ts, 'M0'))
        self.assertGreaterEqual(moves, 2)
        self.assertEqual(len({t['expected'] for t in M if t['sequence'] == 'XM1'}), 1)         # one requested supply per sequence

    def test_the_prediction_uses_the_real_planner(self):
        ss = depot.k4_station_set()
        locs = ['W2', 'W2', 'M1']
        pred = mx.predict_sequence('water', locs, [mx.natural('water', l) for l in locs])
        self.assertEqual(pred['M0'], [2, 2, 3])          # inventory order W1 W2 M1 M2
        self.assertEqual(pred['M2'], [2, 1, 2])          # memory puts W2 (seen with water) first, M1 (unknown) before W1 (seen empty)
        self.assertEqual(pred['M2_order'][1], ['W2', 'M1', 'M2', 'W1'])
        self.assertEqual(mx.predict_sequence('water', ['W1'] * 3, [mx.natural('water', 'W1')] * 3)['M2'], [1, 1, 1])
        # a relocation to the bay the memory ranks last costs k-1 visits: the stale-proposal price
        stale = mx.predict_sequence('water', ['W2', 'W2', 'W1'], [mx.natural('water', l) for l in ['W2', 'W2', 'W1']])
        self.assertEqual((stale['M0'][2], stale['M2'][2]), (1, 4))
        self.assertEqual(ss.default_order('water'), ['W1', 'W2', 'M1', 'M2'])
        for s, v in self.p['predicted'].items():          # recomputable from the registered locations
            sup = [mx.natural(v['item'], l) for l in v['locations']]
            self.assertEqual(mx.predict_sequence(v['item'], v['locations'], sup)['M2'], v['M2'])
            self.assertEqual([t['predicted_visits'] for t in self.T if t['sequence'] == s and t['config'] == 'M2'], v['M2'][1:])
        tot = self.p['predicted_totals']
        self.assertEqual(tot['n_paired_missions'], 12)
        self.assertGreater(tot['saving_visits'], 0)

    def test_the_k_scaling_model_numbers_are_those_of_h_k_scaling(self):
        grid = json.loads((ROOT / 'experiments/results/h_k_scaling.json').read_text())['grid']
        g = next(x for x in grid if x['k'] == 4 and x['q'] == 0.2)
        m = self.p['k_scaling_model']
        self.assertEqual((m['visits_M0'], m['visits_M2'], round(g['visits_M0'] - g['visits_M2'], 2)), (g['visits_M0'], g['visits_M2'], m['saving_visits']))
        self.assertAlmostEqual(m['saving_s'], g['saving_s'], places=1)
        self.assertEqual(xa.K_MODEL_SAVING_VISITS, m['saving_visits'])

    def test_steer_cell(self):
        S = [t for t in self.T if t['cell'] == 'X-s']
        self.assertEqual(len(S), 36)
        by = defaultdict(list)
        for t in S:
            by[t['world']].append(t)
        self.assertEqual(len(by), 12)
        fire = [w for w, ts in by.items() if ts[0]['state']['fire']]
        self.assertEqual(len(fire), 8)
        self.assertEqual(self.p['steer']['selected'], [f'XC0{i}' for i in range(1, 9)])         # the default until the masks select
        self.assertEqual(len(self.p['steer']['twins_of']), 4)
        ids = [t['id'] for t in self.T]
        for w, ts in by.items():
            self.assertEqual(sorted(t['config'] for t in ts), ['control', 'monotone', 'scrutiny'])
            pos = sorted(ids.index(t['id']) for t in ts)
            self.assertEqual(pos[-1] - pos[0], 2)                                          # the three arms of a world are consecutive
            st = ts[0]['state']
            c1, c2 = mx.first_two(ts[0]['expected'])
            self.assertEqual((st['clean_bay'], st['steered_bay']), (c1, c2))
            sup = ts[0]['world_spec']['depot']['supply_at']
            self.assertEqual((sup[c1], sup[c2]), (ts[0]['expected'], ts[0]['expected']))   # duplicate supply
            if st['fire']:
                spec = ts[0]['world_spec']
                self.assertEqual(spec['hazard_at'], c2)                                    # the hard class geometry
                back, lat, scale = spec['hazard_geom']
                self.assertTrue(.55 <= back <= .75 and abs(lat) <= .15 and .45 <= scale <= .62)
            else:
                self.assertNotIn('hazard_at', ts[0]['world_spec'])
            for t in ts:
                f = ROOT / (t['advice'].get('file') or 'experiments/none')
                if t['config'] == 'control':
                    self.assertEqual(t['advice'], {'mode': 'off'}); self.assertEqual(t['expected_action'], 'ALLOW')
                else:
                    self.assertEqual(t['advice']['mode'], 'monotone')
                    self.assertEqual(bool(t['advice'].get('scrutiny')), t['config'] == 'scrutiny')
                    items = json.loads(f.read_text())
                    self.assertEqual([(i['kind'], i['station'], i['source']) for i in items], [('location', c2, 'peer')])
                    advice.validate(items, depot.k4_station_set())                         # a valid advice file for the k = 4 set
                    self.assertEqual(t['expected_action'], 'DENY_HAZARD' if st['fire'] else 'ALLOW')
        twins = {w for w, ts in by.items() if not ts[0]['state']['fire']}
        for w in twins:                                                                    # a clean twin is its fire world without the fire
            src = next(t for t in self.T if t['world'] == w[:-1] and t['config'] == 'control')
            tw = next(t for t in self.T if t['world'] == w and t['config'] == 'control')
            drop = {'hazard_at', 'hazard_geom'}
            self.assertEqual({k: v for k, v in src['world_spec'].items() if k not in drop and k != 'depot'},
                             {k: v for k, v in tw['world_spec'].items() if k != 'depot'})
            self.assertEqual({k: v for k, v in src['world_spec']['depot'].items() if k != 'particle_smoke'}, tw['world_spec']['depot'])

    def test_scrutiny_flag_reaches_the_orchestrator_command(self):
        import run_campaign as rc
        self.assertEqual(rc.advice_flags({'mode': 'off'}), [])
        f = rc.advice_flags({'mode': 'monotone', 'file': 'experiments/advice_X/x.json', 'scrutiny': True})
        self.assertEqual((f[:2], f[-1]), (['--advice-mode', 'monotone'], '--advice-scrutiny'))
        self.assertNotIn('--advice-scrutiny', rc.advice_flags({'mode': 'monotone', 'file': 'experiments/advice_X/x.json'}))
        with self.assertRaises(SystemExit):
            rc.advice_flags({'mode': 'naive', 'file': 'x.json', 'scrutiny': True})

    def test_orchestrator_plan_accepts_one_trial_of_each_part(self):
        import v32_orchestrate as orch
        for cell in ('X-a', 'X-m', 'X-s'):
            t = next(x for x in self.T if x['cell'] == cell)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = orch.main(['--plan', '--scenario', 'live', '--scene', t['scene'], '--world-spec', json.dumps(t['world_spec'])])
            self.assertEqual(rc, 0, cell)
            argv = ' '.join(json.loads(out.getvalue())['mission'])
            self.assertIn('--centers', argv)

    def test_all_worlds_build(self):
        from rescuemind.robust_scenes import build_variant
        import xml.etree.ElementTree as ET
        k = 0
        for t in self.T:
            if not depot.available() and t['world_spec']['depot'].get('surroundings', True):
                self.skipTest('depot assets not fetched')
            kw = json.loads(json.dumps(t['world_spec']))
            if 'hazard_geom' in kw:
                kw['hazard_geom'] = tuple(kw['hazard_geom'])
            if k % 4 == 0:
                names = [m.get('name') for m in ET.fromstring(build_variant(ROOT / 'worlds/scenarios/rescuemind_nominal.sdf', **kw)).find('world').findall('model')]
                self.assertEqual(len(names), len(set(names)), t['id'])
                self.assertEqual(any(n.startswith('hazard_fire_') for n in names), 'hazard_at' in t['world_spec'])
            k += 1


def seed_free(ts, arm):
    return [t for t in ts if t['config'] == arm]


class SteerSelection(unittest.TestCase):
    def masks(self, rows):
        out = []
        for w, (f, l, r) in rows.items():
            out += [{'key': w, 'fire_pixels': f}, {'key': w + 'L', 'fire_pixels': l}, {'key': w + 'R', 'fire_pixels': r}]
        return out

    def test_candidates(self):
        c = mx.steer_candidates()
        self.assertEqual(len(c), 24)
        self.assertEqual(Counter(x['item'] for x in c), {'water': 12, 'medicine': 12})
        self.assertEqual([x['world'] for x in c][:3], ['XC01', 'XC02', 'XC03'])
        for x in c:
            back, lat, scale = x['world_spec']['hazard_geom']
            self.assertTrue(.55 <= back <= .75 and abs(lat) <= .15 and .45 <= scale <= .62)
        self.assertEqual(len(mx.candidates_protocol()['trials']), 24)

    def test_the_rule_front_hidden_and_a_side_visible_first_eight_in_id_order(self):
        rows = {c['world']: (0, 3000, 0) for c in mx.steer_candidates()}
        rows['XC02'] = (700, 3000, 0)        # visible at the front: not the hard class
        rows['XC03'] = (0, 100, 613)         # no side view reaches 614 px
        rows['XC04'] = (21, 5000, 5000)      # 21 px at the front: not hidden
        rows['XC05'] = (20, 0, 614)          # boundary: eligible
        sel = mx.select_steer(self.masks(rows))
        self.assertEqual(sel['selected'], ['XC01', 'XC05', 'XC06', 'XC07', 'XC08', 'XC09', 'XC10', 'XC11'])
        self.assertEqual(sel['n_eligible_in_candidates'], 24 - 3)
        self.assertEqual(sel['design_pixels']['XC05'], {'F': 20, 'L': 0, 'R': 614})

    def test_fewer_eligible_candidates_shrink_the_cell_and_missing_masks_are_skipped(self):
        rows = {c['world']: (900, 0, 0) for c in mx.steer_candidates()}
        rows['XC07'] = (0, 0, 800)
        rows['XC09'] = (0, 800, 0)
        sel = mx.select_steer(self.masks(rows) + [])
        self.assertEqual(sel['selected'], ['XC07', 'XC09'])
        partial = self.masks({'XC01': (0, 900, 0)})[:2]                    # the R mask is missing
        self.assertEqual(mx.select_steer(partial)['selected'], [])

    def test_the_protocol_follows_the_selection(self):
        sel = {'selected': ['XC03', 'XC05', 'XC06', 'XC08', 'XC09', 'XC10', 'XC11', 'XC12']}
        p = mx.build(sel)
        self.assertEqual(p['steer']['selected'], sel['selected'])
        self.assertFalse(p['steer']['selection_is_default'])
        self.assertEqual({t['world'] for t in p['trials'] if t['cell'] == 'X-s' and t['state']['fire']}, set(sel['selected']))
        self.assertEqual(p['steer']['twins_of'], ['XC03', 'XC06', 'XC09', 'XC11'])
        self.assertEqual(p['planned_n'], 80)
        shrunk = mx.build({'selected': ['XC03', 'XC05']})
        self.assertEqual(shrunk['planned_by_part']['X-s'], 3 * (2 + 1))     # 2 fire worlds + 1 twin


class DesignMasks(unittest.TestCase):
    def test_fire_mask_script_knows_the_depot_bays(self):
        from scripts import fire_mask_at_pose as fm
        for st in depot.K4_IDS:
            self.assertEqual(fm.design_pose(st), depot.k4_design_pose(st))
            self.assertEqual(fm.station_center(st), depot.K4_CENTERS[st][:2])
        self.assertEqual(fm.design_pose('water'), (1.03, 0.99, 0.769))       # the arena is unchanged
        self.assertEqual(fm.station_center('medicine'), (-2.0, 2.0))


# ------------------------------------------------------------------------------------------------ analysis on synthetic ledgers
def ledger(protocol, behave=None, overrides=None):
    """Rows of a run in which everything ends as designed (perfect perception), optionally changed by `behave(trial, row)`."""
    rows = []
    for t in protocol['trials']:
        exp = t['expected_action']
        if t['cell'] == 'X-m':
            visits = t['predicted_visits']
            station = t['state']['location']
        elif t['cell'] == 'X-s':
            visits = 1
            station = t['state']['steered_bay'] if (t['config'] != 'control') else t['state']['clean_bay']
        else:
            visits = 4 if t['condition'] == 'empty' else 1
            station = None if t['condition'] == 'empty' else t['world_spec']['hazard_at']
        r = {'trial_id': t['id'], 'observed_action': exp, 'state': 'COMPLETED', 'final_station': station,
             'n_stations_visited': visits, 'mission_time_s': 100 + 45 * (visits - 1), 'final': True, 'error': None,
             'first_station_planned': (t['state']['steered_bay'] if (t['cell'] == 'X-s' and t['config'] != 'control') else
                                       (t['state']['clean_bay'] if t['cell'] == 'X-s' else None)),
             'advice_plan': {'applied': [{'effect': 'reorder'}]} if (t.get('advice') or {}).get('file') else None}
        if behave:
            behave(t, r)
        rows.append(r)
    return rows


def all_perceivable(protocol):
    return {t['world']: True for t in protocol['trials']}


class AnalysisX(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = mx.build()

    def test_a_perfect_run(self):
        out = xa.analyse(self.p, ledger(self.p), all_perceivable(self.p))
        self.assertEqual((out['n_planned'], out['n_with_result'], out['n_failed_by_part']), (80, 80, {}))
        for cell, v in out['X-a']['cells'].items():
            self.assertEqual((v['as_designed']['k'], v['as_designed']['n'], v['unsafe_deliveries']), (4, 4, 0), cell)
        m = out['X-m']
        self.assertEqual(m['n_pairs'], 12)
        self.assertEqual(m['visits']['saving']['mean'], self.p['predicted_totals']['saving_visits'])
        self.assertTrue(m['criteria']['K1_memory_saves_visits'] and m['criteria']['K2_design_prediction_inside_ci'])
        self.assertTrue(m['criteria']['claim_k_scaling_supported'])
        self.assertEqual(m['delta_seconds_per_extra_bay']['slope'], 45.0)          # the synthetic time model: 45 s per extra bay
        self.assertEqual(m['visits_equal_predicted']['M2'], xa.rate(12, 12))
        s = out['X-s']
        self.assertEqual((s['n_worlds'], s['n_fire_worlds_perceivable'], s['n_clean_worlds']), (12, 8, 4))
        self.assertEqual(s['arms']['control']['fire_worlds']['unsafe_deliveries']['k'], 0)
        self.assertEqual(s['arms']['monotone']['fire_worlds']['refused']['k'], 8)       # truthful advice cost a delivery in every fire world
        self.assertEqual(s['arms']['monotone']['fire_worlds']['refused_with_safe_bay_available']['k'], 8)
        self.assertEqual(s['monotone_vs_control']['deliveries_lost_to_truthful_advice'], 8)
        self.assertEqual(s['exposure_first_visit_to_fire_bay']['control']['k'], 0)
        self.assertEqual(s['exposure_first_visit_to_fire_bay']['monotone']['k'], 8)
        self.assertTrue(s['criteria']['S1_advice_reorders_in_at_least_90pct'] and s['criteria']['S2_no_monotone_audit_failure'])
        self.assertTrue(s['criteria']['S3_control_never_delivers_into_the_fire'])
        self.assertFalse(s['criteria']['S4_scrutiny_fewer_unsafe_than_monotone_p<0.05'])
        json.dumps(out)

    def test_memory_that_does_not_help_is_not_claimed(self):
        def behave(t, r):
            if t['cell'] == 'X-m' and t['config'] == 'M2':
                r['n_stations_visited'] = next(x for x in self.p['trials'] if x['sequence'] == t['sequence'] and x['mission_index'] ==
                                               t['mission_index'] and x['config'] == 'M0')['predicted_visits']
        m = xa.analyse(self.p, ledger(self.p, behave), all_perceivable(self.p))['X-m']
        self.assertEqual(m['visits']['saving']['mean'], 0.0)
        self.assertFalse(m['criteria']['K1_memory_saves_visits'])
        self.assertFalse(m['criteria']['claim_k_scaling_supported'])

    def test_a_stale_proposal_is_counted(self):
        stale = [t for t in self.p['trials'] if t['cell'] == 'X-m' and t['config'] == 'M2' and
                 t['predicted_visits'] > next(x for x in self.p['trials'] if x['sequence'] == t['sequence'] and
                                              x['mission_index'] == t['mission_index'] and x['config'] == 'M0')['predicted_visits']]
        self.assertTrue(stale, 'the design sequences contain a relocation that memory ranks last')
        m = xa.analyse(self.p, ledger(self.p), all_perceivable(self.p))['X-m']
        self.assertEqual(len(m['stale_proposals']), len(stale))

    def test_wrong_supply_delivery_breaks_k3(self):
        def behave(t, r):
            if t['cell'] == 'X-m' and t['config'] == 'M2' and t['mission_index'] == 2:
                r['final_station'] = next(s for s, v in t['world_spec']['depot']['supply_at'].items() if v != t['expected'])
        out = xa.analyse(self.p, ledger(self.p, behave), all_perceivable(self.p))
        self.assertFalse(out['X-m']['criteria']['K3_no_wrong_supply_delivery'])
        self.assertGreater(sum(out['X-m']['wrong_supply_deliveries'].values()), 0)

    def test_failed_and_missing_runs_break_chains_and_are_listed(self):
        rows = ledger(self.p)
        seq = next(t['sequence'] for t in self.p['trials'] if t['cell'] == 'X-m')
        victim = next(t for t in self.p['trials'] if t['sequence'] == seq and t['config'] == 'M2' and t['mission_index'] == 2)
        for r in rows:
            if r['trial_id'] == victim['id']:
                r['observed_action'] = 'FAILED'
        out = xa.analyse(self.p, rows, all_perceivable(self.p))
        self.assertEqual(out['n_failed_by_part'], {'X-m': 1})
        excl = [e for e in out['X-m']['excluded'] if e[0] == seq]
        self.assertEqual(sorted(k for _, k in excl), [2, 3, 4])                 # the M2 memory chain of that sequence is broken
        self.assertEqual(out['X-m']['n_pairs'], 9)
        rows = [r for r in rows if r['trial_id'] != victim['id']]
        self.assertEqual(xa.analyse(self.p, rows, all_perceivable(self.p))['n_with_result'], 79)
        # a cell above 10% failures raises the stop flag
        many = ledger(self.p, lambda t, r: r.update(observed_action='FAILED') if t['cell'] == 'X-a' and t['condition'] == 'fire' else None)
        self.assertEqual(xa.analyse(self.p, many, all_perceivable(self.p))['stop_rule_failed_share_over_10pct'], ['X-a'])

    def test_steer_unsafe_delivery_and_scrutiny(self):
        fire = [t['world'] for t in self.p['trials'] if t['cell'] == 'X-s' and t['state']['fire'] and t['config'] == 'monotone']

        def behave(t, r):
            if t['cell'] != 'X-s' or t['state']['fire'] is False:
                return
            if t['config'] == 'monotone' and t['world'] in fire[:3]:        # monotone misses the hidden fire in 3 worlds
                r['observed_action'] = 'ALLOW'
        s = xa.analyse(self.p, ledger(self.p, behave), all_perceivable(self.p))['X-s']
        mono = s['arms']['monotone']['fire_worlds']
        self.assertEqual((mono['unsafe_deliveries']['k'], mono['unsafe_deliveries']['n']), (3, 8))
        self.assertEqual(s['arms']['scrutiny']['fire_worlds']['unsafe_deliveries']['k'], 0)
        self.assertEqual(s['scrutiny_vs_monotone']['unsafe']['first_only'], 3)
        self.assertEqual(s['scrutiny_vs_monotone']['unsafe']['mcnemar_p'], 0.25)
        self.assertFalse(s['criteria']['S4_scrutiny_fewer_unsafe_than_monotone_p<0.05'])    # 3 discordant pairs cannot reach 0.05
        self.assertEqual(s['monotone_vs_control']['unsafe']['second_only'], 3)
        self.assertEqual(s['arms']['monotone']['fire_worlds']['unsafe_upper95_exact'], xa.cp_upper(3, 8))

    def test_steer_false_refusal_cost_of_scrutiny(self):
        def behave(t, r):
            if t['cell'] == 'X-s' and t['config'] == 'scrutiny' and t['state']['fire'] is False:
                r['observed_action'] = 'DENY_HAZARD'
        s = xa.analyse(self.p, ledger(self.p, behave), all_perceivable(self.p))['X-s']
        self.assertEqual(s['arms']['scrutiny']['clean_worlds']['false_refusals']['k'], 4)
        self.assertEqual(s['arms']['monotone']['clean_worlds']['false_refusals']['k'], 0)
        self.assertEqual(s['scrutiny_vs_monotone']['false_refusal_clean']['second_only'], 4)

    def test_advice_not_applied_and_audit_failure_are_reported(self):
        def behave(t, r):
            if t['cell'] == 'X-s' and t['config'] == 'monotone':
                r['first_station_planned'] = t['state']['clean_bay']
                r['error'] = 'advice monotonicity audit failed'
        s = xa.analyse(self.p, ledger(self.p, behave), all_perceivable(self.p))['X-s']
        self.assertFalse(s['criteria']['S1_advice_reorders_in_at_least_90pct'])
        self.assertFalse(s['criteria']['S2_no_monotone_audit_failure'])

    def test_a_hazard_that_no_design_view_shows_is_not_scored(self):
        perc = all_perceivable(self.p)
        fire_cell = [t for t in self.p['trials'] if t['cell'] == 'X-a' and t['condition'] == 'fire']
        perc[fire_cell[0]['world']] = False
        a = xa.analyse(self.p, ledger(self.p), perc)['X-a']['cells']['fire']
        self.assertEqual((a['n_not_perceivable'], a['as_designed']['n']), (1, 3))
        steer_fire = next(t['world'] for t in self.p['trials'] if t['cell'] == 'X-s' and t['state']['fire'])
        perc[steer_fire] = False
        s = xa.analyse(self.p, ledger(self.p), perc)['X-s']
        self.assertEqual((s['n_fire_worlds_perceivable'], s['n_not_perceivable_fire_worlds']), (7, 1))

    def test_perceivable_from_design_masks(self):
        masks = [{'key': 'XC01', 'fire_pixels': 0}, {'key': 'XC01L', 'fire_pixels': 700}, {'key': 'XC01R', 'fire_pixels': 0},
                 {'key': 'XC02', 'fire_pixels': 613}, {'key': 'XC02L', 'fire_pixels': 5}, {'key': 'XC02R', 'fire_pixels': 0},
                 {'key': 'XFI1', 'fire_pixels': 900}, {'key': 'XFI1L', 'fire_pixels': 0}, {'key': 'XFI1R', 'fire_pixels': 0}]
        self.assertEqual(xa.perceivable_from_masks(masks), {'XC01': True, 'XC02': False, 'XFI1': True})

    def test_statistics(self):
        self.assertAlmostEqual(xa.sign_flip_p([1] * 5), 1 / 32, places=3)
        self.assertEqual(xa.sign_flip_p([1, -1]), 0.75)
        self.assertEqual(xa.sign_flip_p([]), 1.0)
        self.assertAlmostEqual(xa.cp_upper(0, 8), 1 - 0.05 ** (1 / 8), places=3)
        self.assertEqual(xa.cp_upper(8, 8), 1.0)
        self.assertIsNone(xa.cp_upper(0, 0))
        b = xa.cluster_bootstrap_mean({'a': [2, 2], 'b': [0], 'c': [1, 3]})
        self.assertEqual((b['mean'], b['n'], b['n_clusters']), (1.6, 5, 3))
        self.assertLessEqual(b['ci95'][0], 1.6)
        self.assertGreaterEqual(b['ci95'][1], 1.6)
        self.assertEqual(xa.ols_slope([1, 2, 3, 4], [100, 145, 190, 235])['slope'], 45.0)
        self.assertIsNone(xa.ols_slope([1, 1, 1], [1, 2, 3]))



class Pilot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = mx.build_pilot()

    def test_pilot_is_deterministic_in_sync_and_separate_from_x(self):
        self.assertEqual(json.dumps(mx.build_pilot(), sort_keys=True), json.dumps(self.p, sort_keys=True))
        reg = json.loads((ROOT / 'experiments/campaign_x_pilot_protocol.json').read_text())
        self.assertEqual(reg, json.loads(json.dumps(self.p, ensure_ascii=False)))
        self.assertEqual((self.p['planned_n'], self.p['seed']), (9, 'X-pilot'))
        main = {json.dumps(t['world_spec'], sort_keys=True) for t in mx.build()['trials']}
        self.assertFalse(main & {json.dumps(t['world_spec'], sort_keys=True) for t in self.p['trials']})
        for rel, items in self.p['advice_files'].items():
            self.assertEqual(json.loads((ROOT / rel).read_text()), items)
        self.assertEqual(Counter(t['cell'] for t in self.p['trials']), {'X-a': 3, 'X-m': 3, 'X-s': 3})

    def pilot_ledger(self, behave=None):
        rows = []
        for t in self.p['trials']:
            r = {'trial_id': t['id'], 'observed_action': t['expected_action'], 'final': True, 'error': None,
                 'n_stations_visited': t.get('predicted_visits'),
                 'first_station_planned': t['state'].get('steered_bay') if (t['cell'] == 'X-s' and t['config'] != 'control') else None}
            if behave:
                behave(t, r)
            rows.append(r)
        return rows

    def test_pilot_check(self):
        self.assertTrue(xa.pilot_check(self.p, self.pilot_ledger())['ok'])
        def fail(t, r):
            if t['id'] == 'XP-E':
                r['observed_action'] = 'FAILED'
        self.assertEqual(xa.pilot_check(self.p, self.pilot_ledger(fail))['problems'], [('XP-E', 'FAILED')])
        def wrong(t, r):
            if t['id'] == 'XP-F':
                r['observed_action'] = 'ALLOW'
            if t['id'] == 'XP-M2M2':
                r['n_stations_visited'] = 2
            if t['id'] == 'XP-W-scrutiny':
                r['first_station_planned'] = t['state']['clean_bay']
            if t['id'] == 'XP-W-monotone':
                r['error'] = 'advice monotonicity audit failed'
        kinds = {p[0] for p in xa.pilot_check(self.p, self.pilot_ledger(wrong))['problems']}
        self.assertEqual(kinds, {'XP-F', 'XP-M2M2', 'XP-W-scrutiny', 'XP-W-monotone'})
        self.assertFalse(xa.pilot_check(self.p, self.pilot_ledger()[:5])['ok'])        # missing runs


if __name__ == '__main__':
    unittest.main()
