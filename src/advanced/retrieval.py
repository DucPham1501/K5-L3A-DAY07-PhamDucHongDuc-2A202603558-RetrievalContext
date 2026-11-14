"""Persistent local exact-vector index + BM25/RRF; uses real cached embeddings."""
import math
from .common import ROOT, DATA, read, write, sha
from src.day6.embeddings import MyEmbedder
from src.retrieval import BM25Retriever, reciprocal_rank_fusion


def embedding_text(text):
    # The report prints ChatML markers as examples. Encode them as ordinary text,
    # rather than tokenizer control tokens. Raw source/evidence remains unchanged.
    return text.replace('<|', '< |').replace('|>', '| >')


class Retriever:
    def __init__(self, config):
        self.cfg = config
        self.rows = read(DATA/'index.json')
        self.lexical = BM25Retriever(self.rows)
        self.embedder = MyEmbedder(config['embedding_model'], config['dimensions'], ROOT/'results/embedding_cache')
        saved = read(DATA/'vectors.json')
        if (saved['index_sha256'],saved['model'],saved['dimensions']) != (sha(DATA/'index.json'), config['embedding_model'], config['dimensions']):
            raise ValueError('Vector index is incompatible with current source/model')
        self.vectors = saved['vectors']
        if set(self.vectors) != {r['id'] for r in self.rows}:
            raise ValueError('Vector/index IDs differ')
        for v in self.vectors.values():
            self.embedder.validate(v)

    def search(self, query):
        vector = self.embedder.embed_query(embedding_text(query))
        norm = math.sqrt(sum(x*x for x in vector))
        dense = []
        for row in self.rows:
            v = self.vectors[row['id']]
            score = sum(a*b for a,b in zip(vector,v))/(norm*math.sqrt(sum(x*x for x in v)))
            dense.append({**row,'score':score})
        dense.sort(key=lambda x:(-x['score'],x['id']))
        k=self.cfg['candidate_k']
        lexical=self.lexical.search(query,top_k=k)
        results=reciprocal_rank_fusion({'dense':dense[:k],'bm25':lexical},top_k=self.cfg['top_k'],rank_constant=self.cfg['rank_constant'])
        # Shared RRF returns the basic chunk schema. Restore the original visual
        # assets by ID so ranked text and the page image cannot become misaligned.
        originals={r['id']:r for r in self.rows}
        results=[{**originals[r['id']],**r} for r in results]
        return {'query':query,'results':results,'branch_ids':{'dense':[r['id'] for r in dense[:k]],'bm25':[r['id'] for r in lexical]}}

    def close(self):
        self.embedder.client.close()


def build_vectors():
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env',encoding='utf-8-sig')
    cfg=read(ROOT/'configs/advanced/base.json')
    rows=read(DATA/'index.json')
    target=DATA/'vectors.json'
    if target.exists():
        raise ValueError('Preserve existing vector index; rebuild only into a new version')
    embedder=MyEmbedder(cfg['embedding_model'],cfg['dimensions'],ROOT/'results/embedding_cache')
    try:
        vectors=embedder.embed_documents([embedding_text(r['text']) for r in rows])
        write(target,{'index_sha256':sha(DATA/'index.json'),'model':cfg['embedding_model'],
            'dimensions':cfg['dimensions'],'metric':'exact cosine','input_processing':'Escape printed ChatML delimiters, then NFC + collapsed whitespace for query and document',
            'store':'Local persistent JSON vector store, separate from Day 6 pgvector',
            'vectors':{r['id']:v for r,v in zip(rows,vectors)}})
        write(ROOT/'results/advanced/embedding-build.json',{'index_sha256':sha(DATA/'index.json'),
            'vectors_sha256':sha(target),'pages':len(rows),'model':cfg['embedding_model'],'dimensions':cfg['dimensions'],
            'api_tokens':embedder.api_tokens,'cache_hits':embedder.cache_hits,'requests':embedder.requests,
            'estimated_usd':embedder.api_tokens*cfg['pricing_usd_per_million']['embedding']/1e6})
    finally:
        embedder.client.close()


if __name__=='__main__':
    build_vectors()
