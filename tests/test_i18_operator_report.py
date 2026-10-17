"""I-18: the operator report is built only from the robot's own logs and says what to do next."""
import unittest
from rescuemind.operator_report import build


def call(supply, hz):
    return {'result': {'supply': supply, 'scene': 'hazard' if hz >= .05 else 'clear'},
            'scores': {'supply_probs': {supply: .98}, 'hazard_prob': hz}}


def cp(reason, allow, supply='medicine', hz=.002, front_reason=None):
    d = {'allow': allow, 'reason': reason}
    if front_reason:
        d['front_reason'] = front_reason
    return {'model_calls': {'first': call(supply, hz), 'second': call(supply, hz)}, 'decision': d,
            'explanation': {'text_ja': '箱が置かれている'}}


BASE = {'run_id': 'abcdef0123456789', 'instruction': '避難所Bに救急箱を', 'intent': {'item': 'medicine'},
        'events': [{'stage': 'shelter_approach', 't_wall_s': 90.0}]}


class Report(unittest.TestCase):
    def test_hidden_fire_seen_from_the_side(self):
        m = dict(BASE, checkpoint_station='medicine',
                 checkpoint=cp('visible_hazard_at_checkpoint', False, front_reason='on_site_supply_confirmed'),
                 look_around={'peeks': [{'side': 'L', 'hazard': True, 'image': 'peek_L.jpg',
                                         'model_calls': {'first': call('medicine', .82)}}]})
        r = build(m, {'state': 'COMPLETED_EXPECTED_DENIAL'})
        self.assertEqual(r['colour'], 'bad')
        self.assertIn('火・煙を検知', r['headline'])
        self.assertTrue(any('消防' in a for a in r['next']))
        self.assertTrue(any('左0.4 m' in x and '0.82' in x for x in r['reasons']))
        self.assertTrue(r['checks'][0]['allow'])          # the front check itself approved

    def test_found_after_search_asks_to_update_the_inventory(self):
        m = dict(BASE, checkpoint_station='water', checkpoint=cp('on_site_supply_confirmed', True),
                 recovery={'first_station': 'medicine', 'first_checkpoint': cp('local_vlm_disagree_or_wrong_supply', False, supply='water')})
        r = build(m, {'state': 'COMPLETED'})
        self.assertEqual(r['outcome']['kind'], 'delivered_after_search')
        self.assertTrue(any('在庫表を更新' in a and '拠点W' in a for a in r['next']))
        self.assertEqual([c['station'] for c in r['checks']], ['medicine', 'water'])

    def test_memory_changes_are_reported_with_station_names(self):
        m = dict(BASE, checkpoint_station='water', checkpoint=cp('on_site_supply_confirmed', True),
                 memory={'mode': 'verified', 'rationale': ['前回は拠点Wで確認']})
        res = {'state': 'COMPLETED', 'memory_update': {'changes': [{'text_ja': '拠点「water」の物資が前回から変化'}]}}
        r = build(m, res)
        self.assertIn('記憶の提案：前回は拠点Wで確認', r['memory'])
        self.assertTrue(any('拠点W' in x and '「water」' not in x for x in r['memory']))

    def test_unaudited_run_is_marked(self):
        m = dict(BASE, checkpoint_station='water', checkpoint=cp('on_site_supply_confirmed', True))
        self.assertFalse(build(m, {'state': 'FAILED'})['audited'])


if __name__ == '__main__':
    unittest.main()
