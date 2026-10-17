"""I-19 scrutiny (--advice-scrutiny): the station that advice moved to the front gets caution + the I-20 extra views.
It can only tighten.  Pure functions plus the mission node run with simulated ROS messages (NOT Gazebo)."""
import itertools
import json
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'ros'))
from rescuemind import advice as adv  # noqa: E402
from rescuemind.mission_memory import apply_memory_caution, CAUTION_TAU_H  # noqa: E402
from rescuemind.stations import StationSet  # noqa: E402
import test_i21_recovery_run as rr  # noqa: E402
from test_caution_soft import CAUT, CLEAR, SIDE_CLEAR, SIDE_HAZ, SOFT, calls  # noqa: E402

SS4 = StationSet.build(['W1', 'M1', 'W2', 'M2'], rr.INV4)
A = lambda kind, station=None, source='peer', text='': {'kind': kind, 'station': station, 'source': source, 'text': text}
TAU_H = 0.05          # the v3.6 hazard threshold


def decide(plan, station, p_front, p_extra, allow_front):
    """The mission's approval at `station` under `plan` for one frame set: front + caution, then (if scrutinised) the extra
    views.  Extra views refuse at the standard threshold or the caution threshold, whichever the station carries."""
    if plan.get('skip_check'):
        return True
    if plan.get('deny_without_visit'):
        return False
    d = {'allow': allow_front, 'reason': 'on_site_supply_confirmed' if allow_front else 'x'}
    c = (plan.get('caution') or {}).get(station)
    call = {'scores': {'hazard_prob': p_front}}
    ok = apply_memory_caution(d, call, call, c['tau_h'] if c else None)['allow']
    if ok and station in (plan.get('scrutiny') or []):
        ok = p_extra < min(TAU_H, c['tau_h'] if c else TAU_H)
    return ok


class PlanRules(unittest.TestCase):
    def test_default_off_changes_nothing(self):
        rng = random.Random(1)
        pool = [A(k, s, src) for k in adv.KINDS for s in adv.STATIONS for src in adv.SOURCES]
        for _ in range(300):
            item = rng.choice(adv.STATIONS)
            items = rng.sample(pool, rng.randint(0, 5))
            plain = adv.plan(item, items, 'monotone')
            self.assertEqual(plain, adv.plan(item, items, 'monotone', scrutiny=False))
            self.assertNotIn('scrutiny', plain)
            self.assertNotIn('scrutiny', plain['advice']['base'])

    def test_location_advice_that_moves_the_head_gets_scrutiny(self):
        p = adv.plan('water', [A('location', 'M1')], 'monotone', stations=SS4, scrutiny=True)
        self.assertEqual(p['order'][0], 'M1'); self.assertEqual(p['scrutiny'], ['M1'])
        self.assertEqual(p['caution']['M1']['tau_h'], CAUTION_TAU_H)
        self.assertEqual(adv.audit_plan(p)['scrutiny'], ['M1'])
        self.assertTrue(p['advice']['applied'][0]['scrutiny'])
        a = adv.plan('water', [A('location', 'medicine')], 'monotone', scrutiny=True)       # the 2-station arena
        self.assertEqual((a['first_station'], a['scrutiny']), ('medicine', ['medicine']))

    def test_no_reorder_no_scrutiny(self):
        for items in ([], [A('location', 'W1')], [A('hazard', 'W2')], [A('safe', 'W1'), A('skip')]):
            p = adv.plan('water', items, 'monotone', stations=SS4, scrutiny=True)
            self.assertNotIn('scrutiny', p)
        base = adv.base_plan('water', SS4); base['first_station'] = 'M2'; base['order'] = SS4.order('water', 'M2')
        p = adv.plan('water', [A('location', 'M1')], 'monotone', base, stations=SS4, scrutiny=True)
        self.assertEqual(p['first_station'], 'M2'); self.assertNotIn('scrutiny', p)           # memory keeps priority

    def test_combines_with_a_hazard_claim_by_taking_the_stricter_threshold(self):
        base = adv.base_plan('water', SS4); base['caution'] = {'M1': {'tau_h': 0.004, 'first_side': 'R', 'seen_in': 'memory'}}
        p = adv.plan('water', [A('location', 'M1')], 'monotone', base, stations=SS4, scrutiny=True)
        self.assertEqual((p['caution']['M1']['tau_h'], p['caution']['M1']['first_side']), (0.004, 'R'))

    def test_only_the_monotone_mode_gets_it(self):
        for mode in ('naive', 'off'):
            p = adv.plan('water', [A('location', 'M1')], mode, stations=SS4, scrutiny=True)
            self.assertNotIn('scrutiny', p); self.assertNotIn('scrutiny', p['advice'])
        p = adv.plan('water', [A('location', 'M1')], 'filtered', stations=SS4, scrutiny=True, filter_fn=lambda a: {'flag': False})
        self.assertNotIn('scrutiny', p)

    def test_audit_rejects_scrutiny_that_advice_did_not_earn_or_that_loosens(self):
        p = adv.plan('water', [A('location', 'M1')], 'monotone', stations=SS4, scrutiny=True)
        bad = json.loads(json.dumps(p)); bad['scrutiny'].append('W2'); bad['caution']['W2'] = {'tau_h': .01}
        with self.assertRaises(adv.AdviceError):
            adv.audit_plan(bad)                                           # W2 was not moved to the front
        bad = json.loads(json.dumps(p)); bad['caution']['M1']['tau_h'] = 0.03
        with self.assertRaises(adv.AdviceError):
            adv.audit_plan(bad)                                           # scrutiny without the caution threshold
        with self.assertRaises(adv.AdviceError):                          # dropping scrutiny relative to the base is a loosening
            adv.assert_monotone(dict(p, **{}), {k: v for k, v in p.items() if k != 'scrutiny'}, SS4)

    def test_exhaustive_item_sets_pass_the_audit(self):
        pool = [A(k, s) for k in ('location', 'hazard') for s in SS4.ids] + [A('safe', 'W1'), A('skip')]
        n = 0
        for r in range(0, 6):
            for items in itertools.combinations(pool, r):
                p = adv.plan('water', list(items), 'monotone', stations=SS4, scrutiny=True)
                self.assertTrue(adv.audit_plan(p)['checked']); n += 1
        self.assertGreater(n, 400)


