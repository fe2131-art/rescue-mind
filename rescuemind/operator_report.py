"""I-18: a one-page report for the people on site, built only from what the robot logged (mission.json and the
orchestrator's stack_result.json).  It says what was asked, what the robot saw where, what it decided and why, what
changed since the last mission, and what a person should do next.  Pure functions: no ROS, no model calls.
The VLM's one-sentence description is shown as the robot's own words and is never used for the decision.
"""
from __future__ import annotations

ITEM_JA = {'water': '飲料水', 'medicine': '医療物資', 'other': '依頼物資以外／空', 'uncertain': '不確か'}
STATION_JA = {'water': '拠点W', 'medicine': '拠点M'}
SIDE_JA = {'L': '左', 'R': '右'}
REASON_JA = {
    'on_site_supply_confirmed': '依頼物資を確認',
    'local_vlm_disagree_or_wrong_supply': '依頼物資ではない／無い',
    'low_confidence_supply_match': '確信が足りない',
    'visible_hazard_at_checkpoint': '火・煙を検知',
    'memory_trusted': '（素朴な記憶）確認を省略',
}


def _p(call, key):
    sc = (call or {}).get('scores') or {}
    return sc.get(key)


def _check(station, cp, kind, side=None, image=None):
    calls = (cp or {}).get('model_calls') or {}
    first = calls.get('first') or {}
    dec = (cp or {}).get('decision') or {}
    probs = _p(first, 'supply_probs') or {}
    return {'kind': kind, 'station': station, 'side': side, 'image': image,
            'decision': dec.get('reason'), 'allow': dec.get('allow'),
            'seen': (first.get('result') or {}).get('supply'),
            'p_supply': {k: round(float(v), 3) for k, v in probs.items()},
            'p_hazard': _p(first, 'hazard_prob')}


def checks(mission: dict) -> list[dict]:
    """Every on-site check in order: recovery first station, the front check, then side views."""
    out = []
    rec = mission.get('recovery') or {}
    if rec:
        out.append(_check(rec.get('first_station'), rec.get('first_checkpoint'), 'front', image=rec.get('first_checkpoint_image')))
    st = mission.get('checkpoint_station')
    cp = mission.get('checkpoint') or {}
    if st and not cp.get('memory_trusted'):
        c = _check(st, cp, 'front', image='checkpoint.jpg')
        if (cp.get('decision') or {}).get('front_reason'):
            c['decision'], c['allow'] = cp['decision']['front_reason'], True      # the front itself approved
        out.append(c)
    for pk in ((mission.get('look_around') or {}).get('peeks') or []):
        out.append({'kind': 'side', 'station': st, 'side': pk.get('side'), 'image': pk.get('image'),
                    'decision': 'visible_hazard_at_checkpoint' if pk.get('hazard') else 'clear',
                    'allow': not pk.get('hazard'), 'seen': None, 'p_supply': {},
                    'p_hazard': _p((pk.get('model_calls') or {}).get('first'), 'hazard_prob')})
    return out


def outcome(mission: dict, result: dict) -> dict:
    """What happened, in operator terms."""
    state = (result or {}).get('state')
    item = (mission.get('intent') or {}).get('item')
    cp = mission.get('checkpoint') or {}
    dec = cp.get('decision') or {}
    rec = mission.get('recovery') or {}
    st = mission.get('checkpoint_station')
    if state in ('COMPLETED', 'COMPLETED_MEMORY_TRUSTED'):
        kind = 'delivered_after_search' if rec else 'delivered'
        if cp.get('memory_trusted'):
            kind = 'delivered_unverified'
    elif state == 'DENIED_BY_MEMORY':
        kind = 'refused_by_memory'
    elif state == 'COMPLETED_EXPECTED_DENIAL':
        kind = 'stopped_hazard' if dec.get('reason') == 'visible_hazard_at_checkpoint' else (
            'stopped_not_found' if dec.get('reason') == 'local_vlm_disagree_or_wrong_supply' else 'stopped_uncertain')
    else:
        kind = 'failed'
    return {'kind': kind, 'item': item, 'station': st, 'state': state}


def headline(o: dict) -> tuple[str, str]:
    """(short verdict, colour key) for the badge."""
    it = ITEM_JA.get(o['item'], o['item'])
    st = STATION_JA.get(o['station'], o['station'])
    return {
        'delivered': (f'{it}を確認し、避難所Bへ向かいました', 'good'),
        'delivered_after_search': (f'定位置に無かった{it}を{st}で見つけ、避難所Bへ向かいました', 'good'),
        'delivered_unverified': (f'確認せずに{st}から出発しました（素朴な記憶の比較対象）', 'bad'),
        'refused_by_memory': ('記憶だけで出発を取りやめました（素朴な記憶の比較対象）', 'warn'),
        'stopped_hazard': (f'{st}で火・煙を検知したため、配達せず停止しました', 'bad'),
        'stopped_not_found': (f'どの拠点にも{it}が見つからず、停止しました', 'warn'),
        'stopped_uncertain': ('物資を確信できなかったため、停止しました', 'warn'),
        'failed': ('システムの異常で中止しました（判断前の停止）', 'warn'),
    }[o['kind']]


