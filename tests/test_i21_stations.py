"""I-21 phase 2: k supply stations (k = 4 in the depot) without changing the two-station arena.  Pure functions only."""
import hashlib
import itertools
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'ros'))
from PIL import Image  # noqa: E402
from rescuemind import advice as adv  # noqa: E402
from rescuemind.camera_aim import station_centers  # noqa: E402
from rescuemind.local_vision import PRIMARY_MODEL, local_decision  # noqa: E402
from rescuemind.mission_memory import MissionMemory, apply_memory_caution  # noqa: E402
from rescuemind.recovery_evidence import RecoveryEvidenceError, audit_recovery  # noqa: E402
from rescuemind.stations import (StationSet, check_centers, next_candidate, plan_order,  # noqa: E402
                                 validate_visits)

INV4 = {'W1': 'water', 'M1': 'medicine', 'W2': 'water', 'M2': 'medicine'}
SS4 = StationSet.build(['W1', 'M1', 'W2', 'M2'], INV4)
A = lambda kind, station=None, source='operator', text='': {'kind': kind, 'station': station, 'source': source, 'text': text}


def cfg4():
    return {'initial': [0, 0], 'W1': [1.18, 1.13], 'M1': [-1.16, 1.1], 'W2': [-1.7, -0.9], 'M2': [-0.1, -1.8],
            'B': [2.15, -1.12], 'physical_pickup': False, 'stations': SS4.to_block()}


class StationSetTests(unittest.TestCase):
    def test_arena_is_the_default_and_unchanged(self):
        ss = StationSet.from_config(json.loads((ROOT / 'configs/gazebo_waypoints.json').read_text()))
        self.assertTrue(ss.is_legacy())
        self.assertEqual(ss.order('water'), ['water', 'medicine'])
        self.assertEqual(ss.order('medicine'), ['medicine', 'water'])
        self.assertEqual(ss.order('water', first='medicine'), ['medicine', 'water'])
        self.assertEqual(ss.catalog('medicine'), 'medicine')

    def test_k4_candidate_order_is_the_inventory_then_the_rest(self):
        self.assertEqual(SS4.order('water'), ['W1', 'W2', 'M1', 'M2'])
        self.assertEqual(SS4.order('medicine'), ['M1', 'M2', 'W1', 'W2'])
        self.assertEqual(SS4.order('water', first='M2'), ['M2', 'W1', 'W2', 'M1'])      # reorder, nothing dropped
        self.assertEqual(sorted(SS4.order('water', first='M2')), sorted(SS4.ids))

    def test_recovery_order_visits_every_candidate_once_in_order(self):
        order, checked, seq = SS4.order('water'), [], []
        while True:
            nxt = next_candidate(order, checked)
            if nxt is None:
                break
            seq.append(nxt); checked.append(nxt)
        self.assertEqual(seq, order)             # first check + k-1 recovery checks, then stop
        self.assertEqual(len(seq), 4)
        self.assertEqual(next_candidate(order, ['W1']), 'W2')
        self.assertEqual(next_candidate(order, ['W1', 'M1']), 'W2')       # strictly the first unchecked one

    def test_validate_visits_rejects_skips_and_repeats(self):
        order = SS4.order('water')
        validate_visits(order, ['W1']); validate_visits(order, order[:3]); validate_visits(order, order)
        for bad in (['W1', 'M1'], ['W2'], ['W1', 'W1'], ['W1', 'W2', 'M2'], ['W1', 'W2', 'M1', 'M2', 'X']):
            with self.assertRaises(ValueError):
                validate_visits(order, bad)

    def test_config_validation(self):
        self.assertEqual(StationSet.from_config(cfg4()), SS4)
        for mutate in (lambda c: c['stations']['inventory'].pop('W2'), lambda c: c.pop('M2'),
                       lambda c: c['stations']['inventory'].update(W1='toy'), lambda c: c['stations'].update(ids=['W1', 'W1']),
                       lambda c: c['stations']['ids'].append('B')):
            c = cfg4(); mutate(c)
            with self.assertRaises(ValueError):
                StationSet.from_config(c)
        with self.assertRaises(ValueError):                  # no station listed for medicine
            StationSet.build(['a', 'b'], {'a': 'water', 'b': 'water'})

    def test_resolve_operator_names(self):
        self.assertEqual(SS4.resolve('water'), 'W1'); self.assertEqual(SS4.resolve('medicine'), 'M1')
        self.assertEqual(SS4.resolve('M2'), 'M2'); self.assertIsNone(SS4.resolve(None))
        self.assertEqual(StationSet.legacy().resolve('water'), 'water')

    def test_centers_file(self):
        c = {'W1': [2, 2], 'M1': [-2, 2], 'W2': [-2.8, -1.4], 'M2': [-0.2, -3.0]}
        self.assertEqual(set(station_centers(c, locked=False)), set(SS4.ids))
        check_centers(station_centers(c, locked=False), SS4)
        with self.assertRaises(ValueError):
            check_centers(station_centers({'water': [3.0, 1.0], 'medicine': [-1.0, 3.2]}, locked=False), SS4)
        with self.assertRaises(ValueError):
            station_centers(c)                                # the locked default is still the arena's two

    def test_route_from_config(self):
        import gazebo_waypoint_mission as mission
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'w.json'; p.write_text(json.dumps(cfg4()))
            self.assertEqual(mission.route_from_config(p, 'water')[0], ('supply_station', 'W1', [1.18, 1.13]))
            self.assertEqual(mission.route_from_config(p, 'medicine', station='M2')[0][1:], ('M2', [-0.1, -1.8]))
            self.assertEqual(mission.route_from_config(p, 'water')[1][1], 'B')
            for item, st in (('toy', None), ('water', 'water'), ('water', 'X')):
                with self.assertRaises(ValueError):
                    mission.route_from_config(p, item, station=st)
        for item in ('water', 'medicine'):                   # the arena config: unchanged
            r = mission.route_from_config(ROOT / 'configs/gazebo_waypoints.json', item)
            self.assertEqual([x[1] for x in r], [item, 'B'])


