"""scripts/make_youtube_description.py: the description follows the rendered video's chapters, never stale text."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mkyt', ROOT / 'scripts/make_youtube_description.py')
mk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mk)

SP = '走行8倍速・確認動作3倍速・AI判断の瞬間は等速'


def ch(start, end, title, kind, speed=None):
    return {'start_s': start, 'end_s': end, 'title': title, 'kind': kind, 'speed': speed, 'run_id': None}


CHAPTERS = [
    ch(0.0, 6.0, 'RescueMind', 'card'),
    ch(6.0, 40.0, 'デモ1：言い換えた指示でも配達', 'mission', SP),
    ch(40.0, 85.5, 'デモ2：欠品 → 停止', 'mission', SP),
    ch(85.5, 130.0, 'デモ3：前回の記憶を使って最短で配達', 'mission', SP),
    ch(130.0, 145.0, '証拠のまとめ', 'table'),
    ch(145.0, 151.0, 'RescueMind', 'card'),
]


class YoutubeDescription(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.res = Path(self.tmp.name)
        (self.res / 'campaign_E_ledger.jsonl').write_text('\n'.join(json.dumps(r) for r in [
            {'expected_action': 'ALLOW', 'observed_action': 'ALLOW', 'correct': True},
            {'expected_action': 'DENY_HAZARD', 'observed_action': 'DENY_HAZARD', 'correct': True},
            {'expected_action': 'DELIVER_AFTER_SEARCH', 'observed_action': 'ALLOW_AFTER_SEARCH', 'correct': True},
            {'expected_action': 'ALLOW', 'observed_action': 'ALLOW', 'correct': False, 'final': False},
        ]) + '\n', encoding='utf8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_structure_comes_from_chapters(self):
        text, facts = mk.build_description(CHAPTERS, self.res)
        self.assertEqual(facts['length_mmss'], '2:31')
        self.assertIn('約2分31秒（`docs/video_chapters.json` の終端 151 秒）', text)
        self.assertIn('デモは3場面：①言い換えた指示でも配達 ②欠品 → 停止 ③前回の記憶を使って最短で配達。', text)
        self.assertIn('走行区間は8倍速、確認動作は3倍速、AI判断の瞬間（画像取得〜判断）は等速です', text)
        # the 6 s cards are merged into their neighbours: YouTube ignores a list with a chapter shorter than 10 s
        for line in ('0:00 RescueMind ＋ デモ1：言い換えた指示でも配達', '0:40 デモ2：欠品 → 停止', '1:25 デモ3：前回の記憶を使って最短で配達',
                     '2:10 証拠のまとめ ＋ RescueMind'):
            self.assertIn(line, text)
        self.assertEqual(facts['warnings'], [])
        self.assertEqual(len(facts['chapters']), 4)
        self.assertEqual(facts['n_tables'], 1)

    def test_fixed_parts_kept(self):
        text, _ = mk.build_description(CHAPTERS, self.res)
        for s in ('## タイトル\nPAI最終課題_141628', '## 公開設定チェック（課題の指定）', 'VOICEVOX:四国めたん',
                  'https://github.com/fe2131-art/rescue-mind'):
            self.assertIn(s, text)

    def test_numbers_only_from_existing_files(self):
        text, _ = mk.build_description(CHAPTERS, self.res)
        self.assertIn('ランダムに作った3個の世界で、期待どおりの行動 3/3、誤った物資・火のある拠点からの配達 0件', text)  # non-final row ignored
        for absent in ('評価H', '評価J', '評価Z', '評価R', '評価P', '実行中'):
            self.assertNotIn(absent, text)
        (self.res / 'h_summary.json').write_text(json.dumps({
            'P1_efficiency_relocation_persist': {'n_pairs': 8, 'time_M0_median_s': 120.4, 'time_M2_median_s': 80.2},
            'P2_safety_naive_vs_verified': {'n_pairs': 32, 'unsafe_M1': 3, 'unsafe_M2': 0},
            'P3_no_extra_risk_vs_v36': {'unsafe_M0': 1},
            'per_arm': {a: {'time_median_s': t, 'by_transition': {'relocation_change': {'time_median_s': r}}}
                        for a, t, r in (('M0', 90.4, 100.2), ('M2', 70.2, 110.6))}}), encoding='utf8')
        (self.res / 'p_summary.json').write_text(json.dumps({
            'n': 400, 'recall': {'k': 298, 'n': 300}, 'false_alarm': {'k': 64, 'n': 100}}), encoding='utf8')
        text, _ = mk.build_description(CHAPTERS, self.res)
        self.assertIn('評価H：所要時間の中央値は、物資が移されたままの8出動で 記憶なし 120秒・検証つき記憶 80秒', text)
        self.assertIn('物資が元に戻った出動では 100秒 対 111秒と遅い（遠回りの代償）。全体は 90→70秒', text)
        self.assertIn('危険な配達は 32出動のうち、確認を省く素朴な記憶 3件（省く設計の比較）、記憶なし 1件、検証つき記憶 0件', text)
        self.assertIn('検出 298/300、火の無い写真で誤警報 64/100', text)
        self.assertNotIn('評価J', text)

    def test_no_missions_no_speed_text(self):
        text, facts = mk.build_description([ch(0, 70, 'RescueMind', 'card')], self.res)
        self.assertNotIn('デモは', text)
        self.assertNotIn('倍速', text)
        self.assertEqual(mk.build_submission_block(facts).count('倍速'), 0)

    def test_submission_block_and_idempotence(self):
        _, facts = mk.build_description(CHAPTERS, self.res)
        block = mk.build_submission_block(facts)
        self.assertIn('動画の3デモ', block)
        self.assertIn('約2分31秒', block)
        md = f'a\n{mk.V_START}\nold\n{mk.V_END}\nb\n'
        once = mk.splice(md, block)
        self.assertEqual(once, mk.splice(once, block))
        self.assertTrue(once.startswith('a\n') and once.endswith('\nb\n'))
        with self.assertRaises(ValueError):
            mk.splice('no markers', block)

    def test_cli_check_and_write(self):
        cj = self.res / 'chapters.json'
        cj.write_text(json.dumps(CHAPTERS, ensure_ascii=False), encoding='utf8')
        sub = self.res / 'SUBMISSION.md'
        sub.write_text(f'x\n{mk.V_START}\n{mk.V_END}\n', encoding='utf8')
        out = self.res / 'YT.md'
        args = ['--chapters', str(cj), '--results', str(self.res), '--out', str(out), '--submission', str(sub)]
        self.assertEqual(mk.main(args + ['--check']), 1)
        self.assertEqual(mk.main(args), 0)
        self.assertEqual(mk.main(args + ['--check']), 0)
        self.assertIn('2:10 証拠のまとめ ＋ RescueMind', out.read_text(encoding='utf8'))

    def test_description_limit_counts_characters(self):
        text, _ = mk.build_description(CHAPTERS, self.res)
        body = text.split('## 概要欄\n', 1)[1].split('\n\n## 公開設定', 1)[0]
        self.assertLessEqual(len(body), mk.LIMIT)
        self.assertLess(mk.LIMIT, 5000)

    def test_repo_files_are_current(self):
        """The committed description and submission notes match the committed chapters and result files."""
        self.assertEqual(mk.main(['--check']), 0)


if __name__ == '__main__':
    unittest.main()
