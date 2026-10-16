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

# v3.4 (I-05): chosen on the domain-randomised dev set v2.  Pass 2 offers an explicit
# "neither" option instead of a hedge ("unclear"), which drew probability away from
# correctly seen first-aid kits; the hazard question names flames/smoke and asks the
# model to look behind objects (a fire behind the kit was missed by the v3.3 wording).
PROMPT_SETS={
 'v33':{'supply':SUPPLY_QUESTIONS,'hazard':HAZARD_QUESTION},
 'v34':{'supply':{
    1:SUPPLY_QUESTIONS[1],
    2:('Which supply is placed on top of the grey platform in this robot camera image?\n'
       'A. neither - the platform top is empty or holds a different object\n'
       'B. a first-aid medical kit\n'
       'C. bottles of drinking water\n'
       'Answer with the letter only.',
       {'A':'other','B':'medicine','C':'water'})},
   'hazard':('Look at the whole image, including behind and around the objects. '
             'Do you see any fire, flames, or smoke? Answer Yes or No.')},
 # v3.5 (I-08): options name both the function and the visible appearance, so the class
 # definition does not depend on how literally a given model reads "kit" vs "box".
 'v35':{'supply':{
    1:('This photo is from a rescue robot camera facing a grey supply platform. '
       'What is placed on top of the platform?\n'
       'A. drinking water (plastic water bottles with caps)\n'
       'B. a first-aid kit (a box marked with a red cross)\n'
       'C. nothing, or some other object\n'
       'Answer with the letter only.',
       {'A':'water','B':'medicine','C':'other'}),
    2:('Which supply is placed on top of the grey platform in this robot camera image?\n'
       'A. neither - the platform top is empty or holds a different object\n'
       'B. a first-aid kit (box with a red cross)\n'
       'C. drinking water (plastic bottles)\n'
       'Answer with the letter only.',
       {'A':'other','B':'medicine','C':'water'})},
   'hazard':('Look at the whole image, including behind and around the objects. '
             'Do you see any fire, flames, or smoke? Answer Yes or No.')},
}


