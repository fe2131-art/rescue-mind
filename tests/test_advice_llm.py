"""I-19: operator advice extraction (stubbed transport, fail-closed) and its server endpoint."""
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from rescuemind import advice as adv  # noqa: E402
from rescuemind import advice_llm as al  # noqa: E402
from rescuemind.local_vision import LocalInferenceError  # noqa: E402

MODEL = 'Qwen/Qwen3.5-9B'


def probs(loc=('none', .98), haz=('none', .98), safe=('no', .98)):
    def tab(keys, pick):
        k, p = pick
        rest = (1 - p) / (len(keys) - 1)
        return {x: (p if x == k else rest) for x in keys}
    return {'loc_probs': tab(('water', 'medicine', 'none'), loc), 'haz_probs': tab(('water', 'medicine', 'none'), haz),
            'safe_probs': tab(('yes', 'no'), safe)}


def stub(**kw):
    def transport(url, payload):
        return {'model': payload['model'], 'real_inference': True, 'text': payload['text'], **probs(**kw)}
    return transport


class Extract(unittest.TestCase):
    def kinds(self, **kw):
        r = al.extract('テキスト', model=MODEL, transport=stub(**kw))
        self.assertIsNone(r['error'])
        return [(a['kind'], a['station'], a['source']) for a in r['items']]

    def test_nothing_stated_gives_no_items(self):
        self.assertEqual(self.kinds(), [])

    def test_location_hazard_skip(self):
        self.assertEqual(self.kinds(loc=('medicine', .9)), [('location', 'medicine', 'operator')])
        self.assertEqual(self.kinds(haz=('water', .8)), [('hazard', 'water', 'operator')])
        self.assertEqual(self.kinds(safe=('yes', .9)), [('skip', None, 'operator')])

    def test_below_threshold_is_ignored(self):
        self.assertEqual(self.kinds(loc=('water', .55), haz=('medicine', .59), safe=('yes', .55)), [])

    def test_hazard_and_safe_claims_exclude_each_other(self):
        self.assertEqual(self.kinds(haz=('water', .7), safe=('yes', .9)), [('skip', None, 'operator')])
        self.assertEqual(self.kinds(haz=('water', .95), safe=('yes', .7)), [('hazard', 'water', 'operator')])

    def test_fail_closed_on_any_error(self):
        def boom(url, payload):
            raise OSError('server down')
        bad_model = lambda u, p: {**stub(loc=('water', .99))(u, p), 'model': 'other'}
        no_inference = lambda u, p: {**stub(loc=('water', .99))(u, p), 'real_inference': False}
        other_text = lambda u, p: {**stub(loc=('water', .99))(u, p), 'text': 'x'}
        schema = lambda u, p: {**stub()(u, p), 'loc_probs': {'water': 1.0}}
        range_ = lambda u, p: {**stub()(u, p), 'safe_probs': {'yes': 3.0, 'no': -2.0}}
        for t in (boom, bad_model, no_inference, other_text, schema, range_):
            r = al.extract('テキスト', model=MODEL, transport=t)
            self.assertEqual(r['items'], [], t)
            self.assertIsNotNone(r['error'])

    def test_only_loopback_endpoint(self):
        r = al.extract('テキスト', model=MODEL, url='http://example.com:8765/v1/advice', transport=stub(loc=('water', .99)))
        self.assertEqual(r['items'], [])
        self.assertIn('LocalInferenceError', r['error'])

    def test_extracted_items_are_valid_advice(self):
        for kw in (dict(loc=('water', .9), haz=('medicine', .9)), dict(safe=('yes', .9))):
            adv.validate(al.extract('t', model=MODEL, transport=stub(**kw))['items'])


