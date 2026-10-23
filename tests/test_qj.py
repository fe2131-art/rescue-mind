"""Study QJ (I-90): inventory, prompts and pixel audit of the text-to-image scenes, and the stop rule of the analysis."""
import json
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT))
import qj_generate as g  # noqa: E402


def test_inventory_is_paired_across_modes():
    a, b, c = g.inventory('N0'), g.inventory('NF'), g.inventory('NB')
    assert len(a) == len(b) == len(c) == 120
    assert [x['seed'] for x in a] == [x['seed'] for x in b] == [x['seed'] for x in c]
    assert len({x['seed'] for x in a}) == 120
    assert {(x['item'], x['light']) for x in a} == set(g.TEMPLATES) and len(g.TEMPLATES) == 6


def test_prompts_differ_only_by_the_fire_clause():
    n0, nf, nb = (g.prompt_of(m, 'water', 0) for m in ('N0', 'NF', 'NB'))
    assert nf.startswith(n0) and nb.startswith(n0) and nf != nb
    assert 'fire' not in n0.lower() and 'flame' in nf.lower() and 'large fire' in nb.lower()


def test_flame_share_counts_orange_pixels_only():
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    img[:, :] = (120, 120, 120)
    assert g.flame_share(img) == 0.0
    img[:5, :] = (255, 140, 20)
    assert 0.4 < g.flame_share(img) <= 0.5


def test_analysis_stop_rule_blocks_the_claim(tmp_path, monkeypatch):
    import qj_analysis as a
    monkeypatch.setattr(a, 'RES', tmp_path)
    (tmp_path / 'qj_byeye.json').write_text(json.dumps({'NF': {'n': 40, 'present': 30}, 'NB': {'n': 40, 'present': 40}}))

    def rec(score):
        return {'qj_item': 'water', 'qj_light': 0, 'flame_share': 0.0, 'p': score}
    monkeypatch.setattr(a, 'hazard_score', lambda r: r['p'])
    recs = {'N0': [rec(0.01)] * 120, 'NF': [rec(0.9)] * 120, 'NB': [rec(0.9)] * 120}
    monkeypatch.setattr(a, 'load', lambda m: recs[m])
    a.main()
    out = json.loads((tmp_path / 'qj_summary.json').read_text())
    assert out['NF']['claim_stopped'] and not out['claims']['QJ3_hard_fire_miss_at_most_20pct']       # 30/40 = 75% present < 85%
    assert out['claims']['QJ1_clean_false_stops_at_most_5pct'] and out['claims']['QJ2_large_fire_miss_at_most_10pct']
    (tmp_path / 'qj_byeye.json').unlink()
    a.main()
    assert 'QJ2_large_fire_miss_at_most_10pct' not in json.loads((tmp_path / 'qj_summary.json').read_text())['claims']        # not evaluated without the by-eye file
