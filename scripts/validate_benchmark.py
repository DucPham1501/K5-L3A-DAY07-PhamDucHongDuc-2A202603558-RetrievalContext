"""Audit the frozen benchmark and source evidence, without running retrieval/API."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.benchmark import validate_input_case


def load(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


def normalized(text):
    text = ''.join(c for c in unicodedata.normalize('NFD', text.casefold()) if not unicodedata.combining(c))
    return ' '.join(text.replace('đ', 'd').split())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate():
    manifest = load('benchmark/manifest.json')
    for relative, expected in manifest['sha256'].items():
        require(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, f'Frozen file changed: {relative}')
    chunks = load('data/chunks.json')
    pages = [json.loads(line) for line in (ROOT / 'data/processed/corpus.pages.jsonl').read_text(encoding='utf-8').splitlines()]
    page_by_key = {(p['document_id'], p['page']): p for p in pages}
    source_docs = {d['source_id']: d for d in load('data/manifest.json')['documents']}
    for doc in source_docs.values():
        require(hashlib.sha256((ROOT / doc['local_path']).read_bytes()).hexdigest() == doc['sha256'], 'Source PDF changed')
    old = [json.loads(line) for line in (ROOT / 'data/day6/questions.jsonl').read_text(encoding='utf-8').splitlines()]
    old_test_pairs = {(q['gold_source_id'], q['gold_article']) for q in old if q['split'] == 'test'}
    ids, questions, article_pairs, audit, counts = set(), set(), {}, [], {}
    for split, minimum in (('dev', (15, 2)), ('test', (5, 2))):
        cases = load(f'benchmark/{split}.json')
        inputs = load(f'benchmark/inputs/{split}.json')
        require(isinstance(cases, list) and isinstance(inputs, list), 'Expected JSON arrays')
        count = Counter()
        article_pairs[split] = set()
        expected_inputs = []
        for q in cases:
            cid = q.get('id')
            require(isinstance(cid, str) and cid and cid not in ids, 'Invalid/duplicate ID')
            ids.add(cid)
            require(q.get('split') == split, f'{cid}: wrong split')
            require(type(q.get('answerable')) is bool, f'{cid}: answerable must be boolean')
            require(isinstance(q.get('question'), str) and q['question'].strip(), f'{cid}: missing question')
            question = normalized(q['question'])
            require(question not in questions, f'{cid}: duplicate question')
            questions.add(question)
            require(isinstance(q.get('expected_answer'), str) and q['expected_answer'].strip(), f'{cid}: missing expected answer/behavior')
            safe = {k: q[k] for k in ('id', 'question', 'filter') if k in q}
            validate_input_case(safe)
            expected_inputs.append(safe)
            if q['answerable']:
                count['answerable'] += 1
                require(q.get('expected_behavior') == 'search_and_answer', f'{cid}: wrong behavior')
                require(isinstance(q.get('gold'), list) and q['gold'], f'{cid}: missing gold')
                matched = set()
                for gold in q['gold']:
                    key = (gold['source_id'], gold['page'])
                    require(key in page_by_key, f'{cid}: source/page missing')
                    require(isinstance(gold['evidence'], str) and gold['evidence'].strip(), f'{cid}: empty evidence')
                    require(gold['evidence'] in page_by_key[key]['text'], f'{cid}: quote absent from source page')
                    hits = [c for c in chunks if (c['source_id'], c['page']) == key and gold['evidence'] in c['text']]
                    require(hits, f'{cid}: evidence does not fit a chunk')
                    matched.update(c['id'] for c in hits)
                    if q.get('filter'):
                        require(all(all(c['metadata'].get(k) == v for k, v in q['filter'].items()) for c in hits), f'{cid}: filter conflicts with evidence')
                    require(q['source'] == source_docs[gold['source_id']]['local_path'], f'{cid}: source path mismatch')
                    require(q['source_url'] == source_docs[gold['source_id']]['source_path_or_url'], f'{cid}: source URL mismatch')
                    article_pairs[split].add((gold['source_id'], q['article']))
                require(matched == set(q['gold_chunk_ids']), f'{cid}: wrong supporting chunk IDs')
                require(bool(q.get('verification', {}).get('method')), f'{cid}: missing review record')
                audit.append({'query_id': cid, 'answerable': True, 'evidence_verified': True, 'chunk_ids': sorted(matched), 'reviewer': q['verification']['reviewer']})
            else:
                count['unanswerable'] += 1
                require(q.get('expected_behavior') == 'search_and_abstain', f'{cid}: wrong behavior')
                require(not q.get('gold') and not q.get('gold_chunk_ids'), f'{cid}: unanswerable case has gold')
                require(bool(q.get('absence_reason')), f'{cid}: missing absence reason')
                check = q.get('absence_check', {})
                require(check.get('terms_expected_absent') and check.get('related_pages') and check.get('method'), f'{cid}: missing absence audit')
                scan = {}
                for term in check['terms_expected_absent']:
                    pattern = re.compile(r'(?<!\w)' + re.escape(normalized(term)) + r'(?!\w)')
                    hits = [{'source_id': p['document_id'], 'page': p['page']} for p in pages if pattern.search(normalized(p['text']))]
                    scan[term] = hits
                    require(not hits, f'{cid}: absence term found; review label')
                for page in check['related_pages']:
                    require((page['source_id'], page['page']) in page_by_key, f'{cid}: invalid contextual review page')
                audit.append({'query_id': cid, 'answerable': False, 'pages_scanned': len(pages), 'term_matches': scan, 'absence_reason': q['absence_reason'], 'limitation': 'Term scan corroborates the contextual absence review; it is not a proof by itself.'})
        require(count['answerable'] >= minimum[0] and count['unanswerable'] >= minimum[1], f'{split}: insufficient cases')
        require(dict(count) == manifest['counts'][split], f'{split}: manifest count mismatch')
        for case in inputs:
            validate_input_case(case)
        require(inputs == expected_inputs, f'{split}: runtime projection mismatch or leaked gold')
        counts[split] = dict(count)
    require(not article_pairs['dev'] & article_pairs['test'], 'Dev/test share source/article')
    require(not article_pairs['test'] & old_test_pairs, 'New test reuses an old Day 6 test article')
    return {'status': 'validated', 'version': manifest['version'], 'counts': counts, 'total': len(ids),
            'content_pages': len(pages), 'source_article_overlap_dev_test': 0, 'old_test_article_overlap': 0,
            'runtime_gold_leakage': False, 'api_calls': 0, 'retrieval_evaluated': False,
            'human_review_completed': False, 'cases': audit}


def main():
    report = validate()
    output = ROOT / 'results/benchmark_validation.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'cases'}, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
