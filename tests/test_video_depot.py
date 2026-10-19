"""Segment 6 of the final video (I-21 depot): the filming helpers and the storyboard code path, on FAKE run records (no Gazebo, no GPU).

Checks that a depot run (station ids W1/M1/W2/M2, search over k = 4, a side-view fire) is accepted by scripts/make_video_plan.py --depot
(wording by what the run shows, depot overview camera, length estimate), that scripts/make_demo_video.py names the depot's bays and
places the overlay labels (the video renderer itself needs the CJK fonts of the rm-dev image and is not run here), that the frozen
film worlds are the generator's output and are no trial worlds of X / XD / the X pilot, and that the evidence card fits its slot.
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


mvp = load('make_video_plan')
mdv = sys.modules.get('make_demo_video') or load('make_demo_video')
fdw = load('film_depot_worlds')

START = 1_700_000_000_000_000_000
S = 10 ** 9
K4_SPEC = {'depot': {'stations': 4, 'seed': 1, 'supply_at': {'W1': 'medicine', 'M1': 'medicine', 'W2': 'water', 'M2': 'medicine'}},
           'hazard_at': 'W1', 'hazard_geom': [0.6, 0.0, 0.55]}


def ev(stage, t, **kw):
    return {'stage': stage, 't_wall_s': t, **kw}


def write_run(base: Path, run_id: str, kind: str):
    d = base / 'outputs/runs' / run_id
    d.mkdir(parents=True)
    peek_call = {'first': {'scores': {'hazard_prob': 0.9, 'supply_probs': {'water': 0.9}}}}
    m = {'run_id': run_id, 'instruction': '避難所Bに飲料水をお願いします', 'intent': {'item': 'water'}, 'intent_gate': {'backend': 'llm'},
         'mission_start_unix_ns': START, 'route': [['supply_station', 'W1', [1.1, 1.1]], ['shelter_approach', 'B', [2.1, -1.1]]],
         'checkpoint_station': 'W1' if kind == 'side_fire' else 'W2', 'checkpoint_image_path': 'checkpoint.jpg'}
    events = [ev('supply_station', 10), ev('checkpoint_frame', 11)]
    if kind == 'side_fire':
        m['checkpoint'] = {'decision': {'allow': False, 'reason': 'visible_hazard_at_checkpoint', 'front_reason': 'on_site_supply_confirmed',
                                        'look_around_hazard_sides': ['L']}, 'model_calls': {}}
        m['look_around'] = {'peeks': [{'side': 'L', 'hazard': True, 'reason': 'visible_hazard_at_checkpoint', 'model_calls': peek_call}]}
        events += [ev('front_checkpoint_decision', 14), ev('checkpoint_decision', 30), ev('look_around_scheduled', 15),
                   ev('look_around_arrival', 20, target='W1:L'), ev('peek_L_checkpoint_frame', 22),
                   ev('peek_L_checkpoint_decision', 25), ev('checkpoint_denial_dwell_finished', 28)]
        state = 'COMPLETED_EXPECTED_DENIAL'
    else:
        m['checkpoint'] = {'decision': {'allow': True, 'reason': 'on_site_supply_confirmed'}, 'model_calls': {}}
        m['look_around'] = {'peeks': []}
        m['recovery'] = {'first_station': 'W1', 'searched_station': 'W2', 'reason': 'local_vlm_disagree_or_wrong_supply',
                         'first_checkpoint': {'decision': {'allow': False, 'reason': 'local_vlm_disagree_or_wrong_supply'}, 'model_calls': {}}}
        events += [ev('recovery_supply_station', 10), ev('recovery_checkpoint_frame', 11), ev('recovery_checkpoint_decision', 14),
                   ev('recovery_search_started', 16), ev('supply_station', 30), ev('checkpoint_frame', 31),
                   ev('checkpoint_decision', 34), ev('shelter_approach', 45)]
        state = 'COMPLETED'
    m['events'] = events
    (d / 'mission.json').write_text(json.dumps(m), encoding='utf8')
    (d / 'stack_result.json').write_text(json.dumps({'state': state}), encoding='utf8')
    (d / 'stack_plan.json').write_text(json.dumps({'world_variant': {'hazard_at': 'W1' if kind == 'side_fire' else None,
                                                                      'world_spec': K4_SPEC}, 'model': 'Qwen/Qwen3.5-9B'}), encoding='utf8')
    rows = [{'kind': 'ground_truth', 'wall_unix_ns': START + i * S, 'x': 0.05 * i, 'y': 0.0} for i in range(0, 60)]
    (d / 'independent_ros_topics.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf8')
    (d / 'film/film').mkdir(parents=True)
    (d / 'film/robot').mkdir(parents=True)
    return d


class FakeDepotRuns(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        write_run(self.base, 'fire0000000000001', 'side_fire')
        write_run(self.base, 'search00000000001', 'search_deliver')
        self.root0, mvp.ROOT = mvp.ROOT, self.base

    def tearDown(self):
        mvp.ROOT = self.root0
        self.tmp.cleanup()

    def test_classify(self):
        self.assertEqual(fdw.classify(self.base / 'outputs/runs/fire0000000000001')['kind'], 'side_fire')
        c = fdw.classify(self.base / 'outputs/runs/search00000000001')
        self.assertEqual((c['kind'], c['first_station'], c['searched']), ('search_deliver', 'W1', True))

    def test_depot_wording_follows_the_run(self):
        t_fire, n_fire, c_fire = mvp.depot_texts('fire0000000000001')
        t_srch, n_srch, c_srch = mvp.depot_texts('search00000000001')
        self.assertIn('火', t_fire); self.assertNotIn('search', n_fire)
        self.assertIn('search', n_srch); self.assertNotIn('火を見つけました', ''.join(n_srch.values()))
        for caps in (c_fire, c_srch):
            self.assertIn('go', caps)
        self.assertEqual(mvp.depot_camera('fire0000000000001'), 'worlds/film/film_camera_depot.sdf')
        (self.base / 'outputs/runs/fire0000000000001/film_camera.txt').write_text('worlds/film/x.sdf\n')
        self.assertEqual(mvp.depot_camera('fire0000000000001'), 'worlds/film/x.sdf')
        self.assertEqual(mvp.depot_camera('fire0000000000001', 'a.sdf'), 'a.sdf')

    def test_front_fire_wording_claims_no_side_view(self):
        # a depot run whose fire the FRONT view already caught (the film's runs): the narration and captions must not say that a side view found it
        real = mvp.depot_kind
        mvp.depot_kind = lambda rid: 'front_fire'
        try:
            title, narr, caps = mvp.depot_texts('x')
        finally:
            mvp.depot_kind = real
        self.assertIn('火', title)
        self.assertNotIn('peek', narr)
        self.assertNotIn('横', ''.join(narr.values()))
        self.assertNotIn('peek', caps)
        self.assertNotIn('search', narr)

    def test_storyboard_accepts_a_depot_run_and_estimates_its_length(self):
        a = Namespace(deliver=None, recover='search00000000001', empty=None, fire=None, hidden_fire=None, memory=None, advice=None,
                      depot='fire0000000000001', depot_camera=None, summary_card=True, repo_url='x')
        parts, est, applied = mvp.fit_budget(a)
        missions = [p for p in parts if p['kind'] == 'mission']
        self.assertEqual([m['run_dir'][-17:] for m in missions], ['search00000000001', 'fire0000000000001'])   # no demo 1
        dep = missions[-1]
        self.assertEqual(dep['film_camera'], 'worlds/film/film_camera_depot.sdf')
        self.assertTrue(all(k in dep['captions'] for k in ('go', 'check', 'peek', 'after')))
        self.assertIn('避難所B', dep['captions']['go'])          # {instr} was replaced by the run's instruction
        secs = {id(p): x for p, x in est}
        self.assertGreater(secs[id(dep)], 5)
        self.assertLessEqual(sum(secs.values()), mvp.LIMIT_S)

    def test_demo_video_names_the_depot_bays_and_labels_them(self):
        self.assertEqual(mdv.station_ja('water'), '拠点W'); self.assertEqual(mdv.station_ja('M2'), '拠点M2')
        run = mdv.load_run(self.base / 'outputs/runs/fire0000000000001')
        labels = {t: xyz for xyz, t, _ in mdv.overlay_labels(run['mission'], {})}
        for bay in ('拠点W1', '拠点M1', '拠点W2', '拠点M2', '避難所 B', '火災'):
            self.assertIn(bay, labels)
        self.assertEqual(labels['拠点W2'][:2], (-2.8, -1.4))
        # the hazard sits behind W1 (away from the origin), inside the arena's x > 2 side
        self.assertGreater(labels['火災'][0], 2.0)
        eps = mdv.checkpoint_episodes(run)
        self.assertEqual([e.get('peek') for e in eps], [None, 'L'])
        self.assertGreater(len(mdv.speed_plan(run, {'fast': 8.0, 'check_speed': 3.0})), 3)
        srch = mdv.checkpoint_episodes(mdv.load_run(self.base / 'outputs/runs/search00000000001'))
        self.assertEqual([e['station'] for e in srch], ['W1', 'W2'])

    def test_arena_labels_unchanged(self):
        ls = {t: xyz for xyz, t, _ in mdv.overlay_labels({'world_variant': None}, {})}
        self.assertEqual(sorted(ls), ['物資拠点 M', '物資拠点 W', '避難所 B'])


class FilmWorlds(unittest.TestCase):
    def test_frozen_file_is_the_generator_output(self):
        self.assertEqual(fdw.load(), json.loads(json.dumps(fdw.build())))

    def test_not_a_trial_world_of_x_xd_or_the_pilot(self):
        def depot_seeds_and_lights(path):
            out = set()
            p = json.loads((ROOT / path).read_text(encoding='utf8'))
            for t in p.get('trials') or p.get('worlds') or []:
                ws = t.get('world_spec') or {}
                if ws.get('depot'):
                    out.add(('seed', ws['depot'].get('seed')))
                    out.add(('light', json.dumps(ws.get('lighting_params'), sort_keys=True)))
            return out
        theirs = set()
        for f in ('experiments/campaign_x_protocol.json', 'experiments/campaign_x_pilot_protocol.json',
                  'experiments/campaign_xd_protocol.json', 'experiments/campaign_x_steer_candidates.json'):
            if (ROOT / f).is_file():
                theirs |= depot_seeds_and_lights(f)
        self.assertGreater(len(theirs), 100)       # the comparison is not vacuous
        for tag, w in fdw.load()['worlds'].items():
            ws = w['world_spec']
            self.assertNotIn(('seed', ws['depot']['seed']), theirs, tag)
            self.assertNotIn(('light', json.dumps(ws['lighting_params'], sort_keys=True)), theirs, tag)
            self.assertEqual(ws['depot']['stations'], 4)

    def test_worlds_show_the_intended_design(self):
        w = fdw.load()['worlds']
        s = w['search']['world_spec']['depot']['supply_at']
        self.assertEqual((s['W1'], s['W2']), ('medicine', 'water'))           # the first water bay is swapped, the second holds water
        for tag in ('fire1', 'fire2', 'fire3'):
            sp = w[tag]['world_spec']
            self.assertEqual(sp['hazard_at'], 'W1'); self.assertEqual(sp['depot']['supply_at']['W1'], 'water')
            self.assertLess(sp['hazard_geom'][2], 0.7)                         # small fire (hard class), not the large one
            self.assertTrue(sp['depot']['particle_smoke'])

    @unittest.skipUnless((ROOT / 'worlds/assets/aws-wh/models/aws_robomaker_warehouse_WallB_01/model.sdf').is_file(), 'depot assets not fetched')
    def test_worlds_build_and_validate_offline(self):
        with tempfile.TemporaryDirectory() as d:
            for tag in fdw.load()['worlds']:
                self.assertTrue(fdw.build_world(tag, Path(d) / tag).is_file())


class EvidenceCard(unittest.TestCase):
    def test_fits_its_slot(self):
        card = mvp.evidence_card(mvp.EVIDENCE_S)
        self.assertIsNotNone(card)
        self.assertLessEqual(len(card['rows']), mvp.EVIDENCE_ROWS_MAX)
        self.assertLessEqual(mvp.speak_s(card['narration']) + mvp.CARD_PAD_S, mvp.EVIDENCE_S)
        for label, (cell, _) in card['rows']:
            self.assertLessEqual(mvp.cell_px(cell), mvp.EVIDENCE_CELL_PX, cell)
            self.assertLessEqual(mvp.cell_px(label), 560, label)
        names = ''.join(r[0] for r in card['rows'])
        for key in ('閉ループ A', '画像 W', '閉ループ G', '閉ループ E'):
            self.assertIn(key, names)


if __name__ == '__main__':
    unittest.main()
