"""I-24 advice credit: admission, settlement, Proposition 3 (price over a horizon) and that credit never touches safety."""
import json
import random
import unittest

from rescuemind import advice, advice_credit as ac
from rescuemind.stations import StationSet

SRC = ('memory', 'peer', 'inventory', 'operator')


def depot():
    return StationSet.build(['S1', 'S2', 'S3', 'S4'], {'S1': 'water', 'S2': 'medicine', 'S3': 'water', 'S4': 'medicine'})


def loc(src, st):
    return {'source': src, 'kind': 'location', 'station': st, 'text': ''}


def haz(src, st):
    return {'source': src, 'kind': 'hazard', 'station': st, 'text': ''}


def visit(st, supply_match=None, refused=False, refused_base=False, scrutiny_views=0):
    return dict(station=st, supply_match=supply_match, refused=refused, refused_base=refused_base,
                scrutiny_views=scrutiny_views)


class Admission(unittest.TestCase):
    def test_liar_is_throttled_after_its_credit(self):
        led = ac.new_ledger()
        for m in range(4):
            p = ac.plan_with_credit(led, 'water', [loc('peer', 'medicine')], 'monotone')
            applied = [a['effect'] for a in p['advice']['applied']]
            if m < 2:
                self.assertEqual(applied, ['reorder'])
                ac.settle(led, p, [visit('medicine', supply_match=False), visit('water', supply_match=True)])
            else:
                self.assertEqual(applied, [])
                self.assertEqual(len(p['advice']['throttled']), 1)
                self.assertEqual(p['first_station'], 'water')          # back to the inventory order
                ac.settle(led, p, [visit('water', supply_match=True)])
        self.assertEqual(led['sources']['file']['debit_loc'], 2.0)

    def test_truthful_location_source_is_never_throttled(self):
        led = ac.new_ledger()
        for _ in range(30):
            p = ac.plan_with_credit(led, 'water', [loc('operator', 'medicine')], 'monotone', channels=['operator'])
            self.assertEqual([a['effect'] for a in p['advice']['applied']], ['reorder'])
            ac.settle(led, p, [visit('medicine', supply_match=True)])
        self.assertEqual(led['sources']['operator']['loc'], ac.C_LOC)
        self.assertEqual(led['sources']['operator']['debit_loc'], 0.0)

    def test_two_items_of_one_channel_in_one_mission_share_the_credit(self):
        led = ac.new_ledger(c_haz=1.0)
        kept, thr = ac.admit(led, [haz('peer', 'water'), haz('peer', 'medicine')], ['file', 'file'])
        self.assertEqual((len(kept), len(thr)), (1, 1))

    def test_channels_have_separate_accounts(self):
        led = ac.new_ledger(c_haz=1.0)
        kept, thr = ac.admit(led, [haz('peer', 'water'), haz('operator', 'water')], ['file', 'operator'])
        self.assertEqual((len(kept), len(thr)), (2, 0))

    def test_ce2_labels_do_not_make_accounts(self):
        """R7 CE-2: one file spreading false claims over the four source labels gets ONE account."""
        led = ac.new_ledger()
        items = [loc(s, 'medicine') for s in SRC]
        wasted = 0
        for _ in range(40):
            p = ac.plan_with_credit(led, 'water', items, 'monotone')
            wasted += p['first_station'] == 'medicine'
            vs = [visit('medicine', supply_match=False), visit('water', supply_match=True)] if p['first_station'] == 'medicine' \
                else [visit('water', supply_match=True)]
            ac.settle(led, p, vs)
        self.assertEqual(set(led['sources']), {'file'})
        self.assertLessEqual(wasted, ac.C_LOC + ac.RHO_SHADOW * 40)

    def test_ce1_true_claims_do_not_refund_lies(self):
        """R7 CE-1: with duplicated supply, alternating a lie and a true-but-useless claim; no refund, only RHO_SHADOW."""
        ss = depot()
        led = ac.new_ledger()
        wasted = 0
        for m in range(40):
            st = 'S2' if m % 2 == 0 else 'S3'          # S2 holds medicine (a lie), S3 holds water (true, a duplicate)
            p = ac.plan_with_credit(led, 'water', [loc('peer', st)], 'monotone', stations=ss)
            first = p['first_station']
            if first == 'S2':
                wasted += 1
                vs = [visit('S2', supply_match=False), visit('S1', supply_match=True)]
            else:
                vs = [visit(first, supply_match=True)]
            ac.settle(led, p, vs)
        self.assertLessEqual(wasted, ac.C_LOC + ac.RHO_SHADOW * 40)
        self.assertLessEqual(wasted, 12)

    def test_safe_and_skip_are_inert_and_counted(self):
        led = ac.new_ledger(c_loc=0, c_haz=0)
        items = [{'source': 'operator', 'kind': 'skip', 'station': None, 'text': '確認不要'}]
        p = ac.plan_with_credit(led, 'water', items, 'monotone', channels=['operator'])
        self.assertFalse(p['skip_check'])
        ac.settle(led, p, [visit('water', supply_match=True)])
        self.assertEqual(led['sources']['operator']['relax_attempts'], 1)

    def test_caution_only_refusal_is_charged_base_refusal_is_not(self):
        led = ac.new_ledger()
        p = ac.plan_with_credit(led, 'water', [haz('memory', 'water')], 'monotone')
        ac.settle(led, p, [visit('water', refused=True, refused_base=True)])
        self.assertEqual(led['sources']['file']['debit_haz'], 0.0)
        p = ac.plan_with_credit(led, 'water', [haz('memory', 'water')], 'monotone')
        ac.settle(led, p, [visit('water', refused=True, refused_base=False)])
        self.assertEqual(led['sources']['file']['debit_haz'], 1.0)
        p = ac.plan_with_credit(led, 'water', [haz('memory', 'water')], 'monotone')
        self.assertEqual(p['caution'], {})                        # throttled: no caution until credit regenerates

    def test_undecided_check_at_the_advised_station_is_charged(self):
        led = ac.new_ledger()
        p = ac.plan_with_credit(led, 'water', [loc('peer', 'medicine')], 'monotone')
        ac.settle(led, p, [visit('medicine', supply_match=None), visit('water', supply_match=True)])
        self.assertEqual(led['sources']['file']['debit_loc'], 1.0)

    def test_scrutiny_caused_refusal_is_charged(self):
        led = ac.new_ledger(c_loc=3.0)
        p = ac.plan_with_credit(led, 'water', [loc('peer', 'medicine')], 'monotone', scrutiny=True)
        ac.settle(led, p, [visit('medicine', supply_match=True, refused=True, refused_base=False, scrutiny_views=3)])
        self.assertEqual(led['sources']['file']['debit_loc'], 1.0)

    def test_unvisited_station_costs_nothing(self):
        led = ac.new_ledger()
        p = ac.plan_with_credit(led, 'water', [loc('peer', 'medicine')], 'monotone')
        ac.settle(led, p, [])
        self.assertEqual(led['sources']['file']['loc'], ac.C_LOC)

    def test_baselines_are_not_credited(self):
        led = ac.new_ledger(c_loc=0, c_haz=0)
        p = ac.plan_with_credit(led, 'water', [haz('peer', 'water')], 'naive')
        self.assertTrue(p['deny_without_visit'])

    def test_corrupt_ledger_fails_closed(self):
        for bad in ({}, {'version': 'x', 'sources': {}}, None):
            with self.assertRaises(ac.CreditError):
                ac.admit(bad, [], [])
        led = ac.new_ledger()
        led['sources']['file'] = {'loc': float('nan'), 'haz': 1.0}
        with self.assertRaises(ac.CreditError):
            ac.admit(led, [], [])
        with self.assertRaises(ac.CreditError):
            ac.new_ledger(c_loc=float('inf'))

    def test_save_load_roundtrip(self):
        import tempfile, os
        led = ac.new_ledger()
        p = ac.plan_with_credit(led, 'water', [loc('peer', 'medicine')], 'monotone')
        ac.settle(led, p, [visit('medicine', supply_match=False)])
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, 'credit.json')
            ac.save(led, f)
            self.assertEqual(ac.load(f), json.loads(json.dumps(led)))
            self.assertEqual(ac.load(os.path.join(d, 'missing.json'))['sources'], {})