def reasons(chk: list[dict], o: dict) -> list[str]:
    lines = []
    for c in chk:
        where = STATION_JA.get(c['station'], c['station'])
        if c['kind'] == 'side':
            ph = c['p_hazard']
            lines.append(f"{where}を{SIDE_JA.get(c['side'], c['side'])}0.4 mから見直し："
                         + (f'火・煙あり（確率 危険 {ph:.2f}）' if not c['allow'] else f'火・煙なし（確率 危険 {ph:.3f}）' if ph is not None else '火・煙なし'))
        else:
            ps = c['p_supply'].get(o['item'])
            nums = '・'.join(x for x in ((f'依頼物資 {ps:.2f}' if ps is not None else ''),
                                         (f"危険 {c['p_hazard']:.3f}" if c['p_hazard'] is not None else '')) if x)
            lines.append(f"{where}（正面）：{REASON_JA.get(c['decision'], c['decision'])}" + (f'（確率 {nums}）' if nums else ''))
    return lines


def next_actions(o: dict, mission: dict, result: dict) -> list[str]:
    it = ITEM_JA.get(o['item'], o['item'])
    st = STATION_JA.get(o['station'], o['station'])
    acts = {
        'delivered': [f'避難所Bで{it}の受け取りを確認してください。'],
        'delivered_after_search': [f'在庫表を更新してください：{it}は{st}にあります（次回はロボットの記憶もここを先に提案します）。',
                                   f'避難所Bで{it}の受け取りを確認してください。'],
        'stopped_hazard': [f'{st}付近の火災の可能性を、消防・施設管理者に確認してください。',
                           'ロボットはその場で停止しています。安全が確認されるまで、この拠点への出動は控えてください。'],
        'stopped_not_found': [f'{it}の在庫を補充するか、別の拠点を指示してください（両拠点とも確認済み）。'],
        'stopped_uncertain': ['拠点の物資を人が確認するか、明るさ・置き方を確認してから再出動してください。'],
        'delivered_unverified': ['（比較対象）実際の運用では使いません。'],
        'refused_by_memory': ['（比較対象）実際の運用では使いません。'],
        'failed': ['ログを確認して再出動してください（判断前の異常のため、安全側で中止しています）。'],
    }[o['kind']]
    return acts


def memory_lines(mission: dict, result: dict) -> list[str]:
    out = []
    plan = mission.get('memory') or {}
    if plan.get('mode') == 'verified':
        out += [f'記憶の提案：{r}' for r in plan.get('rationale') or []]
    for c in ((result or {}).get('memory_update') or {}).get('changes') or []:
        t = c.get('text_ja', '')
        for k, v in STATION_JA.items():
            t = t.replace(f'「{k}」', v)
        out.append(f'前回からの変化：{t}')
    return out


SHORT_JA = {'on_site_supply_confirmed': '依頼物資を確認', 'local_vlm_disagree_or_wrong_supply': '依頼物資なし',
            'low_confidence_supply_match': '確信不足', 'visible_hazard_at_checkpoint': '火・煙を検知'}


def timeline(mission: dict) -> str:
    ev = {e.get('stage'): e.get('t_wall_s') for e in mission.get('events', []) if isinstance(e.get('t_wall_s'), (int, float))}
    end = max([t for k, t in ev.items() if k in ('shelter_approach', 'checkpoint_denial_dwell_finished', 'memory_denial')] or [0])
    n = len(checks(mission))
    return f'出発から完了まで {end:.0f} 秒・現地での確認 {n} 回' if end else f'現地での確認 {n} 回'


def build(mission: dict, result: dict) -> dict:
    """Everything the renderer needs, as plain data."""
    o = outcome(mission, result)
    chk = checks(mission)
    head, colour = headline(o)
    expl = ((mission.get('checkpoint') or {}).get('explanation') or {}).get('text_ja')
    return {'run_id': mission.get('run_id'), 'instruction': mission.get('instruction'),
            'interpretation': f"{ITEM_JA.get(o['item'], o['item'])} を 避難所B へ",
            'headline': head, 'colour': colour, 'checks': chk, 'reasons': reasons(chk, o),
            'memory': memory_lines(mission, result), 'next': next_actions(o, mission, result),
            'robot_words': expl, 'robot_words_where': STATION_JA.get(mission.get('checkpoint_station'), ''),
            'timeline': timeline(mission), 'audited': (result or {}).get('state') in (
                'COMPLETED', 'COMPLETED_EXPECTED_DENIAL', 'COMPLETED_MEMORY_TRUSTED', 'DENIED_BY_MEMORY'),
            'outcome': o}
