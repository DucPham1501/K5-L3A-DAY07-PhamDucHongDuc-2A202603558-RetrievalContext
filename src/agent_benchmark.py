"""Run the real agent on dev only; no benchmark labels enter model requests."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import statistics

from .agent import RetrievalTools, run_agent, validate_config
from .agent_controller import OpenAIController
from .benchmark import load_inputs
from .day6.retrieval import DenseRetriever

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def usage_summary(records, prices):
    totals = Counter(input_tokens=0, cached_input_tokens=0, output_tokens=0)
    for record in records:
        usage = record.get('usage')
        if usage:
            totals['input_tokens'] += usage['prompt_tokens']
            totals['output_tokens'] += usage['completion_tokens']
            totals['cached_input_tokens'] += (usage.get('prompt_tokens_details') or {}).get('cached_tokens', 0) or 0
    totals = dict(totals)
    totals['estimated_usd'] = ((totals['input_tokens'] - totals['cached_input_tokens']) * prices['input']
        + totals['cached_input_tokens'] * prices['cached_input'] + totals['output_tokens'] * prices['output']) / 1e6
    totals['requests_with_usage'] = sum('usage' in r for r in records)
    totals['requests_without_usage'] = sum('usage' not in r for r in records)
    return totals


def execute(output, config_path, question=None, filters=None, split='dev'):
    config = read(config_path)
    validate_config(config)
    frozen = read(ROOT / 'benchmark/manifest.json')
    if split not in ('dev', 'test'):
        raise ValueError('Invalid benchmark split')
    if split == 'test':
        lock = read(ROOT / 'results/experiments/selection.json')
        if lock.get('status') != 'locked' or checksum(config_path) not in lock['allowed_test_config_sha256']:
            raise ValueError('Test requires a previously locked baseline/selected config')
        for filename, expected in lock['code_sha256'].items():
            if checksum(ROOT / filename) != expected:
                raise ValueError('Code changed after dev selection')
        if frozen['sha256'] != lock['benchmark_sha256']:
            raise ValueError('Benchmark changed after dev selection')
    assets = ['data/chunks.json', 'data/processed/corpus.pages.jsonl']
    if question is None:
        assets += [f'benchmark/inputs/{split}.json', f'benchmark/{split}.json']
    for relative in assets:
        if checksum(ROOT / relative) != frozen['sha256'][relative]:
            raise ValueError(f'Frozen asset changed: {relative}')
    inputs = load_inputs(split) if question is None else [{'id': 'interactive', 'question': question, 'filter': filters or {}}]
    chunks = read(ROOT / 'data/chunks.json')
    output.mkdir(parents=True, exist_ok=False)
    stamp = datetime.now(timezone.utc).isoformat()
    source_files = ['src/agent.py', 'src/agent_controller.py', 'src/agent_benchmark.py',
                    'src/retrieval.py', 'src/day6/retrieval.py', 'src/day6/embeddings.py', 'src/day6/store.py']
    record = {'status': 'running', 'started_at': stamp, 'split': split if question is None else 'interactive',
              'config': config, 'config_sha256': checksum(config_path),
              'asset_sha256': {p: checksum(ROOT / p) for p in assets},
              'code_sha256': {p: checksum(ROOT / p) for p in source_files},
              'versions': {p: importlib.metadata.version(p) for p in ('openai', 'psycopg', 'tiktoken')},
              'query_count': len(inputs), 'chunk_count': len(chunks), 'test_run': split == 'test',
              'quality_review_completed': False}
    write(output / 'run.json', record)
    dense = controller = None
    traces = []
    try:
        dense = DenseRetriever()
        dense.verify_snapshot(chunks)
        tools = RetrievalTools(dense, chunks, config)
        controller = OpenAIController(config)
        record['model_preflight_id'] = controller.client.models.retrieve(config['model']).id
        record['store'] = dense.store.versions()
        record['embedding_model'] = dense.embedder.model_name
        record['embedding_dimensions'] = dense.embedder.dimensions
        with (output / 'traces.jsonl').open('x', encoding='utf-8') as stream:
            for case in inputs:
                before_tokens, before_cache = dense.embedder.api_tokens, dense.embedder.cache_hits
                before_requests = len(dense.embedder.requests)
                trace = run_agent(case['question'], controller, tools, config, filters=case.get('filter'))
                trace.update(query_id=case['id'], question=case['question'], split=record['split'],
                             filter=case.get('filter'), model=config['model'])
                trace['embedding_usage'] = {'tokens': dense.embedder.api_tokens-before_tokens,
                    'cache_hits': dense.embedder.cache_hits-before_cache,
                    'requests': dense.embedder.requests[before_requests:]}
                trace['model_usage'] = usage_summary(trace['model_calls'], config['pricing_usd_per_million'])
                stream.write(json.dumps(trace, ensure_ascii=False) + '\n')
                stream.flush()
                traces.append(trace)
                print(f"{case['id']}: {trace['status']}, searches={trace['search_count']}, model_calls={len(trace['model_calls'])}", flush=True)
                if trace['status'] == 'error':
                    # Preserve partial evidence; avoid repeatedly spending on broken infrastructure.
                    raise RuntimeError('Agent execution error recorded; fix before another run')
        record['status'] = 'complete'
        record['finished_at'] = datetime.now(timezone.utc).isoformat()
    except KeyboardInterrupt:
        record.update(status='interrupted', stop_reason='operator_interruption',
                      finished_at=datetime.now(timezone.utc).isoformat())
        raise
    except Exception as exc:
        record.update(status='failed', error_type=type(exc).__name__)
        raise
    finally:
        record['completed_queries'] = len(traces)
        if controller:
            record['model_usage'] = usage_summary(controller.records, config['pricing_usd_per_million'])
            controller.close()
        if dense:
            record['embedding_usage'] = {'tokens': dense.embedder.api_tokens,
                                        'cache_hits': dense.embedder.cache_hits, 'requests': dense.embedder.requests}
            raw_rate = os.getenv('EMBEDDING_USD_PER_MILLION', '').strip()
            record['embedding_estimated_usd'] = dense.embedder.api_tokens * float(raw_rate) / 1e6 if raw_rate else None
            dense.close()
        write(output / 'run.json', record)
    successful = [t for t in traces if t['status'] != 'error']
    summary = {'split': record['split'], 'cases': len(traces),
        'statuses': dict(Counter(t['status'] for t in traces)),
        'tool_use': {'n': sum(t['search_count'] > 0 for t in successful), 'N': len(successful)},
        'search_count_distribution': dict(Counter(t['search_count'] for t in successful)),
        'tools_used': dict(Counter(e['tool'] for t in traces for e in t['events'] if e['event'] == 'search' and e['status'] == 'ok')),
        'stop_reasons': dict(Counter(t['stop_reason'] for t in traces)),
        'median_elapsed_ms': statistics.median(t['elapsed_ms'] for t in traces),
        'model_usage': record['model_usage'], 'embedding_usage': record['embedding_usage'],
        'embedding_estimated_usd': record['embedding_estimated_usd'],
        'quality_review_completed': False, 'test_run': split == 'test',
        'note': 'Counts and citation structure do not establish answer correctness/semantic grounding. Read sources and label separately.'}
    write(output / 'summary.json', summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in ('embedding_usage',)}, ensure_ascii=True, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('dev', 'test', 'ask'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=ROOT / 'configs/agent.json')
    parser.add_argument('--question')
    parser.add_argument('--doc-type')
    parser.add_argument('--year', type=int)
    args = parser.parse_args()
    if args.command == 'ask' and not args.question:
        parser.error('ask requires --question')
    if args.command in ('dev', 'test') and any(v is not None for v in (args.question, args.doc_type, args.year)):
        parser.error('Benchmark runs use only frozen inputs')
    filters = {}
    if args.doc_type is not None:
        filters['doc_type'] = args.doc_type
    if args.year is not None:
        filters['year'] = args.year
    try:
        execute(args.output.resolve(), args.config.resolve(), args.question if args.command == 'ask' else None,
                filters, split='test' if args.command == 'test' else 'dev')
    except Exception as exc:
        print(f'Agent run failed ({type(exc).__name__}); inspect run.json/traces for safe error types.', flush=True)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
