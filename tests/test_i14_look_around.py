"""I-14: look-around side views can only turn an approval into a hazard refusal; audits recompute it."""
import unittest
from pathlib import Path

from rescuemind.local_vision import combine_with_look_around
import scripts.v32_orchestrate as orch

FRONT_OK = {'allow': True, 'reason': 'on_site_supply_confirmed', 'expected': 'water'}


class Combine(unittest.TestCase):
    def test_clear_side_views_keep_the_approval_unchanged(self):
        self.assertEqual(combine_with_look_around(FRONT_OK, [{'side': 'L', 'hazard': False}, {'side': 'R', 'hazard': False}]),
                         FRONT_OK)

    def test_any_side_hazard_refuses_without_search(self):
        d = combine_with_look_around(FRONT_OK, [{'side': 'L', 'hazard': False}, {'side': 'R', 'hazard': True}])
        self.assertEqual((d['allow'], d['reason'], d['look_around_hazard_sides']), (False, 'visible_hazard_at_checkpoint', ['R']))
        self.assertEqual(d['front_reason'], 'on_site_supply_confirmed')

    def test_never_turns_a_refusal_into_an_approval(self):
        deny = {'allow': False, 'reason': 'local_vlm_disagree_or_wrong_supply'}
        self.assertEqual(combine_with_look_around(deny, [{'side': 'L', 'hazard': False}]), deny)


class Plan(unittest.TestCase):
    def test_flag_reaches_the_mission(self):
        plan = orch.build_plan('live', '避難所Bに飲料水を届けて', mission_timeout=900,
                               evidence_dir=Path('/tmp/abcdef0123456789'), look_around=0.4)
        self.assertIn('--look-around 0.4', ' '.join(plan['mission'].argv))
        plan = orch.build_plan('live', '避難所Bに飲料水を届けて', mission_timeout=900, evidence_dir=Path('/tmp/abcdef0123456789'))
        self.assertNotIn('--look-around', ' '.join(plan['mission'].argv))


class OneSided(unittest.TestCase):
    def test_sides_flag_reaches_the_mission_only_when_not_both(self):
        plan = orch.build_plan('live', '避難所Bに飲料水を届けて', mission_timeout=900, evidence_dir=Path('/tmp/abcdef0123456789'), look_around=0.8, look_around_sides='L')
        self.assertIn('--look-around 0.8 --look-around-sides L', ' '.join(plan['mission'].argv))
        plan = orch.build_plan('live', '避難所Bに飲料水を届けて', mission_timeout=900, evidence_dir=Path('/tmp/abcdef0123456789'), look_around=0.8)
        self.assertNotIn('--look-around-sides', ' '.join(plan['mission'].argv))

    def test_record_carries_the_sides(self):
        import json
        from rescuemind import delivery_permit as dp
        raw = dp.build_record({'run_id': 'r', 'checkpoint_station': 'water'}, image_dir='/tmp', front_name='f.jpg', look_around=0.8, look_around_sides='L')
        self.assertEqual(json.loads(raw)['config']['look_around_sides'], 'L')


class DenialAudit(unittest.TestCase):
    def test_extra_points_extend_the_allowed_dwell_area(self):
        import inspect
        from rescuemind.negative_evidence import audit_denial
        self.assertIn('extra_points', inspect.signature(audit_denial).parameters)


if __name__ == '__main__':
    unittest.main()