def obs(station, supply, hazard=False, tag='t'):
    return {'tag': tag, 'station': station, 'supply': supply, 'hazard': hazard, 'hazard_views': ['front'] if hazard else [],
            'hazard_prob_max': 0.0, 'views_checked': ['front']}


class MemoryOverFourStations(unittest.TestCase):
    def memory(self, records):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'm.jsonl'
            p.write_text(''.join(json.dumps(r) + '\n' for r in records))
            return MissionMemory(p)

    def test_empty_memory_keeps_the_inventory_order(self):
        p = self.memory([]).plan('water', 'verified', stations=SS4)
        self.assertEqual((p['first_station'], p['order'], p['catalog_station']), ('W1', ['W1', 'W2', 'M1', 'M2'], 'W1'))

    def test_arena_plan_is_byte_identical_to_before(self):
        p = self.memory([]).plan('water', 'verified')
        self.assertEqual(p, {'mode': 'verified', 'catalog_station': 'water', 'first_station': 'water', 'n_records': 0,
                             'caution': {}, 'skip_check': False, 'deny_without_visit': False, 'rationale': []})

    def test_relocated_supply_goes_first_never_skips(self):
        m = self.memory([obs('W1', 'medicine'), obs('M2', 'water')])
        p = m.plan('water', 'verified', stations=SS4)
        self.assertEqual(p['order'], ['M2', 'W2', 'M1', 'W1'])          # seen there; unknown next; known-wrong last
        self.assertEqual(sorted(p['order']), sorted(SS4.ids))
        self.assertEqual(p['first_station'], 'M2')

    def test_no_reorder_without_evidence_for_another_station(self):
        p = self.memory([obs('W1', 'medicine')]).plan('water', 'verified', stations=SS4)
        self.assertEqual(p['order'], ['W1', 'W2', 'M1', 'M2'])

    def test_caution_is_per_station_over_k(self):
        p = self.memory([obs('M2', 'medicine', hazard=True)]).plan('water', 'verified', stations=SS4)
        self.assertEqual(set(p['caution']), {'M2'})


def decide(plan, station, p_hazard, allow_front):
    """The mission's decision at `station` for one frame pair under `plan` (as in tests/test_advice.py)."""
    if plan.get('skip_check'):
        return True
    if plan.get('deny_without_visit'):
        return False
    d = {'allow': allow_front, 'reason': 'on_site_supply_confirmed' if allow_front else 'x'}
    c = (plan.get('caution') or {}).get(station)
    call = {'scores': {'hazard_prob': p_hazard}}
    return apply_memory_caution(d, call, call, c['tau_h'] if c else None)['allow']


