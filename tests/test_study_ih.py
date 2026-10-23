"""Study IH: the destination rule, the frozen text set and the outcome rule."""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts import ih_eval as ih  # noqa: E402
from rescuemind import intent_llm as il  # noqa: E402


class Rule(unittest.TestCase):
    def test_other_places_are_named(self):
        for t in ('公民館に薬を持っていって', '市役所に水をお願い', '避難所1に飲料水を', '北側の避難所に救急箱を', 'Deliver water to the school.', '第二避難所に水を届けて'):
            self.assertTrue(il.names_other_destination(t), t)

    def test_shelter_b_and_no_place_are_not_touched(self):
        for t in ('避難所Bに飲料水を届けて', 'お水を届けてください', '体育館になっている避難所Bに水を届けてください', 'shelter Bに救急箱', '水、避難所Bへ'):
            self.assertIsNone(il.names_other_destination(t), t)

    def test_numbered_other_shelter_is_named_even_when_b_appears(self):
        self.assertTrue(il.names_other_destination('避難所Bではなく第二避難所に水を'))

    def test_flag_default_off_and_on_before_the_model(self):
        ok = {'accept': True, 'item': 'water', 'reason': 'llm_intent_accepted', 'probs': {}}
        with mock.patch.object(il, 'parse_instruction_llm', return_value=ok) as m:
            self.assertTrue(il.decide_intent_hybrid('公民館に水を届けて')['accept'])           # default off: the submitted v3.6
            self.assertEqual(m.call_count, 1)
            r = il.decide_intent_hybrid('公民館に水を届けて', destination_check=True)
            self.assertEqual((r['accept'], r['reason'], r['rule']), (False, 'unsupported_shelter', 'named_other_destination'))
            self.assertEqual(m.call_count, 1)                                                  # refused before the model was asked
            self.assertTrue(il.decide_intent_hybrid('避難所Bに水を届けて', destination_check=True)['accept'])


class Set(unittest.TestCase):
    def test_counts_uniqueness_and_no_overlap(self):
        rows = ih.load_rows()
        self.assertEqual((len(rows), len({r['text'] for r in rows}), sum(r['expect'] == 'accept' for r in rows)), (133, 133, 61))
        self.assertTrue(all(r['item'] in ('water', 'medicine') for r in rows if r['expect'] == 'accept'))
        seen = set()
        for f in ('ig_v1', 'held_out_v34', 'dev_v35'):
            seen |= {json.loads(l)['text'] for l in (ROOT / f'experiments/intent_eval/{f}.jsonl').read_text(encoding='utf8').splitlines() if l.strip()}
        for f in ('intent_flip_set', 'intent_flip_set2'):
            seen |= {json.loads(l)['text'] for l in (ROOT / f'experiments/{f}.jsonl').read_text(encoding='utf8').splitlines() if l.strip()}
        self.assertEqual([r['text'] for r in rows if r['text'] in seen], [])

    def test_committed_file_matches_generator(self):
        import make_intent_ih_set as mk
        rows = [json.loads(l) for l in (ROOT / 'experiments/intent_eval/ih_v1.jsonl').read_text(encoding='utf8').splitlines()]
        want = [dict(text=t, expect='accept', item=it, category=c) for c, items in mk.ROWS.items() for t, it in items] + \
               [dict(text=t, expect='reject', category=c) for c, items in mk.REJECT.items() for t in items]
        self.assertEqual(rows, want)

    def test_outcome_rule_and_script_lock(self):
        acc, rej = {'expect': 'accept', 'item': 'water'}, {'expect': 'reject'}
        self.assertEqual(ih.outcome(acc, {'accept': True, 'item': 'medicine'}), 'unsafe')
        self.assertEqual(ih.outcome(rej, {'accept': True, 'item': 'water'}), 'unsafe')
        self.assertEqual(ih.outcome(acc, {'accept': False, 'item': None}), 'false_refuse')
        s = (ROOT / 'scripts/ih_run.sh').read_text()
        self.assertIn('flock 9', s)
        for f in ('PREREGISTRATION_IH.md', 'ih_v1.jsonl', 'ih_eval.py', 'intent_llm.py'):
            self.assertIn(f, s)


if __name__ == '__main__':
    unittest.main()
