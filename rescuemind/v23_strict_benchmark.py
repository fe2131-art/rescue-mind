"""Strict case-level benchmark on saved API records against preregistered scene truth.

Key limitations: live_api_capture/real_model fields are self-reported; no digital
attestation. The user must manually inspect images and independently verify
service requests. Cases from repeated scenes are correlated: Wilson intervals
are descriptive only; report not as independent experimental replications.
"""
from __future__ import annotations
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any
from .v23_protocol import validate_protocol
from .benchmark_vision import validate_record, aggregate
from .paired_benchmark import analyze
from .experiment_stats import validate_unique, wilson_interval
from .safety import decide

class ProtocolEvidenceError(ValueError):pass


def load_jsonl(path:Path)->list[dict]:
    rows=[]
    for index,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        if not line.strip():continue
        try: row=json.loads(line)
        except json.JSONDecodeError as exc:raise ProtocolEvidenceError(f'invalid JSON at line {index}') from exc
        if not isinstance(row,dict):raise ProtocolEvidenceError(f'non-object at line {index}')
        rows.append(row)
    return rows


def validate_cases(protocol:dict,records:list[dict],*,allow_partial:bool=False)->dict:
    validate_protocol(protocol)
    by_id={t['id']:t for t in protocol['trials']}
    seen=set()
    if not records:raise ProtocolEvidenceError('no real captures supplied; metrics unavailable')
    for row in records:
        case_id=row.get('id')
        if type(case_id)!=str or case_id not in by_id or case_id in seen:
            raise ProtocolEvidenceError(f'unknown/duplicate case ID {case_id!r}')
        seen.add(case_id); t=by_id[case_id]
        if row.get('expected')!=t['expected'] or row.get('truth')!={'supply':t['truth_supply'],'scene':t['truth_scene']}:
            raise ProtocolEvidenceError(f'ground truth or mission changed for {case_id}')
        if row.get('provenance')!='live_api_capture':raise ProtocolEvidenceError('not captured via live API workflow')
        validate_record(row,require_real=True)
        hashes=row.get('image_sha256')
        if not isinstance(hashes,dict) or any(type(hashes.get(k))!=str or len(hashes[k])!=64 or any(ch not in '0123456789abcdef' for ch in hashes[k]) for k in ('supply','corridor')):
            raise ProtocolEvidenceError('missing/malformed SHA256 for physical image evidence')
        if hashes['supply']==hashes['corridor']:raise ProtocolEvidenceError('reused identical supply/corridor images')
        if row.get('wall_sec') is None or type(row['wall_sec']) not in (int,float) or not 0<=row['wall_sec']<=1000:
            raise ProtocolEvidenceError('missing/invalid inference latency')
        # Pinned model versions enforce fixed conditions rather than mix-and-match releases.
        for loc in ('supply','corridor'):
            if row[loc]['jev'].get('model')!='jev-1.14.0':
                raise ProtocolEvidenceError('Jev model not pinned at 1.14.0')
            if row[loc]['qwen'].get('model')!='qwen3.8-omni-flash':
                raise ProtocolEvidenceError('Qwen model not pinned at 3.8-omni-flash')
    try:validate_unique(records)
    except ValueError as exc:raise ProtocolEvidenceError(str(exc)) from exc
    missing=sorted(set(by_id)-seen)
    if missing and not allow_partial:
        raise ProtocolEvidenceError(f'incomplete study: {len(missing)} of {len(by_id)} trials missing; use --allow-partial for explicitly preliminary report')
    counts=Counter((by_id[r['id']]['scene'],by_id[r['id']]['expected']) for r in records)
    return {'planned_n':len(by_id),'captured_n':len(records),'missing_ids':missing,
            'condition_counts':{f'{scene}:{item}':counts[(scene,item)] for scene in ('nominal','swapped','empty') for item in ('water','medicine')},
            'complete':not missing}


def evaluate(protocol:dict,records:list[dict],*,allow_partial:bool=False)->dict:
    coverage=validate_cases(protocol,records,allow_partial=allow_partial)
    summary=aggregate(records,require_real=True)
    # Paired significance requires unsafe examples. Clearly label inference limitations.
    paired=analyze(records) if any(r['truth']['supply']!=r['expected'] or r['truth']['scene']!='clear' for r in records) else None
    # Per-condition data: success means correctly approved when safe, correctly denied otherwise.
    per_condition={}
    for scene in ('nominal','swapped','empty'):
        sub=[r for r in records if next(t['scene'] for t in protocol['trials'] if t['id']==r['id'])==scene]
        if not sub:continue
        safe=(scene=='nominal')
        counts={'jev_only':0,'qwen_only':0,'fusion':0}
        for r in sub:
            exp=r['expected']
            j={**r['supply']['jev'], 'scene':r['corridor']['jev']['scene'], 'hazard_probability':r['corridor']['jev']['hazard_probability']}
            q={**r['supply']['qwen'], 'scene':r['corridor']['qwen']['scene']}
            jallow=(j.get('supply')==exp and j.get('scene')=='clear' and j.get('supply_present_probability',0)>=.8 and j.get('supply_confidence',0)>=.65 and j.get('hazard_probability',1)<=.20)
            qallow=(q.get('supply')==exp and q.get('scene')=='clear')
            fal=decide(exp,j,q).allow
            for method,al in (('jev_only',jallow),('qwen_only',qallow),('fusion',fal)):
                counts[method]+=int(bool(al)==safe)
        per_condition[scene]={method:{'correct':v,'n':len(sub),'rate':round(v/len(sub),4),
                                              'wilson95_descriptive':wilson_interval(v,len(sub))} for method,v in counts.items()}
    result={'schema':'rescuemind_v23_strict_report_v1','scope':'SAVED_LIVE_API_RECORDS_SELF_ASSERTED_NOT_AUTHENTICATED',
            'complete':coverage['complete'],'report_status':'FINAL_CAPTURE_SET' if coverage['complete'] else 'PRELIMINARY_INCOMPLETE',
            'coverage':coverage,'metrics':summary,'paired_unsafe_comparison':paired,
            'by_scene':per_condition,
            'limitations':['No actual Gazebo/model attestation from JSONL metadata alone.',
                           'Ground truth from SDF must be verified against camera pixels before academic claim.',
                           'Repeated shots in the same Gazebo scene are correlated; Wilson intervals are descriptive, not trial-independent CIs.',
                           'False-denial and unsafe-approval tradeoff both required; superiority never assumed.',
                           'No result is a guarantee of physical safety or robot motion.']}
    return result
