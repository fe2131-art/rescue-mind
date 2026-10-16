"""I-13: the original two-AI rule (Qwen + Jev role answered by local Clef-Flash)."""
import unittest
from pathlib import Path

from rescuemind.local_vision import combine_with_jev, LocalInferenceError
from rescuemind import clef_local
import scripts.v32_orchestrate as orch


def j(supply='water', conf=.9, presence=.9, hazard=.01, scene='unknown'):
    return {'real_model': True, 'model': 'Cloudflare/clef-flash', 'supply': supply, 'supply_confidence': conf,
            'supply_present_probability': presence, 'hazard_probability': hazard, 'scene': scene}


OK = {'allow': True, 'reason': 'on_site_supply_confirmed'}


class Combine(unittest.TestCase):
    def test_both_agree(self):
        self.assertTrue(combine_with_jev(OK, j(), 'water')['allow'])

    def test_jev_hazard_overrides_qwen_approval_and_blocks_search(self):
        d = combine_with_jev(OK, j(hazard=.6), 'water')
        self.assertEqual((d['allow'], d['reason']), (False, 'visible_hazard_at_checkpoint'))
        d = combine_with_jev(OK, j(scene='hazard'), 'water')
        self.assertEqual(d['reason'], 'visible_hazard_at_checkpoint')

    def test_jev_wrong_supply_allows_recovery_search(self):
        d = combine_with_jev(OK, j(supply='other', presence=.01), 'water')
        self.assertEqual(d['reason'], 'local_vlm_disagree_or_wrong_supply')

    def test_jev_low_confidence_stops(self):
        d = combine_with_jev(OK, j(conf=.5), 'water')
        self.assertEqual(d['reason'], 'low_confidence_supply_match')

    def test_qwen_hazard_wins_over_jev_wrong_supply(self):
        d = combine_with_jev({'allow': False, 'reason': 'visible_hazard_at_checkpoint'}, j(supply='other'), 'water')
        self.assertEqual(d['reason'], 'visible_hazard_at_checkpoint')

    def test_unverified_jev_result_refused(self):
        bad = j(); bad['model'] = 'other'
        with self.assertRaises(LocalInferenceError):
            combine_with_jev(OK, bad, 'water')

    def test_threshold_is_configurable(self):
        self.assertTrue(combine_with_jev(OK, j(hazard=.2), 'water', hazard_threshold=.35)['allow'])
        self.assertFalse(combine_with_jev(OK, j(hazard=.2), 'water', hazard_threshold=.05)['allow'])


class ClefParse(unittest.TestCase):
    def payload(self, **kw):
        a = {'supply': {'type': 'choice', 'choice': 'water', 'confidence': .9, 'probabilities': {}},
             'scene': {'type': 'choice', 'choice': 'clear', 'confidence': .8},
             'hazard': {'type': 'noul', 'noul': .02}, 'visible_supply': {'type': 'noul', 'noul': .95}}
        a.update(kw)
        return {'model': 'Cloudflare/clef-flash', 'real_inference': True, 'answers': a}

    def test_parse_and_request_schema(self):
        r = clef_local.parse(self.payload())
        self.assertEqual(r['supply'], 'water')
        req = clef_local.build_request(b'\xff\xd8' + b'0' * 400)
        self.assertEqual(set(req['questions']), {'supply', 'visible_supply', 'hazard', 'scene'})
        self.assertEqual(req['model'], 'Cloudflare/clef-flash')

    def test_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            clef_local.parse(self.payload(hazard={'type': 'noul', 'noul': 1.5}))

    def test_loopback_only(self):
        with self.assertRaises(ValueError):
            clef_local.infer('x.jpg', 'http://10.0.0.1:8767/v1/systemone')


class Plan(unittest.TestCase):
    def test_plan_adds_clef_service_and_mission_flags(self):
        plan = orch.build_plan('live', '避難所Bに飲料水を届けて', mission_timeout=900,
                               evidence_dir=Path('/tmp/abcdef0123456789'), jev_local='clef', jev_hazard_threshold=.05)
        self.assertIn('jev_role_clef', [s.name for s in plan['services']])
        m = ' '.join(plan['mission'].argv)
        self.assertIn('--jev-url http://127.0.0.1:8767/v1/systemone', m)
        self.assertIn('--jev-hazard-threshold 0.05', m)


if __name__ == '__main__':
    unittest.main()