class AdviceOverFourStations(unittest.TestCase):
    def test_location_reorders_and_keeps_every_candidate(self):
        p = adv.plan('water', [A('location', 'M2')], 'monotone', stations=SS4)
        self.assertEqual(p['order'], ['M2', 'W1', 'W2', 'M1']); self.assertEqual(p['first_station'], 'M2')
        self.assertEqual(plan_order(p, SS4, 'water'), p['order'])

    def test_unknown_station_rejected_and_arena_names_are_not_depot_ids(self):
        for st in ('water', 'X'):
            with self.assertRaises(adv.AdviceError):
                adv.plan('water', [A('location', st)], 'monotone', stations=SS4)

    def test_monotone_catches_a_dropped_candidate(self):
        before = adv.base_plan('water', SS4)
        after = dict(before, order=['W1', 'W2', 'M1'])
        with self.assertRaises(adv.AdviceError):
            adv.assert_monotone(before, after, SS4)
        with self.assertRaises(adv.AdviceError):
            adv.assert_monotone(before, dict(before, first_station='M2'), SS4)         # head and first_station disagree

    def test_audit_plan_recomputes_the_invariant(self):
        p = adv.plan('water', [A('location', 'M1'), A('hazard', 'W1', 'peer')], 'monotone', stations=SS4)
        self.assertTrue(adv.audit_plan(p)['checked'])
        p['order'] = p['order'][:3]
        with self.assertRaises(adv.AdviceError):
            adv.audit_plan(p)

    def test_memory_proposal_keeps_priority_over_k(self):
        base = adv.base_plan('water', SS4); base['first_station'] = 'M2'; base['order'] = SS4.order('water', 'M2')
        p = adv.plan('water', [A('location', 'M1')], 'monotone', base, stations=SS4)
        self.assertEqual(p['first_station'], 'M2')

    def test_operator_text_names_resolve_to_inventory_stations(self):
        from rescuemind import advice_llm
        plan = advice_llm.plan_for_mission(
            'water', None, mode='monotone', from_instruction=True, instruction='x', stations=SS4,
            extract_fn=lambda text, **kw: {'items': [A('location', 'medicine')], 'probs': None, 'error': None})
        self.assertEqual(plan['first_station'], 'M1')

    def test_random_adversarial_advice_k4(self):
        """Extends test_advice.Monotonicity to k = 4: for ANY advice set and any model outputs the monotone plan approves a
        station only if the no-advice plan does, the order is a permutation of all four stations (nothing skipped), and
        the audit recomputes the invariant from the logged plan alone."""
        rng = random.Random(4)
        pool = [A(k, s, src, 't') for k in adv.KINDS for s in SS4.ids for src in adv.SOURCES]
        for _ in range(3000):
            item = rng.choice(('water', 'medicine'))
            items = rng.sample(pool, rng.randint(0, 7))
            for k, it in enumerate(items):
                if it['kind'] in ('safe', 'skip') and rng.random() < .5:
                    items[k] = dict(it, station=None)
            base = adv.base_plan(item, SS4)
            p = adv.plan(item, items, 'monotone', stations=SS4)
            self.assertEqual(sorted(p['order']), sorted(SS4.ids))
            self.assertEqual(p['order'][0], p['first_station'])
            self.assertTrue(adv.audit_plan(p)['checked'])
            for st, ph, ok in itertools.product(SS4.ids, (0.0, 0.004, 0.02, 0.2), (True, False)):
                if decide(p, st, ph, ok):
                    self.assertTrue(decide(base, st, ph, ok))

    def test_random_memory_then_advice_k4(self):
        rng = random.Random(5)
        pool = [A(k, s, src, 't') for k in adv.KINDS for s in SS4.ids for src in adv.SOURCES]
        for _ in range(500):
            item = rng.choice(('water', 'medicine'))
            recs = [obs(rng.choice(SS4.ids), rng.choice(('water', 'medicine', 'other', 'uncertain')), rng.random() < .3,
                        tag=f't{i}') for i in range(rng.randint(0, 8))]
            with tempfile.TemporaryDirectory() as d:
                path = Path(d) / 'm.jsonl'
                path.write_text(''.join(json.dumps(r) + '\n' for r in recs))
                mem = MissionMemory(path).plan(item, 'verified', stations=SS4)
            self.assertEqual(sorted(mem['order']), sorted(SS4.ids))
            p = adv.plan(item, rng.sample(pool, rng.randint(0, 5)), 'monotone', mem, stations=SS4)
            self.assertEqual(sorted(p['order']), sorted(SS4.ids))
            adv.assert_monotone(mem, p, SS4)


