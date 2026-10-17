"""I-15 cross-mission memory: memory proposes (route, caution), perception disposes (every check still runs)."""
import json
import random
import tempfile
import unittest
from pathlib import Path

from rescuemind.mission_memory import (MissionMemory, apply_memory_caution, observations, peek_hazard,
                                       CAUTION_TAU_H)
import scripts.v32_orchestrate as orch


def call(supply, hz=0.001, scene='clear', pass_id=1):
    return {'backend': 'local_transformers', 'model': 'Qwen/Qwen3.5-9B', 'real_inference': True, 'image_sha256': 'x',
            'pass_id': pass_id, 'result': {'supply': supply, 'scene': scene},
            'scores': {'supply_probs': {supply: .97}, 'hazard_prob': hz}}


def checkpoint(seen, expected, hz=0.001, scene='clear', peeks=None):
    ok = seen == expected and scene != 'hazard'
    cp = {'model_calls': {'first': call(seen, hz, scene), 'second': call(seen, hz, scene, 2)},
          'decision': {'allow': ok, 'reason': 'on_site_supply_confirmed' if ok else
                       ('visible_hazard_at_checkpoint' if scene == 'hazard' else 'local_vlm_disagree_or_wrong_supply'),
                       'first_supply': seen, 'second_supply': seen, 'first_confidence': .97, 'second_confidence': .97,
                       'min_confidence': .5}}
    return cp


def mission(station, seen, expected, peeks=(), recovery=None, **kw):
    m = {'checkpoint_station': station, 'checkpoint': checkpoint(seen, expected, **kw)}
    if peeks:
        m['look_around'] = {'peeks': [{'side': s, 'hazard': h, 'model_calls': {'first': call(seen, .9 if h else .001),
                                                                                'second': call(seen, .9 if h else .001, pass_id=2)}}
                                      for s, h in peeks]}
    if recovery:
        m['recovery'] = {'first_station': recovery[0], 'first_checkpoint': checkpoint(recovery[1], expected)}
    return m


class Monotone(unittest.TestCase):
    def test_caution_never_turns_a_refusal_into_an_approval(self):
        rng = random.Random(0)
        for _ in range(2000):
            allow = rng.random() < .5
            d = {'allow': allow, 'reason': 'on_site_supply_confirmed' if allow else 'local_vlm_disagree_or_wrong_supply'}
            hz = rng.random() * .1
            out = apply_memory_caution(d, call('water', hz), call('water', hz, pass_id=2), rng.choice([None, .01, .03]))
            self.assertTrue(out['allow'] <= d['allow'])     # approvals with memory are a subset of approvals without
            if not d['allow']:
                self.assertEqual(out, d)

    def test_caution_refuses_in_the_gap_between_thresholds(self):
        d = {'allow': True, 'reason': 'on_site_supply_confirmed'}
        out = apply_memory_caution(d, call('water', .035), call('water', .002, pass_id=2), CAUTION_TAU_H)
        self.assertEqual((out['allow'], out['reason'], out['memory_caution_tau_h']), (False, 'visible_hazard_at_checkpoint', .01))
        self.assertEqual(apply_memory_caution(d, call('water', .035), call('water', .002, pass_id=2), None), d)

    def test_side_view_hazard_is_a_superset(self):
        self.assertTrue(peek_hazard('visible_hazard_at_checkpoint', call('water'), call('water'), None))
        self.assertTrue(peek_hazard('local_vlm_disagree_or_wrong_supply', call('other', .02), call('other'), .01))
        self.assertFalse(peek_hazard('local_vlm_disagree_or_wrong_supply', call('other', .02), call('other'), None))


