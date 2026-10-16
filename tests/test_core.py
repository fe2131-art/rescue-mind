import unittest
from rescuemind.intent import IntentClassifier, parse_shelter
from rescuemind.planner import Grid, astar, rescue_grid
from rescuemind.sim import simulate, START, STATIONS, SHELTERS

class TestRescueMind(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = IntentClassifier('tfidf')

    def test_intent_known_water(self):
        self.assertEqual(self.model.classify('水を優先してください').item, 'water')

    def test_intent_known_medicine(self):
        self.assertEqual(self.model.classify('医薬品を至急配送して').item, 'medicine')

    def test_shelter_parsing(self):
        self.assertEqual(parse_shelter('避難所Ａへ'), 'A')
        self.assertEqual(parse_shelter('避難所Bへ'), 'B')

    def test_empty_instruction_rejected(self):
        with self.assertRaises(ValueError):
            self.model.classify(' ')

    def test_grid_path_exists(self):
        g=rescue_grid()
        self.assertTrue(astar(g, START, STATIONS['water']))
        self.assertTrue(astar(g, STATIONS['water'], SHELTERS['B']))
        self.assertTrue(astar(g, STATIONS['medicine'], SHELTERS['A']))

    def test_astar_avoids_walls(self):
        g=Grid(5, 5, {(2,1), (2,2), (2,3)})
        path=astar(g,(1,2),(3,2))
        self.assertTrue(path)
        self.assertTrue(all(g.free(p) for p in path))
        self.assertEqual(len(path)-1, 6)

    def test_unreachable(self):
        g=Grid(3,3,{(1,0),(1,1),(1,2)})
        self.assertEqual(astar(g,(0,1),(2,1)),[])

    def test_dynamic_adaptive_succeeds(self):
        r=simulate('水を避難所Bへ届けて', 'adaptive', self.model)
        self.assertTrue(r.success, r.reason)
        self.assertEqual(r.item, 'water')
        self.assertEqual(r.shelter, 'B')
        self.assertTrue(r.blockage_inserted)
        self.assertGreaterEqual(r.replans,1)

    def test_dynamic_fixed_fails(self):
        r=simulate('水を避難所Bへ届けて', 'fixed', self.model)
        self.assertFalse(r.success)
        self.assertEqual(r.reason, 'blocked')

    def test_no_obstacle_succeeds(self):
        r=simulate('水を避難所Bへ届けて', 'fixed', self.model, dynamic_obstacle=False)
        self.assertTrue(r.success)

    def test_repeatable(self):
        r1=simulate('水を避難所Bへ届けて', 'adaptive', self.model)
        r2=simulate('水を避難所Bへ届けて', 'adaptive', self.model)
        self.assertEqual((r1.path_length,r1.replans), (r2.path_length,r2.replans))

if __name__ == '__main__':
    unittest.main()