def resp(pass_id, supply, sha, probs):
    return {'backend': 'local_transformers', 'real_inference': True, 'model': PRIMARY_MODEL, 'image_sha256': sha,
            'pass_id': pass_id, 'result': {'supply': supply, 'scene': 'clear'},
            'scores': {'method': 'closed_set_logprob', 'supply_probs': probs, 'hazard_prob': 0.01, 'hazard_threshold': 0.05}}


class RecoveryChainAudit(unittest.TestCase):
    """audit_recovery accepts a k = 4 recovery sequence in candidate order and rejects a skipped / repeated candidate."""

    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.addCleanup(self.t.cleanup)
        self.dir = Path(self.t.name)
        self.m = self.build(3)

    def hop(self, k):
        img = self.dir / (('recovery_' if k == 0 else f'recovery{k + 1}_') + 'checkpoint.jpg')
        Image.new('RGB', (64, 48), (200, 30 + k * 20, 30)).save(img)
        sha = hashlib.sha256(img.read_bytes()).hexdigest()
        probs = {'water': 0.01, 'medicine': 0.9, 'other': 0.09}
        a, b = resp(1, 'medicine', sha, probs), resp(2, 'medicine', sha, probs)
        cp = {'checkpoint_type': 'local_on_site_camera_supply_check', 'image_sha256': sha, 'backend': 'LOCAL_ONLY_NO_CLOUD_API',
              'mode': 'single', 'model_calls': {'first': a, 'second': b}, 'decision': local_decision('water', a, b)}
        return cp, img.name, sha

    def build(self, n_denied, order=('W1', 'W2', 'M1', 'M2')):
        """n_denied wrong-supply denials, then the final checkpoint at the next candidate."""
        stages, hops_ = [], [self.hop(k) for k in range(n_denied)]
        for _ in range(n_denied):
            stages += ['recovery_supply_station', 'recovery_checkpoint_frame', 'recovery_checkpoint_decision',
                       'recovery_checkpoint_denial_dwell_finished', 'recovery_search_started']
        stages += ['supply_station', 'checkpoint_frame', 'checkpoint_decision']
        events = [{'stage': s, 't_wall_s': float(i)} for i, s in enumerate(stages)]
        for k, (_, _, sha) in enumerate(hops_):
            events[k * 5 + 1]['image_sha256'] = sha
        rec = {'first_station': order[0], 'first_checkpoint': hops_[0][0], 'first_checkpoint_image': hops_[0][1],
               'searched_station': order[n_denied], 'candidates': list(order), 'reason': 'local_vlm_disagree_or_wrong_supply'}
        if n_denied > 1:
            rec['hops'] = [{'station': order[k], 'checkpoint': hops_[k][0], 'checkpoint_image': hops_[k][1]}
                           for k in range(1, n_denied)]
        return {'intent': {'item': 'water'}, 'checkpoint_station': order[n_denied], 'events': events,
                'checkpoint': {'decision': {'allow': True}}, 'recovery': rec}

    def test_three_denials_then_confirmation_passes(self):
        r = audit_recovery(self.m, self.dir, completed=True)
        self.assertEqual((r['visited'], r['n_checks']), (['W1', 'W2', 'M1', 'M2'], 4))
        self.assertEqual((r['first_station'], r['searched_station']), ('W1', 'M2'))

    def test_every_chain_length_passes(self):
        for n in (1, 2, 3):
            audit_recovery(self.build(n), self.dir, completed=True)

    def test_exhausted_candidates_denial_passes_uncompleted(self):
        m = self.build(3); m['checkpoint'] = {'decision': {'allow': False}}
        self.assertTrue(audit_recovery(m, self.dir, completed=False)['pass'])
        with self.assertRaises(RecoveryEvidenceError):
            audit_recovery(m, self.dir, completed=True)

    def test_skipped_candidate_rejected(self):
        m = self.build(2)
        m['recovery']['hops'][0]['station'] = 'M1'           # W1 -> M1 skips W2
        m['recovery']['searched_station'] = 'M2'; m['checkpoint_station'] = 'M2'
        with self.assertRaises(RecoveryEvidenceError):
            audit_recovery(m, self.dir, completed=True)

    def test_skipped_last_candidate_rejected(self):
        m = self.build(3)
        m['recovery']['searched_station'] = 'M1'; m['checkpoint_station'] = 'M1'      # M1 searched twice
        with self.assertRaises(RecoveryEvidenceError):
            audit_recovery(m, self.dir, completed=True)

    def test_memory_reordered_candidates_are_accepted(self):
        audit_recovery(self.build(2, order=('M2', 'W1', 'W2', 'M1')), self.dir, completed=True)

    def test_hop_must_be_a_wrong_supply_denial(self):
        m = self.build(3)
        m['recovery']['hops'][1]['checkpoint']['decision']['reason'] = 'visible_hazard_at_checkpoint'
        with self.assertRaises(RecoveryEvidenceError):
            audit_recovery(m, self.dir, completed=True)

    def test_tampered_hop_image_and_missing_event_rejected(self):
        (self.dir / 'recovery3_checkpoint.jpg').write_bytes(b'x' * 500)
        with self.assertRaises(RecoveryEvidenceError):
            audit_recovery(self.m, self.dir, completed=True)
        m = self.build(3); del m['events'][12]
        with self.assertRaises(RecoveryEvidenceError):
            audit_recovery(m, self.dir, completed=True)

    def test_search_count_must_match_hops(self):
        m = self.build(3); m['recovery'].pop('hops')
        with self.assertRaises(RecoveryEvidenceError):
            audit_recovery(m, self.dir, completed=True)