class Property(unittest.TestCase):
    def test_scrutiny_only_tightens_relative_to_monotone_and_to_no_advice(self):
        """Any advice set, any frames: an approval under monotone+scrutiny is an approval under plain monotone AND under no
        advice at the same frames (same order, so the same stations are visited)."""
        rng = random.Random(11)
        pool = [A(k, s, src) for k in adv.KINDS for s in SS4.ids for src in adv.SOURCES]
        n_tighter = 0
        for _ in range(2500):
            item = rng.choice(('water', 'medicine'))
            items = rng.sample(pool, rng.randint(0, 6))
            for k, it in enumerate(items):
                if it['kind'] in ('safe', 'skip') and rng.random() < .5:
                    items[k] = dict(it, station=None)
            base = adv.base_plan(item, SS4)
            mono = adv.plan(item, items, 'monotone', stations=SS4)
            scru = adv.plan(item, items, 'monotone', stations=SS4, scrutiny=True)
            self.assertEqual(scru['order'], mono['order'])                      # reorder only, identically
            self.assertEqual(sorted(scru['order']), sorted(SS4.ids))
            self.assertTrue(adv.audit_plan(scru)['checked'])
            self.assertFalse(scru['skip_check'] or scru['deny_without_visit'])
            for st, pf, pe, ok in itertools.product(SS4.ids, (0.0, 0.004, 0.02, 0.2), (0.0, 0.004, 0.02, 0.2), (True, False)):
                a_s, a_m, a_b = decide(scru, st, pf, pe, ok), decide(mono, st, pf, pe, ok), decide(base, st, pf, pe, ok)
                if a_s:
                    self.assertTrue(a_m and a_b)
                n_tighter += a_m and not a_s
        self.assertGreater(n_tighter, 100)          # it does tighten (so the property is not vacuous)


class Audit(unittest.TestCase):
    def mission(self, **kw):
        plan = adv.plan('water', [A('location', 'M1')], 'monotone', stations=SS4, scrutiny=True)
        m = {'memory': plan, 'advice_scrutiny': True, 'checkpoint_station': 'M1',
             'checkpoint': {'decision': {'allow': True}, 'memory_caution_tau_h': CAUTION_TAU_H,
                            'look_around': {'adaptive': {'scrutiny': True, 'triggered': True},
                                            'peeks': [{'side': s} for s in ('L', 'R', 'L2', 'R2', 'N')]}}}
        m.update(kw)
        return m

    def test_a_scrutinised_approval_needs_caution_and_the_three_extra_views(self):
        self.assertTrue(adv.audit_scrutiny(self.mission())['checked'])
        m = self.mission(); m['checkpoint']['look_around']['peeks'].pop()
        with self.assertRaises(adv.AdviceError):
            adv.audit_scrutiny(m)
        m = self.mission(); m['checkpoint']['memory_caution_tau_h'] = None
        with self.assertRaises(adv.AdviceError):
            adv.audit_scrutiny(m)
        m = self.mission(); m['checkpoint']['look_around']['adaptive'] = {'triggered': True}      # extra views for another reason
        with self.assertRaises(adv.AdviceError):
            adv.audit_scrutiny(m)
        with self.assertRaises(adv.AdviceError):
            adv.audit_scrutiny(self.mission(advice_scrutiny=False))
        m = self.mission(); m['checkpoint']['look_around']['peeks'] = [{'side': 'L'}, {'side': 'R'}] + [{'side': 'N'}] * 3
        with self.assertRaises(adv.AdviceError):          # three views of ONE extra pose are not the three extra poses
            adv.audit_scrutiny(m)

    def test_a_refusal_or_a_run_without_scrutiny_is_not_constrained(self):
        m = self.mission(); m['checkpoint'] = {'decision': {'allow': False}}
        self.assertFalse(adv.audit_scrutiny(m)['checked'])
        self.assertEqual(adv.audit_scrutiny({'memory': {'caution': {}}}), {'scrutiny': [], 'checked': False})
        m = self.mission(checkpoint_station='W1')
        self.assertFalse(adv.audit_scrutiny(m)['checked'])


