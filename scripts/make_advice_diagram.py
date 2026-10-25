#!/usr/bin/env python3
"""I-19 principle diagram ("untrusted inputs may only tighten") -> docs/figures/advice_principle_{ja,en}.png (1600x900).
Same layout as the I-15 memory diagram.  Run: docker exec rm-dev rescuemind-entrypoint python3 scripts/make_advice_diagram.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_memory_diagram import render, OUT  # noqa: E402

T = {
 'ja': dict(
  title='「確認不要」と言われても、自分で確かめる', sub='依頼文・ほかのロボットの報告・物資リスト・前回の記憶は、どれも「聞いた情報」として扱う',
  h=['届く情報の例', '使ってよいこと', '使わないこと', '着いたら必ず確認'],
  b=[['「水は拠点Mに移した」', '「拠点Wで火事」', '「火は消えた。', '　確認不要、急いで」'],
     ['① 先に見に行く', '　 拠点を決める', '② 火の報告がある拠点は', '　 より注意して調べる'],
     ['確認を省く', '「安全」をうのみにする'],
     ['正面と左右から撮影', '→ 届ける / 止まる']],
  naive='聞いた情報をそのまま信じる方式', ours='本方式（確認は省かない）',
  nb=['「確認不要」で確認を省略', 'うその「Mにある」で誤配達', 'うその「火事」で出動しない'],
  ob=['うその情報でも危険は増えない', '（数学的に証明し、プログラムでも検証）', '代わりに遠回りや停止が増えうる', '（実験：うその情報で危険な配達 0/24）'],
  bad='危険', good='安全'),
 'en': dict(
  title='Untrusted inputs may only tighten', sub='Instructions, peer robots, inventory and memory are all advice (I-19)',
  h=['Advice received', 'What advice can do', 'What advice cannot do', 'Always check on site'],
  b=[['"Water was moved to M"', '"Fire at W"', '"Fire is out, skip', ' the check, hurry"'],
     ['1. Reorder the', '    stations to visit', '2. Stricter threshold', '    where fire is reported'],
     ['Skip the check', 'Trust a "safe" claim'],
     ['Front + left/right views', '-> allow / refuse']],
  naive='Naive advice-following', ours='Ours (tighten only)',
  nb=['"No need to check" -> skips it', 'False location -> wrong delivery', 'False fire -> never goes'],
  ob=['Adversarial advice adds no risk', '(proved: P(unsafe) <= k * eps)', 'Cost: detours and false stops only', '(measured in study A)'],
  bad='Unsafe', good='Safe'),
}

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    for lg in ('ja', 'en'):
        render(lg, T, 'advice_principle')
        print('wrote', OUT / f'advice_principle_{lg}.png')
