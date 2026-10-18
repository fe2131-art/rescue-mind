"""scripts/youtube_chapters.py: the chapter list is YouTube-valid by construction (0:00 start, >= 3 chapters, ascending, each >= 10 s)."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ytc', ROOT / 'scripts/youtube_chapters.py')
yc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(yc)


def seg(a, b, title, kind='card'):
    return {'start_s': a, 'end_s': b, 'title': title, 'kind': kind,
            'speed': 'x8' if kind == 'mission' else None, 'run_id': f'r{int(a)}' if kind == 'mission' else None}


# the v5 video as rendered: five cards of 5-10 s between the demos
V5 = [seg(0, 9.73, 'RescueMind'), seg(9.73, 35.9, 'デモ1：A', 'mission'), seg(35.9, 74.07, 'デモ2：B', 'mission'),
      seg(74.07, 79.63, '記憶'), seg(79.63, 108.9, 'デモ3：記憶 → 直行', 'mission'), seg(108.9, 114.4, 'H例'),
      seg(114.4, 120.03, '締める'), seg(120.03, 143.37, 'デモ4：C', 'mission'), seg(143.37, 166.47, '表', 'table'),
      seg(166.47, 172.53, 'RescueMind')]


class YoutubeChapters(unittest.TestCase):
    def test_raw_v5_is_invalid(self):
        self.assertGreaterEqual(len(yc.validate(V5)), 4)

    def test_merge_makes_it_valid(self):
        ch = yc.merge_short(V5)
        self.assertEqual(yc.validate(ch), [])
        self.assertEqual(len(ch), 5)
        self.assertEqual(yc.mmss(ch[0]['start_s']), '0:00')
        self.assertTrue(all(x >= 10 for x in yc.lengths(ch)))
        self.assertEqual(ch[-1]['end_s'], 172.53)                          # the end of the video is kept
        self.assertTrue(all(a['end_s'] == b['start_s'] for a, b in zip(ch, ch[1:])))      # no gap, no overlap

    def test_titles_kinds_and_runs(self):
        ch = yc.merge_short(V5)
        self.assertEqual(ch[0]['title'], 'RescueMind ＋ デモ1：A')
        self.assertEqual(ch[0]['demo_title'], 'デモ1：A')
        self.assertEqual(ch[0]['run_id'], 'r9')
        self.assertEqual(ch[2]['title'], 'デモ3：記憶 → 直行 ＋ H例')          # '記憶' alone is contained in the demo title: not repeated
        self.assertEqual(ch[3]['title'], '締める ＋ デモ4：C')                  # two short cards in a row: first into the preceding, second into the next
        self.assertEqual(ch[4]['kind'], 'table')
        self.assertEqual(sum(c['kind'] == 'mission' for c in ch), 4)         # all four demo runs survive
        self.assertEqual(len(yc.flatten(ch)), len(V5))

    def test_idempotent_and_reversible(self):
        ch = yc.merge_short(V5)
        self.assertEqual(yc.merge_short(ch), ch)
        self.assertEqual(yc.merge_short(yc.flatten(ch)), ch)
        self.assertEqual([{k: v for k, v in s.items()} for s in yc.flatten(ch)], V5)

    def test_floored_marks_count(self):
        """9.73 s is short, and so is a chapter whose shown marks are 9 s apart (0:09 -> 0:18)."""
        ch = yc.merge_short([seg(0, 9.9, 'a'), seg(9.9, 19.1, 'b'), seg(19.1, 40, 'c'), seg(40, 60, 'd'), seg(60, 80, 'e')])
        self.assertEqual(yc.validate(ch), [])
        self.assertEqual(yc.validate([seg(0, 9.9, 'a'), seg(9.9, 20, 'b'), seg(20, 40, 'c')]), ["chapter 'a' (0:00) is 9 s, shorter than 10 s"])

    def test_last_short_goes_into_previous(self):
        ch = yc.merge_short([seg(0, 20, 'a'), seg(20, 40, 'b'), seg(40, 60, 'c'), seg(60, 64, 'end')])
        self.assertEqual([c['title'] for c in ch], ['a', 'b', 'c ＋ end'])

    def test_first_must_start_at_zero(self):
        self.assertIn('first chapter does not start at 0:00', yc.validate([seg(1, 20, 'a'), seg(20, 40, 'b'), seg(40, 60, 'c')]))
        self.assertEqual(yc.merge_short([seg(1, 20, 'a'), seg(20, 40, 'b'), seg(40, 60, 'c')])[0]['start_s'], 0)

    def test_validate_rules(self):
        ok = [seg(0, 20, 'a'), seg(20, 40, 'b'), seg(40, 60, 'c')]
        self.assertEqual(yc.validate(ok), [])
        self.assertTrue(any('at least 3' in x for x in yc.validate(ok[:2])))
        self.assertTrue(any('ascending' in x for x in yc.validate([ok[0], ok[2], ok[1]])))
        self.assertEqual(yc.validate([]), ['no chapters'])

    def test_impossible_raises(self):
        with self.assertRaises(ValueError):
            yc.merge_short([seg(0, 8, 'a'), seg(8, 16, 'b'), seg(16, 24, 'c')])      # 24 s cannot hold 3 chapters of 10 s
        with self.assertRaises(ValueError):
            yc.merge_short([])

    def test_repo_chapter_file_is_valid(self):
        ch = json.loads((ROOT / 'docs/video_chapters.json').read_text(encoding='utf8'))
        self.assertEqual(yc.validate(ch), [])


if __name__ == '__main__':
    unittest.main()