class Memory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'mem.jsonl'

    def tearDown(self):
        self.tmp.cleanup()

    def test_observations_cover_recovery_front_and_side_views_without_ground_truth(self):
        m = mission('medicine', 'water', 'water', peeks=[('L', False), ('R', True)], recovery=('water', 'medicine'))
        obs = observations(m, 'r1')
        self.assertEqual([(o['station'], o['supply'], o['hazard']) for o in obs],
                         [('water', 'medicine', False), ('medicine', 'water', True)])
        self.assertEqual(obs[1]['hazard_views'], ['R'])
        self.assertNotIn('truth', json.dumps(obs))

    def test_relocated_supply_is_visited_first_but_still_checked(self):
        mem = MissionMemory(self.path)
        mem.append_mission(mission('medicine', 'water', 'water', recovery=('water', 'medicine')), 'r1')
        for mode in ('verified', 'naive'):
            p = MissionMemory(self.path).plan('water', mode)
            self.assertEqual(p['first_station'], 'medicine')
        self.assertFalse(MissionMemory(self.path).plan('water', 'verified')['skip_check'])
        self.assertTrue(MissionMemory(self.path).plan('water', 'naive')['skip_check'])
        self.assertEqual(MissionMemory(self.path).plan('water', 'off')['first_station'], 'water')

    def test_remembered_hazard_raises_caution_and_orders_the_revealing_side_first(self):
        mem = MissionMemory(self.path)
        mem.append_mission(mission('water', 'water', 'water', peeks=[('L', False), ('R', True)]), 'r1')
        p = MissionMemory(self.path).plan('water', 'verified')
        self.assertEqual(p['caution']['water'], {'tau_h': CAUTION_TAU_H, 'first_side': 'R', 'seen_in': 'r1'})
        self.assertFalse(p['deny_without_visit'])
        self.assertTrue(MissionMemory(self.path).plan('water', 'naive')['deny_without_visit'])

    def test_hazard_memory_expires_after_the_horizon(self):
        mem = MissionMemory(self.path)
        mem.append_mission(mission('water', 'water', 'water', scene='hazard', hz=.9), 'r1')
        for k in range(2, 5):
            mem.append_mission(mission('water', 'water', 'water'), f'r{k}')
        self.assertEqual(MissionMemory(self.path).plan('water', 'verified')['caution'], {})

    def test_change_report(self):
        mem = MissionMemory(self.path)
        mem.append_mission(mission('water', 'water', 'water', scene='hazard', hz=.9), 'r1')
        up = mem.append_mission(mission('water', 'medicine', 'water', recovery=None), 'r2')
        kinds = {c['kind'] for c in up['changes']}
        self.assertEqual(kinds, {'supply_changed', 'hazard_not_seen_now'})

    def test_naive_trusted_checkpoint_is_not_remembered_as_an_observation(self):
        m = {'checkpoint_station': 'water', 'checkpoint': {'memory_trusted': True, 'decision': {'allow': True}}}
        self.assertEqual(observations(m, 'r1'), [])


class Audit(unittest.TestCase):
    def test_audit_recomputes_the_memory_caution(self):
        from rescuemind.local_run_audit import audit_local_checkpoint, LocalReceiptError
        from rescuemind.local_vision import local_decision
        a, b = call('water', .03), call('water', .03, pass_id=2)
        base = local_decision('water', a, b)
        cp = {'backend': 'LOCAL_ONLY_NO_CLOUD_API', 'mode': 'single', 'image_sha256': 'x',
              'model_calls': {'first': a, 'second': b}, 'memory_caution_tau_h': .01,
              'decision': apply_memory_caution(base, a, b, .01)}
        self.assertFalse(audit_local_checkpoint(cp, 'x', expected='water')['allow'])
        cp['decision'] = base     # claiming the looser decision under caution must fail the audit
        with self.assertRaises(LocalReceiptError):
            audit_local_checkpoint(cp, 'x', expected='water')
        cp['memory_caution_tau_h'] = .2   # memory may never loosen the threshold
        with self.assertRaises(LocalReceiptError):
            audit_local_checkpoint(cp, 'x', expected='water')


class Plumbing(unittest.TestCase):
    def test_flags_reach_the_mission(self):
        plan = orch.build_plan('live', '避難所Bに飲料水を届けて', mission_timeout=900, evidence_dir=Path('/tmp/abcdef0123456789'),
                               memory_file='/tmp/m.jsonl', memory_mode='verified')
        self.assertIn('--memory-file /tmp/m.jsonl --memory-mode verified', ' '.join(plan['mission'].argv))


if __name__ == '__main__':
    unittest.main()
