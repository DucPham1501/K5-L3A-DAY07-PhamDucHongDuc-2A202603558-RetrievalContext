"""Aggregate source-reviewed labels AFTER the agent run; never call a model."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from starter.agent_metrics import aggregate
from .retrieval_benchmark import evidence_hit

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def evaluate(run_dir, reviews_path):
    record = read(run_dir / 'run.json')
    if record['status'] != 'complete' or record['split'] not in ('dev', 'test'):
        raise ValueError('Only completed dev/test runs can be scored')
    split = record['split']
    for relative, checksum in record['asset_sha256'].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != checksum:
            raise ValueError('Frozen assets changed since run')
    cases = read(ROOT / f'benchmark/{split}.json')
    traces = [json.loads(line) for line in (run_dir / 'traces.jsonl').read_text(encoding='utf-8').splitlines()]
    reviews = read(reviews_path)
    if len({r['query_id'] for r in reviews}) != len(reviews):
        raise ValueError('Duplicate review IDs')
    by_id = {r['query_id']: r for r in reviews}
    if set(by_id) != {q['id'] for q in cases} or {t['query_id'] for t in traces} != set(by_id):
        raise ValueError('Incomplete/extra cases, traces or reviews')
    for t in traces:
        r = by_id[t['query_id']]
        if type(r.get('context_grade')) is not int or r['context_grade'] not in (0, 1, 2):
            raise ValueError('Context grade must be 0..2')
        if not r.get('reason') or not r.get('reviewer'):
            raise ValueError('Each review needs reason and reviewer')
        if len(r.get('citation_reasons', [])) != len(t['citations']) or not all(r['citation_reasons']):
            if t['citations']:
                raise ValueError('Every citation needs a support reason')
    report = aggregate(cases, traces, reviews)
    chunks = {c['id']: c for c in read(ROOT / 'data/chunks.json')}
    answerable = {q['id']: q for q in cases if q['answerable']}
    context_hits = 0
    for t in traces:
        if t['query_id'] in answerable:
            gold = answerable[t['query_id']]['gold']
            context_hits += any(cid in chunks and evidence_hit(chunks[cid], gold)
                                and chunks[cid]['text'] in t['context'] for cid in t['context_ids'])
    first_hits = {'hit1': 0, 'hit3': 0}
    for t in traces:
        if t['query_id'] in answerable:
            first = next((e for e in t['events'] if e['event'] == 'search' and e['status'] == 'ok'), None)
            ranked = first['results'] if first else []
            matched = [evidence_hit(c, answerable[t['query_id']]['gold']) for c in ranked]
            first_hits['hit1'] += bool(matched and matched[0])
            first_hits['hit3'] += any(matched[:3])
    report.update(split=split, review_file=str(reviews_path.relative_to(ROOT)),
                  reviewer_types=sorted({r['reviewer'] for r in reviews}),
                  human_review_completed=False, test_run=split == 'test',
                  first_retrieval_exact={k: {'n': n, 'N': len(answerable), 'rate': n / len(answerable)} for k,n in first_hits.items()},
                  context_grades=dict(Counter(r['context_grade'] for r in reviews if r['query_id'] in answerable)),
                  context_evidence_exact={'n': context_hits, 'N': len(answerable), 'rate': context_hits / len(answerable)},
                  note='Semantic labels come from explicit post-run source reviews, not from citation IDs or exact-match checks. AI review is disclosed and is not independent human confirmation.')
    target = run_dir / 'evaluation.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--reviews', type=Path, required=True)
    args = parser.parse_args()
    evaluate(args.run.resolve(), args.reviews.resolve())


if __name__ == '__main__':
    main()