class ModelWorker:
    def __init__(self,model_id: str, max_pixels: int=321126, method: str='scored', prompt_set: str='v33',
                 dtype: str='float16'):
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
        if prompt_set not in PROMPT_SETS:
            raise ValueError('unknown prompt set')
        self.prompt_set=prompt_set
        self.torch=torch
        kwargs={'local_files_only':True}
        if model_id.startswith('Qwen/Qwen2.5-VL'):
            kwargs.update(min_pixels=256*28*28,max_pixels=max_pixels)
        self.processor=AutoProcessor.from_pretrained(model_id,**kwargs)
        if model_id.startswith('Qwen/Qwen2.5-VL'):
            from transformers import Qwen2_5_VLForConditionalGeneration
            cls=Qwen2_5_VLForConditionalGeneration
        else:
            from transformers import AutoModelForImageTextToText
            cls=AutoModelForImageTextToText
        # Qwen3.5 thinks by default; the checkpoint must answer directly.
        self.template_kwargs={'enable_thinking':False} if model_id.startswith('Qwen/Qwen3') else {}
        self.dtype=getattr(torch,dtype)
        load=dict(attn_implementation='eager',local_files_only=True,low_cpu_mem_usage=True)
        import transformers
        key='dtype' if int(transformers.__version__.split('.')[0])>=5 else 'torch_dtype'  # renamed in v5
        self.model=cls.from_pretrained(model_id,**{key:self.dtype},**load).to(self.device).eval()
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
        self.answer_ids={w:ids(w) for w in ('A','B','C','D','Yes','No')}

    def _inputs(self,pic,question):
        messages=[{'role':'user','content':[{'type':'image'},{'type':'text','text':question}]}]
        text=self.processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,
                                                **self.template_kwargs)
        inputs=self.processor(text=[text],images=[pic],return_tensors='pt',padding=True)
        return inputs.to(self.device,dtype=self.dtype)

    def _answer_probs(self,pic,question,choices):
        inputs=self._inputs(pic,question)
        with self.torch.inference_mode():
            logits=self.model(**inputs).logits[0,-1].float()
        if not self.torch.isfinite(logits).all():
            raise RuntimeError('non-finite logits (FP16 overflow?) - refuse to decide')
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

    DESCRIBE_PROMPTS={
     'e0':('この画像は災害支援ロボットのカメラ画像です。灰色の台の上に何が置かれているか、'
           'そして火や煙などの危険が見えるかを、日本語の1文（50文字以内）で事実だけ説明してください。'),
     # I-03: anti-hallucination instruction for empty platforms
     'e1':('この画像は災害支援ロボットのカメラ画像です。灰色の台の上に実際に見えている物だけを、日本語の1文（40文字以内）で答えてください。'
           '台の上に何も無ければ「台の上には何もありません」と答えてください。見えない物を推測しないでください。'
           '火や煙が見える場合は必ずそれも書いてください。'),
     # I-03: vocabulary hint (names the kinds of objects that can appear)
     'e2':('この画像は災害支援ロボットのカメラ画像です。灰色の台の上にある物を、日本語の1文（40文字以内）で答えてください。'
           '例：ペットボトルの水、救急箱、段ボール箱、または何も無い。見えない物を推測しないでください。'
           '火や煙が見える場合は必ずそれも書いてください。'),
    }
    describe_prompt='e0'

    INTENT_PROMPTS={
     'i34':None,   # filled below from the class attributes
     # I-08: concrete "other" and "elsewhere" options (examples deliberately differ from the test set)
     'i35':(('次の依頼文で、ロボットに届けてほしい物資はどれですか。\n依頼文：「{text}」\n'
             'A. 飲料水（水・飲み物）\nB. 医療物資（救急箱・薬・包帯・消毒など）\nC. 飲料水と医療物資の両方\n'
             'D. それ以外（衣類・寝具・燃料・電池などの別の物、物資の依頼ではない、何が必要か書かれていない）\n'
             '記号だけで答えてください。'),
            ('次の依頼文で、物資の届け先はどれですか。\n依頼文：「{text}」\n'
             'A. 避難所B\nB. 避難所B以外の場所（別の避難所や、学校・病院・公共施設などの建物）\nC. 届け先が書かれていない\n'
             '記号だけで答えてください。')),
     # I-08: i35 + a self-consistency check (like the two vision questions): a Yes/No
     # confirmation for each supply, asked in different words.
     'i36':'i35+verify',
     # i37: purpose-based self-check (would receiving the supply serve the requester's purpose?)
     'i37':'i35+purpose',
    }
    INTENT_PURPOSE_Q=('依頼文：「{text}」\nこの依頼をした人は、ロボットから{item}を受け取れば目的を果たせますか。'
                      'Yes か No で答えてください。')
    INTENT_VERIFY_Q=('依頼文：「{text}」\nこの依頼は、ロボットに{item}を運んでほしいという意味ですか。'
                     'Yes か No で答えてください。')
    intent_prompt='i34'
    INTENT_ITEM_Q=('次の依頼文で、届けてほしい物資はどれですか。\n依頼文：「{text}」\n'
                   'A. 飲料水（水・飲み物）\nB. 医療物資（救急箱・薬・包帯など）\nC. 飲料水と医療物資の両方\n'
                   'D. どちらでもない（他の物、物資の依頼ではない、または不明）\n記号だけで答えてください。')
    INTENT_DEST_Q=('次の依頼文で、物資の届け先はどれですか。\n依頼文：「{text}」\n'
                   'A. 避難所B\nB. 避難所B以外の場所\nC. 届け先が書かれていない\n記号だけで答えてください。')

    def _text_probs(self,question,choices):
        messages=[{'role':'user','content':[{'type':'text','text':question}]}]
        prompt=self.processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,
                                                  **self.template_kwargs)
        inputs=self.processor(text=[prompt],return_tensors='pt',padding=True).to(self.device)
        with self.torch.inference_mode():
            logits=self.model(**inputs).logits[0,-1].float()
        scores=self.torch.stack([self.torch.logsumexp(logits[self.answer_ids[c]],0) for c in choices])
        return dict(zip(choices,self.torch.softmax(scores,0).tolist()))

    def intent(self,text):
        """I-04: closed-set parse of a natural-language request (supply + destination)."""
        text=' '.join(str(text).split())[:200].replace('「','').replace('」','')
        key='i35' if self.intent_prompt in ('i36','i37') else self.intent_prompt
        item_q,dest_q=(self.INTENT_ITEM_Q,self.INTENT_DEST_Q) if key=='i34' else self.INTENT_PROMPTS[key]
        item=self._text_probs(item_q.format(text=text),('A','B','C','D'))
        dest=self._text_probs(dest_q.format(text=text),('A','B','C'))
        extra={}
        if self.intent_prompt in ('i36','i37'):
            vq=self.INTENT_VERIFY_Q if self.intent_prompt=='i36' else self.INTENT_PURPOSE_Q
            extra['verify_probs']={k:round(self._text_probs(vq.format(text=text,item=ja),('Yes','No'))['Yes'],4)
                                   for k,ja in (('water','飲み水（飲料水）'),('medicine','救急箱や薬などの医療物資'))}
        return {**extra,'item_probs':{'water':round(item['A'],4),'medicine':round(item['B'],4),'both':round(item['C'],4),
                              'none':round(item['D'],4)},
                'dest_probs':{'B':round(dest['A'],4),'other':round(dest['B'],4),'unstated':round(dest['C'],4)}}

    def describe(self,image_bytes):
        """I-03: short Japanese situation report for people. NEVER used for the allow/deny decision."""
        pic=self._picture(image_bytes)
        inputs=self._inputs(pic,self.DESCRIBE_PROMPTS[self.describe_prompt])
        with self.torch.inference_mode():
            generation=self.model.generate(**inputs,max_new_tokens=56,do_sample=False,use_cache=True)
        offset=inputs['input_ids'].shape[1]
        text=self.processor.batch_decode(generation[:,offset:],skip_special_tokens=True,
                                         clean_up_tokenization_spaces=False)[0]
        return ' '.join(text.split())[:120]

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
        prompts=PROMPT_SETS[self.prompt_set]
        question,mapping=prompts['supply'][pass_id]
        letter_probs=self._answer_probs(pic,question,('A','B','C'))
        supply_probs={mapping[k]:round(v,4) for k,v in letter_probs.items()}
        hazard=self._answer_probs(pic,prompts['hazard'],('Yes','No'))
        supply=max(supply_probs,key=supply_probs.get)
        return {'supply':supply,'scene':'hazard' if hazard['Yes']>=0.5 else 'clear',
                '_scores':{'method':'closed_set_logprob','prompt_set':self.prompt_set,'supply_probs':supply_probs,
                           'hazard_prob':round(hazard['Yes'],4)}}


