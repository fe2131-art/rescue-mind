#!/usr/bin/env python3
"""Score captured Jev+Qwen records against locked plan. No mock as proof."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rescuemind.v23_strict_benchmark import evaluate,load_jsonl,ProtocolEvidenceError

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--protocol',type=Path,default=ROOT/'experiments/v23_locked_protocol.json')
    p.add_argument('--captures',type=Path,required=True)
    p.add_argument('--out',type=Path,default=ROOT/'outputs/v23_real_metrics.json')
    p.add_argument('--allow-partial',action='store_true',help='mark as PRELIMINARY; cannot claim full protocol evaluation')
    a=p.parse_args(argv)
    try:
        result=evaluate(json.loads(a.protocol.read_text(encoding='utf-8')),load_jsonl(a.captures),allow_partial=a.allow_partial)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(f'REJECTED: {type(exc).__name__}: {exc}',file=sys.stderr);return 2
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'out':str(a.out),'captured_n':result['coverage']['captured_n'],
                      'complete':result['complete'],'scope':result['scope']},ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