def random_items(rng, ids):
    out = []
    for _ in range(rng.randint(0, 4)):
        kind = rng.choice(('location', 'hazard', 'safe', 'skip'))
        st = rng.choice(ids) if kind in ('location', 'hazard') else rng.choice((None,) + tuple(ids))
        out.append({'source': rng.choice(SRC), 'kind': kind, 'station': st, 'text': ''})
    return out


def random_visits(rng, plan, ids):
    order = plan.get('order') or [plan['first_station']] + [s for s in ids if s != plan['first_station']]
    out = []
    for st in order[:rng.randint(0, len(order))]:
        refused = rng.random() < 0.3
        out.append(visit(st, supply_match=rng.choice((True, False, None)), refused=refused,
                         refused_base=refused and rng.random() < 0.5, scrutiny_views=rng.randint(0, 3)))
    return out


class Proposition3(unittest.TestCase):
    """Random adaptive sequences (the adversary sees the ledger): the price bounds hold for every source, every mission
    prefix, and the admitted plan is always monotone (safety untouched)."""

    def run_horizon(self, seed, ss, ids, scrutiny):
        rng = random.Random(seed)
        led = ac.new_ledger()
        caution_refusals = {}
        for m in range(1, 61):
            item = rng.choice(('water', 'medicine'))
            its = random_items(rng, ids)
            p = ac.plan_with_credit(led, item, its, 'monotone', stations=ss, scrutiny=scrutiny,
                                    channels=[rng.choice(ac.CHANNELS) for _ in its])
            advice.assert_monotone(advice.base_plan(item, ss), p, ss)          # credit only drops items
            self.assertEqual(ac.audit_credit(p)['checked'], True)
            vs = random_visits(rng, p, ids)
            s = ac.settle(led, p, vs)
            for c in s['charges']:
                if c['pool'] == 'haz' and c['charge'] > 0:
                    caution_refusals[c['account']] = caution_refusals.get(c['account'], 0) + 1
            for key, acc in led['sources'].items():
                self.assertGreaterEqual(acc['loc'], 0.0)
                self.assertGreaterEqual(acc['haz'], 0.0)
                # (a) wasted visits (debits, incl. scrutiny) <= C_LOC + refunds earned by confirmed reorders
                # (a) location price <= C_LOC + RHO_SHADOW * m (no refunds; recovery at most RHO_SHADOW per mission)
                self.assertLessEqual(acc['debit_loc'], ac.C_LOC + acc['recovered_loc'] + 1e-9)
                self.assertLessEqual(acc['recovered_loc'], ac.RHO_SHADOW * m + 1e-9)
                # (b) caution-only refusals <= C_HAZ + RHO * missions
                self.assertLessEqual(caution_refusals.get(key, 0), ac.C_HAZ + ac.RHO * m + 1e-9)

    def test_legacy_arena(self):
        for seed in range(40):
            self.run_horizon(seed, None, ('water', 'medicine'), scrutiny=False)

    def test_depot_with_scrutiny(self):
        ss = depot()
        for seed in range(40):
            self.run_horizon(seed, ss, tuple(ss.ids), scrutiny=True)