class Node(unittest.TestCase):
    EXTRA = {'look_around': 0.4, 'advice_scrutiny': True}

    def memory(self):
        # advice moved W1 (not the inventory head here: the inventory head for 'water' is W1, so use medicine items)
        p = adv.plan('medicine', [A('location', 'W2')], 'monotone', stations=SS4, scrutiny=True)
        p['first_station'] = p['order'][0]
        return p

    def run_node(self, verdicts, extra=None, order=None):
        p = self.memory()
        return rr.run(order or p['order'], verdicts, stations=SS4, memory=p, extra_args=dict(self.EXTRA, **(extra or {})))

    def test_scrutinised_station_takes_the_extra_views_though_nothing_was_suspicious(self):
        r, err = self.run_node([CLEAR] + [SIDE_CLEAR] * 5)
        self.assertIsNone(err); self.assertEqual(r['checkpoint_station'], 'W2')
        la = r['look_around']
        self.assertEqual([p['side'] for p in la['peeks']], ['L', 'R', 'L2', 'R2', 'N'])
        self.assertTrue(la['adaptive']['scrutiny']); self.assertTrue(la['adaptive']['triggered'])
        self.assertEqual(la['adaptive']['offset_m'], 0.8)
        self.assertEqual(len(r['_calls']), 6)
        self.assertTrue(adv.audit_scrutiny(r)['checked'])
        self.assertEqual(r['checkpoint']['memory_caution_tau_h'], CAUTION_TAU_H)

    def test_without_the_flag_the_same_plan_takes_no_extra_views(self):
        r, err = self.run_node([CLEAR] + [SIDE_CLEAR] * 5, extra={'advice_scrutiny': False})
        self.assertIsNone(err); self.assertEqual(len(r['_calls']), 3)
        self.assertNotIn('adaptive', r['look_around'])

    def test_a_hazard_in_an_extra_view_refuses(self):
        r, err = self.run_node([CLEAR, SIDE_CLEAR, SIDE_CLEAR, SIDE_HAZ, SIDE_CLEAR, SIDE_CLEAR])
        self.assertIn('DENIED: visible_hazard_at_checkpoint (look-around L2)', err)

    def test_other_stations_are_not_scrutinised(self):
        # the first station refuses for a wrong supply; the next candidate is not the advice-promoted one
        r, err = self.run_node([rr.WRONG[:2] + (calls(.001),), CLEAR, SIDE_CLEAR, SIDE_CLEAR])
        self.assertIsNone(err); self.assertEqual(checks(r), ['W2', 'M1'])
        self.assertEqual(len(r['_calls']), 4); self.assertNotIn('adaptive', r['look_around'])

    def test_scrutiny_with_soft_refusal_moves_on_instead_of_stopping(self):
        # caution-only refusal at the scrutinised station: with --caution-soft the search continues (no extra views there)
        r, err = self.run_node([CAUT, CLEAR, SIDE_CLEAR, SIDE_CLEAR], extra=SOFT)
        self.assertIsNone(err); self.assertEqual(checks(r), ['W2', 'M1']); self.assertEqual(r['checkpoint_station'], 'M1')
        r, err = self.run_node([CAUT, CLEAR], extra={})
        self.assertIn('DENIED: visible_hazard_at_checkpoint', err); self.assertEqual(checks(r), ['W2'])


def checks(r):
    return rr.checks(r)


class Wiring(unittest.TestCase):
    def test_flags_and_modules(self):
        import scripts.v32_orchestrate as orch
        plan = orch.build_plan('live', '避難所Bに飲料水を届けて', mission_timeout=900, evidence_dir=Path('/tmp/abcdef0123456789'),
                               advice_scrutiny=True, advice_mode='monotone', advice_file='/tmp/a.json')
        self.assertIn('--advice-scrutiny', ' '.join(plan['mission'].argv))
        plan = orch.build_plan('live', 'x', mission_timeout=900, evidence_dir=Path('/tmp/abcdef0123456789'))
        self.assertNotIn('--advice-scrutiny', ' '.join(plan['mission'].argv))
        from scripts import run_campaign as rc
        fl = rc.advice_flags({'mode': 'monotone', 'file': 'experiments/advice_A/x.json', 'scrutiny': True, 'caution_soft': True})
        self.assertIn('--advice-scrutiny', fl); self.assertIn('--caution-soft', fl)
        self.assertEqual(rc.advice_flags({'mode': 'monotone', 'file': 'x.json'}), ['--advice-mode', 'monotone', '--advice-file', str(ROOT / 'x.json')])
        from rescuemind import advice_llm
        plan = advice_llm.plan_for_mission('water', None, mode='monotone', advice_file=None, from_instruction=True, instruction='x',
                                           stations=SS4, scrutiny=True,
                                           extract_fn=lambda text, **kw: {'items': [A('location', 'M1', source='operator')], 'probs': None, 'error': None})
        self.assertEqual(plan['scrutiny'], ['M1'])


if __name__ == '__main__':
    unittest.main()
