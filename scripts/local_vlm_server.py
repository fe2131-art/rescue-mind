#!/usr/bin/env python3
"""Loopback-only Transformers vision worker; weights must be pre-downloaded.

Runs on a V100 in torch.float16 with eager attention (no BF16 / FlashAttention2).

Two decision methods (`--method`):

* ``scored`` (default, v3.3): closed-set **log-probability scoring**.  Each pass
  asks one multiple-choice question about the supply on the platform (option
  letters are permuted between pass 1 and pass 2 to cancel letter-position bias)
  plus a Yes/No hazard question.  One forward pass per question; the next-token
  logits of the answer letters are softmax-normalised into probabilities.  No
  free text is parsed, so there is no "unparseable JSON" failure mode, and every
  decision carries a confidence the mission can threshold.
* ``json`` (v3.2 handoff baseline): free-form generation of a JSON object.  On real
  Gazebo frames this pass-2 prompt answered "other" for every image and pass 1
  hallucinated water on an empty platform; kept only for the ablation study.
"""
import argparse
import base64
import hashlib
import io
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.local_vision import ALLOWED_MODELS, parse_model_json

# ---- v3.2 baseline (free-form JSON generation) -------------------------------
PROMPTS={
 1:'Identify only the object visibly PRESENT at this emergency supply station. Do not infer from shelf text/color or instructions. Give exactly JSON {"supply":"water|medicine|other","scene":"clear|hazard|unknown"}. water=sealed drinking bottles, medicine=first aid kit, other=missing/uncertain. scene=hazard only if visible smoke/fire/debris/blockage; unknown if corridor cannot be assessed. No prose.',
 2:'Independently re-check this photo. Is a clear identifiable bottle of drinking water, first-aid medicine kit, or neither visible? Never guess from background. Return JSON ONLY with exactly keys "supply" (water, medicine, other) and "scene" (clear, hazard, unknown). If unsure use other and unknown; visible danger means hazard.'
}

# ---- v3.3 closed-set scoring --------------------------------------------------
# The option ORDER differs between passes so a letter-position bias cannot make
# both passes agree on the same wrong label.
SUPPLY_QUESTIONS={
 1:('This photo is from a rescue robot camera facing a grey supply platform. '
    'What is placed on top of the platform?\n'
    'A. sealed bottles of drinking water\n'
    'B. a first-aid medical kit\n'
    'C. nothing (the platform is empty) or something else\n'
    'Answer with the letter only.',
    {'A':'water','B':'medicine','C':'other'}),
 2:('Look carefully at the top of the grey platform in this robot camera image. '
    'Which option describes what is actually there?\n'
    'A. nothing - the platform top is empty, or the object is unclear\n'
    'B. a medical first-aid box\n'
    'C. bottles of drinking water\n'
    'Answer with the letter only.',
    {'A':'other','B':'medicine','C':'water'}),
}
HAZARD_QUESTION=('Is there any visible fire, smoke, flooding, or fallen debris in this image? '
                 'Answer Yes or No.')


