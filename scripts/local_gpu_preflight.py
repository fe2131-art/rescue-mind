#!/usr/bin/env python3
"""Non-secret local GPU / CUDA / cached-model preflight. No model download."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def probe(mode='single'):
    from rescuemind.local_vision import PRIMARY_MODEL, SECONDARY_MODEL
    result={'mode':mode,'gpu_required':'NVIDIA Tesla V100 32GB',
            'precision':'float16','attention':'eager','cloud_credentials_required':False,
            'ready':False,'checks':[]}
    def check(name,ok,note):
        result['checks'].append({'name':name,'ok':bool(ok),'note':str(note)[:230]})
    try:
        import torch
        gpu=torch.cuda.is_available()
        check('cuda',gpu,'PyTorch '+torch.__version__)
        if gpu:
            cap=torch.cuda.get_device_capability(0)
            name=torch.cuda.get_device_name(0)
            mem=torch.cuda.get_device_properties(0).total_memory/(1024**3)
            check('cuda_capability',cap[0]>=7,'GPU '+name+' compute capability '+str(cap))
            check('gpu_vram',mem>=12, 'visible total VRAM GiB %.1f; model memory measured later'%mem)
        else:
            check('cuda_capability',False,'GPU inaccessible; no live inferencing')
    except (ImportError,RuntimeError,OSError) as e:
        check('cuda',False,str(e))
    try:
        import transformers
        check('transformers',True,transformers.__version__)
    except ImportError as e:
        check('transformers',False,str(e))
    try:
        from huggingface_hub import snapshot_download
        for model in ([PRIMARY_MODEL] + ([SECONDARY_MODEL] if mode=='dual' else [])):
            try:
                folder=snapshot_download(model,local_files_only=True)
                check('model_cache_'+model,True,folder)
            except (OSError,ValueError) as e:
                check('model_cache_'+model,False,'not fully cached: '+str(e)[:130])
    except ImportError as e:
        check('huggingface_hub',False,str(e))
    result['ready']=all(c['ok'] for c in result['checks'])
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['single','dual'],default='single');a=p.parse_args()
    report=probe(a.mode)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    sys.exit(0 if report['ready'] else 2)