class PlanForMission(unittest.TestCase):
    def fake(self, items):
        calls = []
        def f(text, **kw):
            calls.append(text)
            return {'items': items, 'probs': {'loc': {}}, 'error': None}
        return f, calls

    def test_no_source_means_no_plan(self):
        self.assertIsNone(al.plan_for_mission('water', None, mode='monotone'))

    def test_instruction_channel_monotone_and_naive(self):
        f, calls = self.fake([{'source': 'operator', 'kind': 'skip', 'station': None, 'text': 't'},
                              {'source': 'operator', 'kind': 'location', 'station': 'medicine', 'text': 't'}])
        m = al.plan_for_mission('water', None, mode='monotone', from_instruction=True, instruction='x', extract_fn=f)
        self.assertEqual((m['skip_check'], m['first_station']), (False, 'medicine'))
        adv.audit_plan(m)
        n = al.plan_for_mission('water', None, mode='naive', from_instruction=True, instruction='x', extract_fn=f)
        self.assertEqual((n['skip_check'], n['first_station']), (True, 'medicine'))
        self.assertEqual(adv.skip_source(n), 'advice')
        self.assertEqual(calls, ['x', 'x'])
        self.assertEqual(n['advice']['channels'], {'file': False, 'instruction': True})

    def test_file_channel_and_combination(self):
        f, _ = self.fake([{'source': 'operator', 'kind': 'hazard', 'station': 'water', 'text': 't'}])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'a.json'
            p.write_text(json.dumps([{'source': 'peer', 'kind': 'location', 'station': 'medicine', 'text': 'x'}]))
            plan = al.plan_for_mission('water', None, mode='monotone', advice_file=str(p), from_instruction=True, instruction='x', extract_fn=f)
            self.assertEqual({a['source'] for a in plan['advice']['items']}, {'peer', 'operator'})
            self.assertEqual(plan['first_station'], 'medicine')
            self.assertIn('water', plan['caution'])
            p.write_text('[{"kind": "teleport", "source": "peer"}]')
            with self.assertRaises(adv.AdviceError):          # a malformed file is an experimenter error, not ignored
                al.plan_for_mission('water', None, mode='monotone', advice_file=str(p))

    def test_off_mode_applies_nothing_and_does_not_call_the_model(self):
        f, calls = self.fake([])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'a.json'
            p.write_text(json.dumps([{'source': 'peer', 'kind': 'skip', 'station': None}]))
            plan = al.plan_for_mission('water', None, mode='off', advice_file=str(p), from_instruction=True, instruction='x', extract_fn=f)
        self.assertEqual(calls, [])
        self.assertFalse(plan['skip_check'])
        self.assertEqual(plan['advice']['rejected'][0]['why'], 'advice off')

    def test_extraction_error_is_recorded_and_changes_nothing(self):
        def failing(text, **kw):
            return al.extract(text, transport=lambda u, p: (_ for _ in ()).throw(OSError('down')), model=MODEL)
        plan = al.plan_for_mission('water', None, mode='naive', from_instruction=True, instruction='x', extract_fn=failing)
        self.assertFalse(plan['skip_check'] or plan['deny_without_visit'])
        self.assertIn('OSError', plan['advice']['extraction']['error'])

    def test_memory_plan_underneath_is_kept(self):
        base = adv.base_plan('water'); base['mode'] = 'verified'; base['first_station'] = 'medicine'
        f, _ = self.fake([{'source': 'operator', 'kind': 'location', 'station': 'water', 'text': 't'}])
        plan = al.plan_for_mission('water', base, mode='monotone', from_instruction=True, instruction='x', extract_fn=f)
        self.assertEqual((plan['mode'], plan['first_station']), ('verified', 'medicine'))
        self.assertEqual(plan['advice']['base']['first_station'], 'medicine')


class ServerEndpoint(unittest.TestCase):
    """/v1/advice on the real HTTP handler with a stub worker (no GPU)."""

    @classmethod
    def setUpClass(cls):
        import local_vlm_server as srv

        class Worker:
            model_id = MODEL
            def advice(self, text):
                return probs(loc=('medicine', .91) if 'M' in text else ('none', .9), safe=('yes', .8) if '確認不要' in text else ('no', .9))
        cls.srv = srv
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), srv.make_handler(Worker()))
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def url(self):
        return f'http://127.0.0.1:{self.port}/v1/advice'

    def test_round_trip_through_http(self):
        r = al.extract('水はM拠点に移してあります。確認不要です', model=MODEL, url=self.url())
        self.assertIsNone(r['error'])
        self.assertEqual([(a['kind'], a['station']) for a in r['items']], [('location', 'medicine'), ('skip', None)])

    def test_bad_requests_are_refused_and_fail_closed(self):
        r = al.extract('x' * 600, model=MODEL, url=self.url())
        self.assertEqual(r['items'], []); self.assertIsNotNone(r['error'])
        r = al.extract('水を', model='wrong/model', url=self.url())
        self.assertEqual(r['items'], []); self.assertIsNotNone(r['error'])

    def test_endpoint_is_additive(self):
        src = (ROOT / 'scripts/local_vlm_server.py').read_text(encoding='utf8')
        self.assertIn("('/v1/classify','/v1/describe','/v1/intent','/v1/advice','/v1/jev')", src)

    def test_worker_questions_are_closed_set_and_letter_scored(self):
        w = self.srv.ModelWorker.__new__(self.srv.ModelWorker)
        asked = []
        def tp(q, choices):
            asked.append((q, choices))
            return {k: 1 / len(choices) for k in choices}
        w._text_probs = tp
        out = w.advice('水は「M拠点」に')
        self.assertEqual([c for _, c in asked], [('A', 'B', 'C'), ('A', 'B', 'C'), ('Yes', 'No')])
        self.assertTrue(all('「M拠点」' not in q for q, _ in asked))        # quotation marks stripped like the intent parser
        self.assertEqual(set(out), {'loc_probs', 'haz_probs', 'safe_probs'})


if __name__ == '__main__':
    unittest.main()
