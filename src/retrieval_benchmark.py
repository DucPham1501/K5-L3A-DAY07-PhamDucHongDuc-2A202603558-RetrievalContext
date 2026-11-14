"""Run dev retrieval first; score saved results separately. Test is held out."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import statistics
import time

from .benchmark import load_inputs
from .retrieval import BM25Retriever, pack_context, reciprocal_rank_fusion

ROOT = Path(__file__).resolve().parents[1]
METHODS = ('dense', 'bm25', 'hybrid_rrf')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def run(output):
    from .day6.retrieval import DenseRetriever
    from .day6.embeddings import embedding_input
    config = load(ROOT / 'configs/retrieval.json')
    if config['split'] != 'dev' or tuple(config['methods']) != METHODS:
        raise ValueError('This stage only runs the three declared methods on dev')
    if not 3 <= config['top_k'] <= config['candidate_k'] <= 100:
        raise ValueError('Expected 3 <= top_k <= candidate_k <= 100')
    if type(config['context_budget_chars']) is not int or config['context_budget_chars'] < 1:
        raise ValueError('Invalid context budget')
    manifest = load(ROOT / 'benchmark/manifest.json')
    paths = ('data/processed/corpus.pages.jsonl', 'data/chunks.json', 'benchmark/dev.json', 'benchmark/inputs/dev.json')
    # Hash the selected split's labels without reading/interpreting them in retrieval.
    for relative in paths:
        if sha(ROOT / relative) != manifest['sha256'][relative]:
            raise ValueError(f'Frozen asset changed: {relative}')
    inputs = load_inputs('dev')
    chunks = load(ROOT / config['chunk_file'])
    # Reject existing output instead of destroying a prior experiment.
    output.mkdir(parents=True, exist_ok=False)
    record = {'status': 'running', 'started_at': now(), 'split': 'dev', 'config': config,
              'asset_sha256': {p: sha(ROOT / p) for p in paths},
              'code_sha256': {p: sha(ROOT / p) for p in ('src/retrieval.py', 'src/retrieval_benchmark.py',
                  'src/day6/retrieval.py', 'src/day6/embeddings.py', 'src/day6/store.py', 'configs/retrieval.json')},
              'query_count': len(inputs), 'chunk_count': len(chunks), 'test_run': False,
              'versions': {p: importlib.metadata.version(p) for p in ('openai', 'psycopg', 'tiktoken')},
              'timing_policy': 'One shared measured embedding/dense/BM25 stage per query. Composed latency is a sum of reused measured stages, not independently timed standalone calls.',
              'cost_policy': 'Actual embedding API usage counted once per run. Per-method logical tokens show standalone demand; do not add shared billed cost twice. USD uses configured estimate, not invoice/current verified pricing.'}
    write(output / 'run.json', record)
    dense = None
    failures = 0
    try:
        started = time.perf_counter()
        dense = DenseRetriever()
        dense.verify_snapshot(chunks)
        record['dense_setup_seconds'] = time.perf_counter() - started
        record['store'] = dense.store.versions()
        record['model'] = dense.embedder.model_name
        record['dimensions'] = dense.embedder.dimensions
        record['namespace'] = dense.store.namespace
        started = time.perf_counter()
        bm25 = BM25Retriever(chunks, **config['bm25'])
        record['bm25_build_seconds'] = time.perf_counter() - started
        raw_rate = os.getenv('EMBEDDING_USD_PER_MILLION', '').strip()
        rate = float(raw_rate) if raw_rate else None
        if rate is not None and (not math.isfinite(rate) or rate < 0):
            raise ValueError('Invalid configured cost rate')
        record['configured_usd_per_million_tokens'] = rate
        write(output / 'run.json', record)
        with (output / 'traces.jsonl').open('x', encoding='utf-8') as stream:
            for case in inputs:
                question, filters = case['question'], case.get('filter')
                # These are the ONLY fields sent to retrieval/model.
                shared = {'query_id': case['id'], 'filter': filters, 'filter_origin': 'explicit benchmark user input',
                          'input_tokens': len(dense.embedder.encoding.encode(embedding_input(question)))}
                started = time.perf_counter()
                lexical = bm25.search(question, filters=filters, top_k=config['candidate_k'])
                shared['bm25_ms'] = (time.perf_counter() - started) * 1000
                before_tokens, before_cache = dense.embedder.api_tokens, dense.embedder.cache_hits
                before_requests = len(dense.embedder.requests)
                dense_hits, error_type = [], None
                started = time.perf_counter()
                try:
                    vector = dense.embedder.embed_query(question)
                except Exception as exc:
                    error_type = type(exc).__name__
                    shared['error_stage'] = 'query_embedding'
                shared['embedding_ms'] = (time.perf_counter() - started) * 1000
                shared['api_tokens'] = dense.embedder.api_tokens - before_tokens
                shared['cache_hits'] = dense.embedder.cache_hits - before_cache
                shared['requests'] = dense.embedder.requests[before_requests:]
                shared['actual_estimated_api_cost_usd'] = shared['api_tokens'] * rate / 1e6 if rate is not None else None
                started = time.perf_counter()
                if error_type is None:
                    try:
                        dense_hits = dense.search_vector(vector, filters=filters, top_k=config['candidate_k'])
                    except Exception as exc:
                        error_type = type(exc).__name__
                        shared['error_stage'] = 'vector_store_search'
                shared['dense_ms'] = (time.perf_counter() - started) * 1000
                if error_type:
                    failures += 1
                started = time.perf_counter()
                fused = reciprocal_rank_fusion({'dense': dense_hits, 'bm25': lexical},
                    top_k=config['top_k'], **config['rrf']) if error_type is None else []
                shared['fusion_ms'] = (time.perf_counter() - started) * 1000
                per_method = {'dense': dense_hits[:config['top_k']], 'bm25': lexical[:config['top_k']], 'hybrid_rrf': fused}
                for method in METHODS:
                    error = error_type if method != 'bm25' else None
                    results = per_method[method]
                    started = time.perf_counter()
                    context, context_ids = pack_context(results, budget=config['context_budget_chars'])
                    context_ms = (time.perf_counter() - started) * 1000
                    composed_ms = context_ms + (shared['bm25_ms'] if method in ('bm25', 'hybrid_rrf') else 0)
                    if method != 'bm25':
                        composed_ms += shared['embedding_ms'] + shared['dense_ms']
                    if method == 'hybrid_rrf':
                        composed_ms += shared['fusion_ms']
                    trace = {'query_id': case['id'], 'split': 'dev', 'question': question, 'query_original': question,
                             'method': method, 'status': 'error' if error else 'ok', 'error_type': error,
                             'filter': filters, 'top_k': config['top_k'], 'candidate_k': config['candidate_k'],
                             'results': results, 'context': context, 'context_ids': context_ids,
                             'context_chars': len(context), 'context_budget_chars': config['context_budget_chars'],
                             'context_embedding_tokenizer_tokens': len(dense.embedder.encoding.encode(context)),
                             'composed_latency_ms': composed_ms, 'context_pack_ms': context_ms,
                             'shared_stage_id': case['id'], 'shared_stages': shared,
                             'logical_embedding_tokens': shared['input_tokens'] if method != 'bm25' else 0,
                             'logical_estimated_embedding_cost_usd': (shared['input_tokens'] * rate / 1e6 if rate is not None else None) if method != 'bm25' else 0,
                             'branches': {'dense': dense_hits, 'bm25': lexical} if method == 'hybrid_rrf' else {method: dense_hits if method == 'dense' else lexical}}
                    stream.write(json.dumps(trace, ensure_ascii=False) + '\n')
                    stream.flush()
                print(f"{case['id']}: {'error ' + error_type if error_type else 'retrieved'}", flush=True)
        record['status'] = 'complete_with_errors' if failures else 'complete'
        record['query_errors'] = failures
        record['finished_at'] = now()
    except Exception as exc:
        record['status'] = 'failed'
        record['error_type'] = type(exc).__name__
        raise
    finally:
        if dense:
            record['actual_api_usage'] = {'tokens': dense.embedder.api_tokens, 'cache_hits': dense.embedder.cache_hits,
                                          'requests': dense.embedder.requests}
            rate = record.get('configured_usd_per_million_tokens')
            record['actual_estimated_embedding_cost_usd'] = dense.embedder.api_tokens * rate / 1e6 if rate is not None else None
            dense.close()
        write(output / 'run.json', record)
    if failures:
        raise RuntimeError('Retrieval errors recorded; inspect error types, do not replace with mock')


def evidence_hit(row, gold):
    return any(row['source_id'] == g['source_id'] and row['page'] == g['page']
               and g['evidence'] in row['text'] for g in gold)


def ratio(n, total):
    return {'n': n, 'N': total, 'rate': n / total if total else None}


def score(output):
    """Evaluator-only: gold is opened only AFTER the retrieval run has finished."""
    record = load(output / 'run.json')
    if record['split'] != 'dev' or record['status'] not in ('complete', 'complete_with_errors'):
        raise ValueError('Score a completed dev run only')
    for relative, checksum in record['asset_sha256'].items():
        if sha(ROOT / relative) != checksum:
            raise ValueError('Assets changed since retrieval')
    labels = {q['id']: q for q in load(ROOT / 'benchmark/dev.json')}
    traces = [json.loads(line) for line in (output / 'traces.jsonl').read_text(encoding='utf-8').splitlines()]
    if len({(t['query_id'], t['method']) for t in traces}) != len(traces):
        raise ValueError('Duplicate traces')
    expected = {(cid, m) for cid in labels for m in METHODS}
    if {(t['query_id'], t['method']) for t in traces} != expected:
        raise ValueError('Missing/extra query-method traces')
    summary, audits = {}, []
    total = sum(q['answerable'] for q in labels.values())
    for method in METHODS:
        rows = [t for t in traces if t['method'] == method]
        values = {'hit1': 0, 'hit3': 0, 'context_evidence': 0}
        for t in rows:
            q = labels[t['query_id']]
            audit = {'query_id': q['id'], 'method': method, 'answerable': q['answerable'], 'status': t['status']}
            if q['answerable']:
                hits = [evidence_hit(c, q['gold']) for c in t['results']]
                h1, h3 = bool(hits and hits[0]), any(hits[:3])
                context_hit = any(hit and c['id'] in t['context_ids'] for hit, c in zip(hits, t['results']))
                # Full chunk text and its source label must actually be present, not just its ID.
                if context_hit:
                    context_hit = any(c['id'] in t['context_ids'] and c['text'] in t['context']
                                      and c['source'] in t['context'] and evidence_hit(c, q['gold']) for c in t['results'])
                if t['status'] == 'error':
                    h1, h3, context_hit = False, False, False
                values['hit1'] += h1
                values['hit3'] += h3
                values['context_evidence'] += context_hit
                audit.update(hit1=h1, hit3=h3, context_evidence=context_hit,
                             expected_answer=q['expected_answer'], gold=q['gold'])
            else:
                audit.update(hit1=None, hit3=None, context_evidence=None,
                             note='Excluded from retrieval denominators. Retrieval scores cannot determine abstention.')
            audits.append(audit)
        ok = [r for r in rows if r['status'] == 'ok']
        summary[method] = {**{k: ratio(v, total) for k, v in values.items()}, 'queries': len(rows),
                           'errors': len(rows) - len(ok),
                           'median_composed_latency_ms': statistics.median(r['composed_latency_ms'] for r in ok) if ok else None,
                           'mean_context_chars': statistics.mean(r['context_chars'] for r in ok) if ok else None,
                           'logical_embedding_tokens': sum(r['logical_embedding_tokens'] for r in rows),
                           'logical_estimated_embedding_cost_usd': sum(r['logical_estimated_embedding_cost_usd'] for r in rows) if all(r['logical_estimated_embedding_cost_usd'] is not None for r in rows) else None}
    report = {'split': 'dev', 'metrics_policy': 'Exact verbatim evidence, source and page. 15 answerable cases in denominator; errors count as misses and are also reported. Manual semantic review and agent metrics are separate.',
              'methods': summary, 'actual_api_usage_shared_once': record['actual_api_usage'],
              'actual_estimated_embedding_cost_usd_shared_once': record['actual_estimated_embedding_cost_usd'],
              'test_run': False, 'agent_evaluated': False, 'final_config_selected': False}
    write(output / 'summary.json', report)
    write(output / 'evidence_audit.json', audits)
    with (output / 'comparison.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['method', 'Hit@1', 'Evidence Hit@3', 'Context Evidence Rate', 'median_composed_ms', 'errors'])
        for method, row in summary.items():
            writer.writerow([method, *(f"{row[k]['n']}/{row[k]['N']}" for k in ('hit1', 'hit3', 'context_evidence')),
                             row['median_composed_latency_ms'], row['errors']])
    print(json.dumps(summary, ensure_ascii=True, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'score'))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        (run if args.command == 'run' else score)(args.output.resolve())
    except Exception as exc:
        # Never log raw provider/DSN exceptions, keys or tokens.
        print(f'Retrieval benchmark failed ({type(exc).__name__}); inspect run.json/error_type.', flush=True)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
