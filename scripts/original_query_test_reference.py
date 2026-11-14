"""Compare original test queries after selection using real vectors and live pgvector."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
import os
from src.benchmark import load_inputs
from src.day6.embeddings import embedding_input, MyEmbedder
from src.day6.store import PgVectorStore
from src.retrieval import BM25Retriever, pack_context, reciprocal_rank_fusion
from src.retrieval_benchmark import evidence_hit


def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def main():
    load_dotenv(ROOT / '.env', encoding='utf-8-sig')
    inherited = load('configs/day6/inherited.json')
    lock = load('results/experiments/selection.json')
    assert lock['status'] == 'locked'
    for name, digest in {**lock['code_sha256'], **lock['benchmark_sha256']}.items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest
    config_paths = {'baseline': lock['baseline_config'], 'focused': lock['selected_config']}
    for path in config_paths.values():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() in lock['allowed_test_config_sha256']
    embedder = MyEmbedder(inherited['model'], inherited['dimensions'], ROOT / 'results/embedding_cache')
    output = ROOT / 'results/experiments/original-query-test-reference.json'
    if output.exists():
        raise ValueError('Preserve existing test reference')
    configs = {name: load(path) for name, path in config_paths.items()}
    chunks = load('data/chunks.json')
    lexical = BM25Retriever(chunks, **configs['baseline']['bm25'])
    store = PgVectorStore(os.getenv('DATABASE_URL', ''), inherited['dimensions'], inherited['namespace'])
    traces = []
    try:
        for case in load_inputs('test'):
            key = hashlib.sha256(f"{inherited['model']}:{inherited['dimensions']}:nfc-ws-v1:{embedding_input(case['question'])}".encode()).hexdigest()
            vector = embedder.embed_query(case['question'])
            dense_raw = store.search('C', vector, max(c['candidate_k'] for c in configs.values()), case.get('filter'))
            dense = [dict(id=h['chunk_id'], source_id=h['document_id'], text=h['text'], source=h['source'],
                          page=h['page'], metadata=h['metadata'], score=h['score']) for h in dense_raw]
            bm25 = lexical.search(case['question'], filters=case.get('filter'), top_k=max(c['candidate_k'] for c in configs.values()))
            for name, cfg in configs.items():
                results = reciprocal_rank_fusion({'dense': dense[:cfg['candidate_k']], 'bm25': bm25[:cfg['candidate_k']]},
                            top_k=cfg['top_k'], **cfg['rrf'])
                context, ids = pack_context(results, budget=cfg['context_budget_chars'])
                traces.append({'query_id': case['id'], 'config': name, 'query_original': case['question'],
                    'filter': case.get('filter'), 'results': results, 'context': context, 'context_ids': ids})
    finally:
        store.close()
    # Labels enter only this evaluator, after all ranking/context computation.
    labels = {q['id']: q for q in load('benchmark/test.json') if q['answerable']}
    metrics = {}
    for name in configs:
        rows = [t for t in traces if t['config'] == name and t['query_id'] in labels]
        values = {'hit1': 0, 'hit3': 0, 'context_evidence': 0}
        for row in rows:
            gold = labels[row['query_id']]['gold']
            hits = [evidence_hit(h, gold) for h in row['results']]
            values['hit1'] += bool(hits and hits[0])
            values['hit3'] += any(hits[:3])
            values['context_evidence'] += any(hit and h['id'] in row['context_ids'] for hit,h in zip(hits,row['results']))
        metrics[name] = {k: {'n': n, 'N': len(rows), 'rate': n/len(rows)} for k,n in values.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError('Reference already exists; preserve prior artifacts')
    output.write_text(json.dumps({'split': 'test', 'selection_locked_at': lock['locked_at'], 'query_policy': 'Original questions, fixed user filter; no model rewriting',
        'api_calls': len(embedder.requests), 'embedding_tokens': embedder.api_tokens, 'embedding_requests': embedder.requests, 'embedding_cache_hits': embedder.cache_hits, 'embedding_estimated_usd': embedder.api_tokens * float(os.getenv('EMBEDDING_USD_PER_MILLION', '0.02')) / 1e6, 'source': 'Live pgvector plus real query embeddings shared across both fixed configurations',
        'config_sha256': {k: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for k,p in config_paths.items()},
        'metrics': metrics, 'traces': traces}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(metrics, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
