"""Verify inherited assets offline, check pgvector, or restore real cached vectors.

Runs independently of the removed source directory. Never calls an embedding API.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.day6.chunking import fixed_size, by_paragraph
from src.day6.ingestion import load_corpus
from src.day6.models import Chunk


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    provenance = load(ROOT / 'configs/inherited.json')
    for relative, expected in provenance['sha256'].items():
        if digest(ROOT / relative) != expected:
            raise ValueError(f'Inherited file checksum mismatch: {relative}')
    manifest = load(ROOT / 'data/manifest.json')
    for doc in manifest['documents']:
        if digest(ROOT / doc['local_path']) != doc['sha256']:
            raise ValueError('Source PDF checksum mismatch')
    pages = load_corpus(ROOT / 'data/processed/corpus.pages.jsonl', ROOT / 'data/manifest.json')
    config = load(ROOT / 'configs/strategies.json')
    strategies = {}
    for name, cfg in config.items():
        chunks = [json.loads(line) for line in (ROOT / f'data/chunks/{name}.jsonl').read_text(encoding='utf-8').splitlines()]
        regenerated = []
        for page in pages:
            regenerated.extend(fixed_size(page, cfg['chunk_size'], cfg['overlap'])
                               if cfg['chunking'] == 'fixed' else by_paragraph(page, cfg['chunk_size']))
        if chunks != [asdict(c) for c in regenerated]:
            raise ValueError(f'Changed chunks or IDs: {name}')
        strategies[name] = chunks
    adapted = load(ROOT / 'data/chunks.json')
    expected = [dict(id=c['chunk_id'], text=c['text'], source_id=c['document_id'],
                     source=c['source'], page=c['page'], metadata=c['metadata']) for c in strategies['C']]
    if adapted != expected:
        raise ValueError('Day 7 chunk adapter changed content or identity')
    cached = {}
    for chunks in strategies.values():
        for c in chunks:
            # Identical to the inherited embedding implementation, without importing its SDK.
            import unicodedata
            text = ' '.join(unicodedata.normalize('NFC', c['text']).split())
            key = hashlib.sha256(f"{provenance['model']}:{provenance['dimensions']}:nfc-ws-v1:{text}".encode()).hexdigest()
            path = ROOT / f'results/embedding_cache/{key}.json'
            if not path.exists():
                raise ValueError(f'Missing real cached document embedding: {key}')
            vector = load(path)['vector']
            if len(vector) != provenance['dimensions'] or not all(type(x) in (int, float) and math.isfinite(x) for x in vector) or not any(vector):
                raise ValueError(f'Invalid cached embedding: {key}')
            if digest(path) != provenance['cache_sha256'].get(key):
                raise ValueError(f'Cached vector differs from inherited snapshot: {key}')
            cached[c['chunk_id']] = vector
    return provenance, strategies, cached, {
        'status': 'offline_verified', 'content_pages': len(pages),
        'characters': sum(len(p.text) for p in pages),
        'chunks': {s: len(c) for s, c in strategies.items()},
        'day7_chunks': len(adapted), 'document_vectors_verified': len(cached),
        'model': provenance['model'], 'dimensions': provenance['dimensions'],
        'database_checked': False, 'api_calls': 0,
    }


def database(provenance, strategies, vectors, restore):
    from dotenv import load_dotenv
    from src.day6.store import PgVectorStore
    load_dotenv(ROOT / '.env', encoding='utf-8-sig')
    model = os.getenv('EMBEDDING_MODEL', provenance['model'])
    dimensions = int(os.getenv('EMBEDDING_DIMENSIONS', str(provenance['dimensions'])))
    if (model, dimensions) != (provenance['model'], provenance['dimensions']):
        raise ValueError('Configured model/dimensions differ from inherited vectors; use a separate index for a new model')
    store = PgVectorStore(os.getenv('DATABASE_URL', ''), dimensions, provenance['namespace'])
    try:
        if restore:
            store.create_schema()
            for name, chunks in strategies.items():
                store.upsert(name, [Chunk(**c) for c in chunks], [vectors[c['chunk_id']] for c in chunks])
        for name, chunks in strategies.items():
            rows = store.conn.execute('''SELECT chunk_id, document_id, source, page, content, metadata,
                vector_dims(embedding) FROM day6_chunks WHERE namespace=%s AND strategy=%s
                ORDER BY chunk_id''', (provenance['namespace'], name)).fetchall()
            expected = [(c['chunk_id'], c['document_id'], c['source'], c['page'], c['text'], c['metadata'], dimensions)
                        for c in sorted(chunks, key=lambda c: c['chunk_id'])]
            if rows != expected:
                raise ValueError(f'Database snapshot differs from inherited chunks: {name}')
        return {'status': 'restored_and_verified' if restore else 'verified', **store.versions()}
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('verify', 'check-store', 'restore-store'), nargs='?', default='verify')
    args = parser.parse_args()
    try:
        provenance, strategies, vectors, result = verify()
        if args.command != 'verify':
            result['database'] = database(provenance, strategies, vectors, args.command == 'restore-store')
            result['database_checked'] = True
        target = ROOT / 'results' / f'day6-{args.command}.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except Exception as exc:
        # Do not print DSNs, provider exceptions or secrets.
        print(f'Setup failed ({type(exc).__name__}); check files, dependencies, Docker and local .env.', file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
