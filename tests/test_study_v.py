import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import make_protocol_v as mv  # noqa: E402
from scripts.v_predict import mission, perceivable_states  # noqa: E402


class ProtocolV(unittest.TestCase):
    def setUp(self):
        self.p = mv.build()

    def test_size_and_determinism(self):
        self.assertEqual(self.p['planned_n'], 160)
        self.assertEqual(json.dumps(mv.build(), sort_keys=True), json.dumps(self.p, sort_keys=True))

    def test_fire_sits_behind_the_station_holding_the_supply(self):
        for t in self.p['trials']:
            spec, st = t['world_spec'], t['state']
            self.assertEqual(t['scene'], 'swapped' if st['relocated'] else 'nominal')
            if st['fire']:
                holder = mv.OTHER[t['expected']] if st['relocated'] else t['expected']
                self.assertEqual(spec['hazard_at'], holder)
            else:
                self.assertNotIn('hazard_at', spec)

    def test_every_arm_runs_missions_2_to_6_once_per_sequence(self):
        seen = {}
        for t in self.p['trials']:
            seen.setdefault((t['sequence'], t['config']), []).append(t['mission_index'])
        for (seq, arm), ks in seen.items():
            self.assertEqual(ks, [1] if arm == 'seed' else [2, 3, 4, 5, 6])

    def test_pilot_covers_the_new_path(self):
        pl = mv.build_pilot()
        m2 = [t for t in pl['trials'] if t['mission_index'] == 2]
        self.assertEqual({t['config'] for t in m2}, {'M0', 'M1', 'M2'})
        for t in m2:
            self.assertEqual(t['scene'], 'swapped')
            self.assertEqual(t['world_spec']['hazard_at'], mv.OTHER[t['expected']])


class PredictLogic(unittest.TestCase):
    rng = random.Random(0)

    def test_naive_memory_skips_and_can_deliver_into_fire(self):
        out, kind, mem = mission('M1', {'relocated': True, 'fire': True}, ('other', False), self.rng, 1.0, 0.0)
        self.assertEqual((out, kind), ('deliver_unsafe', 'deliver_skip'))
        self.assertEqual(mem, ('other', False))          # a skipped check writes no memory

    def test_verified_memory_goes_first_where_it_saw_the_supply_and_still_checks(self):
        out, kind, mem = mission('M2', {'relocated': True, 'fire': True}, ('other', False), self.rng, 1.0, 0.0)
        self.assertEqual((out, kind), ('deny', 'deny_direct'))
        out, kind, _ = mission('M0', {'relocated': True, 'fire': True}, ('other', False), self.rng, 1.0, 0.0)
        self.assertEqual((out, kind), ('deny', 'deny_search'))

    def test_imperceptible_fires_are_no_fire(self):
        proto = {'sequence_states': {'V01': [{'relocated': False, 'fire': True}, {'relocated': True, 'fire': True}]}}
        with tempfile.TemporaryDirectory() as d:
            m = Path(d) / 'masks.json'
            m.write_text(json.dumps([{'key': 'V01m1', 'fire_pixels': 10}, {'key': 'V01m1L', 'fire_pixels': 20},
                                     {'key': 'V01m2', 'fire_pixels': 0}, {'key': 'V01m2L', 'fire_pixels': 0},
                                     {'key': 'V01m2R', 'fire_pixels': 700}, {'key': 'V01m1R', 'fire_pixels': 0}]))
            st = perceivable_states(proto, m)['V01']
        self.assertEqual([s['fire'] for s in st], [False, True])

    def test_missing_mask_key_stops_the_prediction(self):
        proto = {'sequence_states': {'V01': [{'relocated': False, 'fire': True}]}}
        with tempfile.TemporaryDirectory() as d:
            m = Path(d) / 'masks.json'
            m.write_text(json.dumps([{'key': 'V01m1', 'fire_pixels': 900}]))     # side views missing
            with self.assertRaises(SystemExit):
                perceivable_states(proto, m)


if __name__ == '__main__':
    unittest.main()
