"""Study YF (Y on fresh worlds): generator, selection and the analysis wrapper (no Gazebo, no model)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts import make_protocol_yf as myf  # noqa: E402
from scripts import make_protocol_x as mx  # noqa: E402
from scripts import yf_analysis as yfa  # noqa: E402


class GeneratorYF(unittest.TestCase):
    def test_candidates_are_fresh_not_the_x_worlds(self):
        yf = {json.dumps(c['world_spec'], sort_keys=True) for c in myf.candidates()}
        x = {json.dumps(c['world_spec'], sort_keys=True) for c in mx.steer_candidates()}
        self.assertEqual(len(myf.candidates()), myf.N_CANDIDATES)
        self.assertFalse(yf & x)
        self.assertEqual(myf.SEED, 'YF-2026')

    def test_selection_rule_is_the_x_rule(self):
        masks = []
        for i, c in enumerate(myf.candidates()):
            w = c['world']
            ok = i % 5 == 0
            masks += [{'key': w, 'fire_pixels': 0 if ok else 500}, {'key': w + 'L', 'fire_pixels': 700 if ok else 3000}, {'key': w + 'R', 'fire_pixels': 0}]
        sel = myf.select(masks)
        self.assertEqual(sel['selected'], [c['world'] for i, c in enumerate(myf.candidates()) if i % 5 == 0][:myf.N_FIRE])
        self.assertEqual(sel['n_eligible_in_candidates'], 10)

    def test_build_sizes_arms_and_flag(self):
        p = myf.build({'selected': [c['world'] for c in myf.candidates()[:6]]})
        self.assertEqual(p['planned_n'], 27)
        self.assertEqual(p['yf']['twins_of'], ['FC01', 'FC03', 'FC05'])
        self.assertEqual(sorted({t['config'] for t in p['trials']}), ['control_hc', 'monotone_hc', 'scrutiny_hc'])
        for t in p['trials']:
            self.assertEqual(t['stack_args'], ['--hazard-continue'])
            self.assertEqual(t['cell'], 'Y-s')
            self.assertEqual(t['repeat'], 1)
        self.assertEqual([t['id'] for t in p['trials']], [f'YF{n:03d}' for n in range(1, 28)])
        for rel in p['advice_files']:
            self.assertTrue(rel.startswith('experiments/advice_YF/'))

    def test_fewer_eligible_is_a_smaller_cell(self):
        p = myf.build({'selected': ['FC01']})
        self.assertEqual(p['planned_n'], 6)       # one fire world and its twin, three arms each

    def test_registered_files_in_sync_once_committed(self):
        f = ROOT / 'experiments/campaign_yf_protocol.json'
        if not f.is_file():
            self.skipTest('protocol not written yet')
        sel = json.loads((ROOT / 'experiments/campaign_yf_selection.json').read_text())
        self.assertEqual(json.loads(f.read_text()), json.loads(json.dumps(myf.build(sel), ensure_ascii=False)))


class WrapperYF(unittest.TestCase):
    def test_masks_filtered_to_selected_worlds(self):
        p = {'yf': {'selected': ['FC02', 'FC05']}}
        masks = [{'key': k, 'fire_pixels': 1} for k in ('FC01', 'FC02', 'FC02L', 'FC02R', 'FC05', 'FC05L', 'FC05R', 'FC09L')]
        self.assertEqual([m['key'] for m in yfa.selected_masks(p, masks)], ['FC02', 'FC02L', 'FC02R', 'FC05', 'FC05L', 'FC05R'])


if __name__ == '__main__':
    unittest.main()