def make_handler(worker):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path!='/health':
                self.send_error(404);return
            self.reply(200,{'status':'ready','model':worker.model_id,'backend':'local_transformers',
                            'method':getattr(worker,'method','json'),'prompt_set':getattr(worker,'prompt_set',None)})
        def do_POST(self):
            if self.path not in ('/v1/classify','/v1/describe','/v1/intent'):
                self.send_error(404);return
            n=int(self.headers.get('Content-Length','0'))
            if n<20 or n>9_000_000:
                self.send_error(413);return
            try:
                request=json.loads(self.rfile.read(n))
                if type(request) is not dict or request.get('model')!=worker.model_id:
                    raise ValueError('wrong model')
                if self.path=='/v1/intent':
                    text=request.get('text')
                    if not isinstance(text,str) or not text.strip() or len(text)>500:
                        raise ValueError('invalid instruction text')
                    self.reply(200,{'backend':'local_transformers','model':worker.model_id,'real_inference':True,
                                    'text':text,**worker.intent(text)})
                    return
                blob=base64.b64decode(request['image_base64'],validate=True)
                if not (300<=len(blob)<=5_000_000):
                    raise ValueError('image byte size invalid')
                digest=hashlib.sha256(blob).hexdigest()
                if request.get('image_sha256')!=digest:
                    raise ValueError('image hash mismatch')
                if self.path=='/v1/describe':
                    self.reply(200,{'backend':'local_transformers','model':worker.model_id,'real_inference':True,
                                    'image_sha256':digest,'purpose':'explanation_only_not_decision',
                                    'text_ja':worker.describe(blob)})
                    return
                pass_id=request.get('pass_id')
                if type(pass_id) is not int or pass_id not in (1,2):
                    raise ValueError('unsupported pass')
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
    p.add_argument('--dtype',choices=['float16','float32'],default='float16')
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--method',choices=['scored','json'],default='scored')
    p.add_argument('--prompt-set',choices=sorted(PROMPT_SETS),default='v33')
    p.add_argument('--describe-prompt',choices=sorted(ModelWorker.DESCRIBE_PROMPTS),default='e0')
    p.add_argument('--intent-prompt',choices=sorted(ModelWorker.INTENT_PROMPTS),default='i34')
    a=p.parse_args()
    if not 1024<=a.port<=65535: p.error('invalid port')
    worker=ModelWorker(a.model,method=a.method,prompt_set=a.prompt_set,dtype=a.dtype)
    worker.describe_prompt=a.describe_prompt
    worker.intent_prompt=a.intent_prompt
    ThreadingHTTPServer(('127.0.0.1',a.port),make_handler(worker)).serve_forever()

if __name__=='__main__': main()