if __name__ == '__main__':
    unittest.main()


class FromMission(unittest.TestCase):
    def cp(self, exp, a, b, allow, reason='ok', peeks=()):
        return {'decision': {'expected': exp, 'first_supply': a, 'second_supply': b, 'allow': allow, 'reason': reason},
                'look_around': {'peeks': [{'side': s} for s in peeks]}}

    def test_recovery_run(self):
        m = {'recovery': {'first_station': 'medicine',
                          'first_checkpoint': self.cp('water', 'medicine', 'medicine', False, 'local_vlm_disagree_or_wrong_supply')},
             'checkpoint_station': 'water', 'checkpoint': self.cp('water', 'water', 'water', True, peeks=('L', 'R', 'L2', 'R2', 'N'))}
        v = ac.visits_from_mission(m)
        self.assertEqual([x['station'] for x in v], ['medicine', 'water'])
        self.assertEqual([x['supply_match'] for x in v], [False, True])
        self.assertEqual([x['refused'] for x in v], [False, False])
        self.assertEqual(v[1]['scrutiny_views'], 3)

    def test_ce4_caution_only_from_scores_without_soft_refusal(self):
        """R7 CE-4: caution-only is classified from per-view scores, not from caution_refusals (written only with
        --caution-soft)."""
        def call(p):
            return {'scores': {'hazard_prob': p}}
        def cp(pf, peeks):
            return {'decision': {'expected': 'water', 'first_supply': 'water', 'second_supply': 'water', 'allow': False,
                                 'reason': 'visible_hazard_at_checkpoint'},
                    'model_calls': {'first': call(pf), 'second': call(pf)},
                    'look_around': {'peeks': [{'side': sd, 'model_calls': {'first': call(q), 'second': call(q)}}
                                              for sd, q in peeks]}}
        self.assertEqual(ac.classify_station(cp(0.02, [('L', 0.001), ('R', 0.03)])), (True, False))   # caution only
        self.assertEqual(ac.classify_station(cp(0.02, [('L', 0.2), ('R', 0.0)])), (True, True))       # base hazard
        broken = cp(0.02, [('L', 0.0)])
        broken['look_around']['peeks'][0]['model_calls']['first'] = {'scores': {'hazard_prob': float('nan')}}
        self.assertEqual(ac.classify_station(broken), (True, True))                                   # fail closed
        wrong = {'decision': {'allow': False, 'reason': 'local_vlm_disagree_or_wrong_supply'}}
        self.assertEqual(ac.classify_station(wrong), (False, False))

    def test_real_saved_run_if_present(self):
        import os
        p = os.path.expanduser('~/work/rescue-mind/outputs/runs/b4fcd9d164444db7/mission.json')
        if not os.path.isfile(p):
            self.skipTest('saved run not available')
        v = ac.visits_from_mission(json.load(open(p, encoding='utf8')))
        self.assertEqual([(x['station'], x['supply_match']) for x in v], [('medicine', False), ('water', True)])