class ReportAndMemoryOfASearch(unittest.TestCase):
    """The k-station search chain feeds memory (every checked station) and the operator report (every check, JA names)."""

    def setUp(self):
        sys.path.insert(0, str(ROOT / 'tests'))
        import test_i15_memory as t15
        import test_i18_operator_report as t18
        self.t15, self.t18 = t15, t18

    def chain(self):
        t15 = self.t15
        m = t15.mission('M2', 'water', 'water')
        m['recovery'] = {'first_station': 'W1', 'first_checkpoint': t15.checkpoint('medicine', 'water'), 'searched_station': 'M2',
                         'candidates': ['W1', 'W2', 'M1', 'M2'],
                         'hops': [{'station': 'W2', 'checkpoint': t15.checkpoint('other', 'water')},
                                  {'station': 'M1', 'checkpoint': t15.checkpoint('medicine', 'water')}]}
        return m

    def test_memory_learns_every_checked_station(self):
        from rescuemind.mission_memory import observations
        o = observations(self.chain(), 'r1')
        self.assertEqual([(x['station'], x['supply']) for x in o],
                         [('W1', 'medicine'), ('W2', 'other'), ('M1', 'medicine'), ('M2', 'water')])
        # ... and the next plan goes to M2 first (every other station was seen holding something else)
        with tempfile.TemporaryDirectory() as d:
            mem = MissionMemory(Path(d) / 'm.jsonl'); mem.append_mission(self.chain(), 'r1')
            self.assertEqual(mem.plan('water', 'verified', stations=SS4)['order'], ['M2', 'W1', 'W2', 'M1'])

    def test_operator_report_lists_all_checks_in_order(self):
        t18 = self.t18
        m = dict(t18.BASE, checkpoint_station='M2', checkpoint=t18.cp('on_site_supply_confirmed', True), recovery=self.chain()['recovery'])
        for h in m['recovery']['hops']:
            h['checkpoint'] = t18.cp('local_vlm_disagree_or_wrong_supply', False, supply='water')
        m['recovery']['first_checkpoint'] = t18.cp('local_vlm_disagree_or_wrong_supply', False, supply='water')
        r = t18.build(m, {'state': 'COMPLETED'})
        self.assertEqual([c['station'] for c in r['checks']], ['W1', 'W2', 'M1', 'M2'])
        self.assertEqual(r['outcome']['kind'], 'delivered_after_search')


if __name__ == '__main__':
    unittest.main()
