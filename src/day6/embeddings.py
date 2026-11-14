import hashlib, json, math, os, unicodedata
from pathlib import Path

def embedding_input(text):
    return ' '.join(unicodedata.normalize('NFC',text).split())

class MyEmbedder:
    def __init__(self, model_name='text-embedding-3-small', dimensions=1536, cache_dir=Path('results/embedding_cache')):
        from openai import OpenAI
        import tiktoken
        if not os.getenv('OPENAI_API_KEY'): raise ValueError('OPENAI_API_KEY missing; configure the LAB07 root .env locally')
        if model_name not in ('text-embedding-3-small','text-embedding-3-large'): raise ValueError('Unsupported model')
        if not 1 <= dimensions <= (1536 if model_name.endswith('small') else 3072): raise ValueError('Invalid dimensions')
        self.model_name,self.dimensions = model_name,dimensions
        self.client = OpenAI(timeout=60,max_retries=2)
        self.encoding = tiktoken.encoding_for_model(model_name)
        self.cache_dir=Path(cache_dir); self.cache_dir.mkdir(parents=True,exist_ok=True)
        self.api_tokens=0; self.cache_hits=0; self.requests=[]

    def validate(self,v):
        if len(v)!=self.dimensions or not all(math.isfinite(x) for x in v) or not any(v): raise ValueError('Invalid embedding vector')
        return v

    def embed_documents(self,texts):
        inputs=[embedding_input(t) for t in texts]
        if any(not t or len(self.encoding.encode(t))>8191 for t in inputs): raise ValueError('Empty or oversized input')
        keys=[hashlib.sha256(f'{self.model_name}:{self.dimensions}:nfc-ws-v1:{t}'.encode()).hexdigest() for t in inputs]
        found,missing={},{}
        for key,text in zip(keys,inputs):
            file=self.cache_dir/f'{key}.json'
            if key in found: self.cache_hits+=1
            elif file.exists():
                found[key]=self.validate(json.loads(file.read_text())['vector']); self.cache_hits+=1
            else: missing[key]=text
        entries=list(missing.items())
        for offset in range(0,len(entries),32):
            batch=entries[offset:offset+32]
            response=self.client.embeddings.create(model=self.model_name,dimensions=self.dimensions,input=[t for _,t in batch])
            data=sorted(response.data,key=lambda x:x.index)
            if [d.index for d in data]!=list(range(len(batch))): raise ValueError('Embedding count/index mismatch')
            self.api_tokens+=response.usage.total_tokens
            self.requests.append({'request_id':response._request_id,'model':response.model,'tokens':response.usage.total_tokens})
            for (key,_),item in zip(batch,data):
                found[key]=self.validate(item.embedding)
                target=self.cache_dir/f'{key}.json'; temp=target.with_suffix('.tmp')
                temp.write_text(json.dumps({'vector':found[key]})); temp.replace(target)
        return [found[k] for k in keys]

    def embed_query(self,question): return self.embed_documents([question])[0]