class Wiring(unittest.TestCase):
    """plan_for_mission (mission node) reads the ledger; the orchestrator audits and settles it from mission.json."""

    def test_plan_for_mission_and_orchestrator_settlement(self):
        import os, sys, tempfile
        from pathlib import Path
        from rescuemind.advice_llm import plan_for_mission
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
        import v32_orchestrate as orch
        with tempfile.TemporaryDirectory() as d:
            led_p, adv_p = os.path.join(d, 'credit.json'), os.path.join(d, 'advice.json')
            Path(adv_p).write_text(json.dumps([loc('peer', 'medicine')]))
            for mission in range(3):
                plan = plan_for_mission('water', None, mode='monotone', advice_file=adv_p, credit_path=led_p)
                log = Path(d) / f'run{mission}'
                log.mkdir()
                fc = {'decision': {'expected': 'water', 'first_supply': 'medicine', 'second_supply': 'medicine', 'allow': False,
                                   'reason': 'local_vlm_disagree_or_wrong_supply'}}
                ok = {'decision': {'expected': 'water', 'first_supply': 'water', 'second_supply': 'water', 'allow': True}}
                m = {'memory': plan, 'checkpoint_station': 'water', 'checkpoint': ok, 'events': []}
                if plan['first_station'] == 'medicine':
                    m['recovery'] = {'first_station': 'medicine', 'first_checkpoint': fc}
                (log / 'mission.json').write_text(json.dumps(m))
                ev = orch.advice_audit(log)
                self.assertTrue(ev['checked'])
                self.assertEqual(ev['credit']['checked'], True)
                out = orch.settle_credit(log, led_p, f'run{mission}')
                self.assertEqual(plan['first_station'], 'medicine' if mission < 2 else 'water')
            self.assertEqual(out['credit']['file']['loc'], 0.0)
            self.assertEqual(ac.load(led_p)['missions'], 3)


class OperatorReport(unittest.TestCase):
    def test_throttled_advice_is_reported(self):
        from rescuemind.operator_report import advice_lines
        led = ac.new_ledger(c_loc=0.0)
        p = ac.plan_with_credit(led, 'water', [loc('peer', 'medicine')], 'monotone')
        lines = advice_lines({'memory': p})
        self.assertEqual(len(lines), 1)
        self.assertIn('信用を使い切って', lines[0])


class Sybil(unittest.TestCase):
    def test_uncertified_peer_ids_share_the_file_account(self):
        led = ac.new_ledger(c_haz=1.0)
        items = [dict(haz('peer', 'water'), peer_id='p1'), dict(haz('peer', 'medicine'), peer_id='p2')]
        p = ac.plan_with_credit(led, 'water', items, 'monotone')
        self.assertEqual(len(p['advice']['throttled']), 1)

    def test_ce5_certified_peers_reach_their_own_account(self):
        """R7 CE-5: peer_id survives to the account (validate drops it, so accounts are computed from the raw items)."""
        led = ac.new_ledger(c_haz=1.0, certified_peers=('p1', 'p2'))
        items = [dict(haz('peer', 'water'), peer_id='p1'), dict(haz('peer', 'medicine'), peer_id='p2')]
        p = ac.plan_with_credit(led, 'water', items, 'monotone')
        self.assertEqual(p['advice']['throttled'], [])
        self.assertEqual(p['advice']['accounts'], ['peer:p1', 'peer:p2'])


