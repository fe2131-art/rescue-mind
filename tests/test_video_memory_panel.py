"""Memory change report box in the demo video AI panel (synthetic frame, no filmed run needed)."""
import importlib.util
import os
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('make_demo_video', ROOT / 'scripts' / 'make_demo_video.py')
mdv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mdv)

RESULT = {'memory_update': {'changes': [
    {'station': 'water', 'text_ja': '拠点「water」の物資が前回（医療物資）から変化（飲料水）'},
    {'station': 'medicine', 'text_ja': '拠点「medicine」：前回なかった火・煙を新たに観測'},
    {'station': 'x', 'text_ja': '3行目は出さない'}]}}


class MemoryPanel(unittest.TestCase):
    def test_lines_mapped_to_japanese_stations(self):
        ls = mdv.change_lines_ja(RESULT)
        self.assertIn('拠点W', ls[0]); self.assertNotIn('water', ls[0])
        self.assertIn('拠点M', ls[1]); self.assertNotIn('medicine', ls[1])
        self.assertEqual(mdv.change_lines_ja({}), [])
        self.assertEqual(mdv.change_lines_ja({'memory_update': {'changes': []}}), [])
        self.assertEqual(mdv.change_lines_ja({'outcome': RESULT})[0], ls[0])

    @unittest.skipUnless(os.path.exists(mdv.FONT_R) and os.path.exists(mdv.FONT_B),
                         'Noto Sans CJK fonts (rm-dev image) not installed; pixel layout needs them')
    def test_box_fits_banner_slot_and_clear_of_verdict(self):
        img = Image.new('RGB', (1920, 1080), mdv.BG)
        d = ImageDraw.Draw(img, 'RGBA')
        mdv.rounded(d, (1340, 552, 1880, 1048), mdv.PANEL, 18)
        y = 640
        box = (1356, y - 4, 1866, y + 62)
        self.assertTrue(mdv.draw_memory_changes(d, mdv.change_lines_ja(RESULT), box))
        self.assertLess(box[3], y + 66)          # next content starts at y+66
        self.assertLess(box[3], 980)             # verdict box starts at 980
        # text stays inside the box: pixels right of the box edge are untouched panel colour
        self.assertEqual(img.getpixel((1868, y + 20)), mdv.PANEL)
        self.assertFalse(mdv.draw_memory_changes(d, [], box))
        out = os.environ.get('MEM_PANEL_PREVIEW')
        if out:
            # full-panel preview with a verdict box and prob bars at the worst-case layout
            yy = y + 66 + 32
            for _ in range(2):
                yy += 24
                for lab, col in (('water', mdv.WATER), ('medicine', mdv.MED), ('other', mdv.OTHER)):
                    mdv.prob_bar(d, 1380, yy, 240, mdv.ITEM_JA[lab], 0.5, col); yy += 27
            self.assertLessEqual(yy, 980)
            mdv.rounded(d, (1362, 980, 1858, 1036), (30, 90, 60), 14)
            mdv.text(d, (1610, 1008), '判定：許可 → 避難所Bへ出発', 26, mdv.INK, True, anchor='mm')
            img.crop((1330, 540, 1890, 1060)).save(out)


if __name__ == '__main__':
    unittest.main()