class ModelWorker:
    def __init__(self,model_id: str, max_pixels: int=321126, method: str='scored'):
        if model_id not in ALLOWED_MODELS:
            raise ValueError('model not on local allowlist')
        if method not in ('scored','json'):
            raise ValueError('method must be scored or json')
        import torch
        from transformers import AutoProcessor
        if not torch.cuda.is_available():
            raise RuntimeError('CUDA GPU required: no CPU fallback in robot live mode')
        if torch.cuda.get_device_capability(0)[0] < 7:
            raise RuntimeError('V100 or newer required for this FP16 preset')
        self.device='cuda:0'
        self.model_id=model_id
        self.method=method
        self.torch=torch
        kwargs={'local_files_only':True}
        if model_id.startswith('Qwen/'):
            kwargs.update(min_pixels=256*28*28,max_pixels=max_pixels)
        self.processor=AutoProcessor.from_pretrained(model_id,**kwargs)
        if model_id.startswith('Qwen/'):
            from transformers import Qwen2_5_VLForConditionalGeneration
            cls=Qwen2_5_VLForConditionalGeneration
        else:
            from transformers import AutoModelForImageTextToText
            cls=AutoModelForImageTextToText
        self.model=cls.from_pretrained(model_id,torch_dtype=torch.float16,
                                      attn_implementation='eager',local_files_only=True,
                                      low_cpu_mem_usage=True).to(self.device).eval()
        tok=self.processor.tokenizer
        def ids(word):
            out=set()
            for variant in (word,' '+word):
                enc=tok.encode(variant,add_special_tokens=False)
                if len(enc)==1:
                    out.add(enc[0])
            if not out:
                raise RuntimeError('answer token not single-token: '+word)
            return sorted(out)
        self.answer_ids={w:ids(w) for w in ('A','B','C','Yes','No')}

    def _inputs(self,pic,question):
        messages=[{'role':'user','content':[{'type':'image'},{'type':'text','text':question}]}]
        text=self.processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
        inputs=self.processor(text=[text],images=[pic],return_tensors='pt',padding=True)
        return inputs.to(self.device,dtype=self.torch.float16)

    def _answer_probs(self,pic,question,choices):
        inputs=self._inputs(pic,question)
        with self.torch.inference_mode():
            logits=self.model(**inputs).logits[0,-1].float()
        # log-sum-exp over the tokenizer's variants of each answer ("A" / " A")
        scores=self.torch.stack([self.torch.logsumexp(logits[self.answer_ids[c]],0) for c in choices])
        probs=self.torch.softmax(scores,0).tolist()
        return dict(zip(choices,probs))

    @staticmethod
    def _picture(image_bytes):
        from PIL import Image, ImageOps
        with Image.open(io.BytesIO(image_bytes)) as im:
            pic=ImageOps.exif_transpose(im).convert('RGB')
            pic.thumbnail((640,640))
        return pic

    def classify(self,image_bytes,pass_id):
        pic=self._picture(image_bytes)
        if self.method=='json':
            inputs=self._inputs(pic,PROMPTS[pass_id])
            with self.torch.inference_mode():
                generation=self.model.generate(**inputs,max_new_tokens=96,do_sample=False,use_cache=True)
            offset=inputs['input_ids'].shape[1]
            raw=self.processor.batch_decode(generation[:,offset:],skip_special_tokens=True,
                                            clean_up_tokenization_spaces=False)[0]
            return parse_model_json(raw)
        question,mapping=SUPPLY_QUESTIONS[pass_id]
        letter_probs=self._answer_probs(pic,question,('A','B','C'))
        supply_probs={mapping[k]:round(v,4) for k,v in letter_probs.items()}
        hazard=self._answer_probs(pic,HAZARD_QUESTION,('Yes','No'))
        supply=max(supply_probs,key=supply_probs.get)
        return {'supply':supply,'scene':'hazard' if hazard['Yes']>=0.5 else 'clear',
                '_scores':{'method':'closed_set_logprob','supply_probs':supply_probs,
                           'hazard_prob':round(hazard['Yes'],4)}}


def make_handler(worker):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path!='/health':
                self.send_error(404);return
            self.reply(200,{'status':'ready','model':worker.model_id,'backend':'local_transformers',
                            'method':getattr(worker,'method','json')})
        def do_POST(self):
            if self.path!='/v1/classify':
                self.send_error(404);return
            n=int(self.headers.get('Content-Length','0'))
            if n<100 or n>9_000_000:
                self.send_error(413);return
            try:
                request=json.loads(self.rfile.read(n))
                if type(request) is not dict or request.get('model')!=worker.model_id:
                    raise ValueError('wrong model')
                pass_id=request.get('pass_id')
                if type(pass_id) is not int or pass_id not in (1,2):
                    raise ValueError('unsupported pass')
                blob=base64.b64decode(request['image_base64'],validate=True)
                if not (300<=len(blob)<=5_000_000):
                    raise ValueError('image byte size invalid')
                digest=hashlib.sha256(blob).hexdigest()
                if request.get('image_sha256')!=digest:
                    raise ValueError('image hash mismatch')
                result=dict(worker.classify(blob,pass_id))
                scores=result.pop('_scores',None)
                body={'backend':'local_transformers','model':worker.model_id,
                      'real_inference':True,'image_sha256':digest,
                      'pass_id':pass_id,'result':result}
                if scores is not None:
                    body['scores']=scores
                self.reply(200,body)
            except Exception as e:
                self.reply(422,{'error':type(e).__name__+': '+str(e)[:240]})
        def reply(self,code,obj):
            b=json.dumps(obj,ensure_ascii=False).encode('utf8')
            self.send_response(code);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        def log_message(self,fmt,*args):
            sys.stderr.write('local-vlm: '+fmt%args+'\n')
    return Handler


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',choices=sorted(ALLOWED_MODELS),default='Qwen/Qwen2.5-VL-3B-Instruct')
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--method',choices=['scored','json'],default='scored')
    a=p.parse_args()
    if not 1024<=a.port<=65535: p.error('invalid port')
    worker=ModelWorker(a.model,method=a.method)
    ThreadingHTTPServer(('127.0.0.1',a.port),make_handler(worker)).serve_forever()

if __name__=='__main__': main()
