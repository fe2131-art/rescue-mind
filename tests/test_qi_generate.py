"""Study QI generator: the pure parts (composite, flame-colour check, inventory) without a GPU."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import qi_generate as q  # noqa: E402


class Pure(unittest.TestCase):
    def test_composite_keeps_outside_bytes(self):
        base = np.zeros((6, 6, 3), np.uint8)
        edit = np.full((6, 6, 3), 200, np.uint8)
        region = np.zeros((6, 6), bool)
        region[2:4, 2:4] = True
        out = q.composite(base, edit, region)
        self.assertTrue((out[~region] == 0).all())
        self.assertTrue((out[region] == 200).all())

    def test_fire_colour_fraction(self):
        img = np.zeros((4, 4, 3), np.uint8)
        img[:2] = (255, 140, 20)
        region = np.ones((4, 4), bool)
        self.assertAlmostEqual(q.fire_colour_fraction(img, region), 0.5)
        self.assertEqual(q.fire_colour_fraction(img, np.zeros((4, 4), bool)), 0.0)

    def test_inventory_g_uses_clean_twin_with_fire_mask(self):
        items = q.inventory('G', 'test', ['F', 'L', 'R'])
        self.assertTrue(items)
        for x in items:
            self.assertEqual(x['kind'], 'twin')
            self.assertTrue((q.BASE / x['mask']).is_file())
            self.assertTrue((q.BASE / x['src']).is_file())
            self.assertIn('_', x['key'])


if __name__ == '__main__':
    unittest.main()
