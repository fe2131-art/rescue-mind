#!/usr/bin/env python3
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.stack_contract import check
x=check(ROOT)
out=ROOT/'verification/v17/stack_contract.json';out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(x,ensure_ascii=False,indent=2))
raise SystemExit(0 if x['ok'] else 3)
