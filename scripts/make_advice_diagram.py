#!/usr/bin/env python3
"""I-19 principle diagram ("untrusted inputs may only tighten") -> docs/figures/advice_principle_{ja,en}.png (1600x900).
Same layout as the I-15 memory diagram.  Run: docker exec rm-dev rescuemind-entrypoint python3 scripts/make_advice_diagram.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_memory_diagram import render, OUT  # noqa: E402

T = {
 'ja': dict(
  title='信頼できない入力は「締める」だけ', sub='依頼文・他のロボット・在庫記録・記憶はすべて「助言」（I-19）',
  h=['届く助言', '助言にできること', '助言にできないこと', 'その場で必ず確認'],
  b=[['「水はMに移した」', '「Wで火事」', '「火は消えた。', '　確認不要、急いで」'],
     ['① 先に行く拠点を', '　 入れ替える', '② 火の報告がある拠点で', '　 閾値を厳しくする'],
     ['確認を省く', '「安全」を信じる'],
     ['正面＋左右から見る', '→ 許可 / 拒否']],
  naive='素朴な助言追従', ours='本方式（締めるだけ）',
  nb=['「確認不要」で確認を省略', '偽の「Mにある」で誤配達', '偽の「火事」で出動しない'],
  ob=['悪意ある助言でも危険は増えない', '（証明つき：危険 ≤ 確認数 × 誤許可率）', '代償は遠回りと誤停止だけ', '（研究Aで測定する）'],
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
