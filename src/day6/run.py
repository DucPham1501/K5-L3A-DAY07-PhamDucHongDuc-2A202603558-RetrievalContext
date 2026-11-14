"""Stage 3 CLI: prepare, ingest (real API/database), or one top-3 search."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import statistics
import sys
import time
from .chunking import fixed_size, by_paragraph
from .ingestion import load_corpus
from .embeddings import MyEmbedder, embedding_input
from .store import PgVectorStore

ROOT = Path(__file__).resolve().parents[2]
STARTER = ROOT
RESULTS = ROOT / 'results'

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare():
    import tiktoken
    corpus = ROOT/'data/processed/corpus.pages.jsonl'
    manifest = ROOT/'data/manifest.json'
    for doc in json.loads(manifest.read_text(encoding='utf-8-sig'))['documents']:
        if digest(ROOT/doc['local_path']) != doc['sha256']: raise ValueError('Source PDF checksum mismatch')
    pages = load_corpus(corpus, manifest)
    configs = json.loads((ROOT/'configs/day6/strategies.json').read_text(encoding='utf-8-sig'))
    if {**configs['B'], 'filter': True} != configs['C']: raise ValueError('B/C may differ only by filter')
    model = os.getenv('EMBEDDING_MODEL','text-embedding-3-small')
    enc = tiktoken.encoding_for_model(model)
    chunks, stats = {}, {}
    for strategy, cfg in configs.items():
        chunk_started = time.perf_counter()
        items=[]
        for page in pages:
            items.extend(fixed_size(page,cfg['chunk_size'],cfg['overlap']) if cfg['chunking']=='fixed' else by_paragraph(page,cfg['chunk_size']))
        for c in items:
            if not c.text or len(c.text)>cfg['chunk_size']: raise ValueError('Invalid chunk length')
        lengths = sorted(len(c.text) for c in items)
        tokens = [len(enc.encode(embedding_input(c.text))) for c in items]
        stats[strategy] = {'config':cfg,'chunk_count':len(items),'characters':sum(lengths),'tokens':sum(tokens),
            'chunking_and_statistics_seconds':time.perf_counter()-chunk_started,
            'length_characters':{'min':min(lengths),'p50':statistics.median(lengths),'p95':lengths[int((len(lengths)-1)*.95)],'max':max(lengths),'mean':statistics.mean(lengths)},
            'max_input_tokens':max(tokens)}
        chunks[strategy]=items
        target=RESULTS/'chunks'/f'{strategy}.jsonl'; target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(''.join(json.dumps(asdict(c),ensure_ascii=False)+'\n' for c in items),encoding='utf-8')
    if chunks['B'] != chunks['C']: raise ValueError('B/C chunk mismatch')
    report={'status':'prepared_only_no_embeddings','timestamp':datetime.now(timezone.utc).isoformat(),'content_pages':len(pages),
        'corpus_sha256':digest(corpus),'benchmark_sha256':digest(ROOT/'data/day6/questions.jsonl'),
        'model':model,'dimensions':int(os.getenv('EMBEDDING_DIMENSIONS','1536')),
        'input_processing':'NFC + collapse whitespace; no prefixes; identical document/query processing',
        'strategies':stats,'versions':{p:importlib.metadata.version(p) for p in ['openai','psycopg','tiktoken','pypdf','python-dotenv']}}
    write(RESULTS/'preparation.json',report)
    return chunks, report

def search_filters(raw=None, doc_type=None, year=None, strategy='C'):
    if raw is not None and (doc_type is not None or year is not None):
        raise ValueError('Use --filter OR --doc-type/--year, not both')
    try:
        filters = json.loads(raw) if raw is not None else {}
    except json.JSONDecodeError:
        raise ValueError('Invalid --filter JSON. In PowerShell use --doc-type "Nghị định" --year 2023 instead.') from None
    if not isinstance(filters, dict):
        raise ValueError('Filter must be a JSON object')
    if doc_type is not None:
        filters['doc_type'] = doc_type
    if year is not None:
        filters['year'] = year
    for key, value in filters.items():
        if key not in ('doc_type', 'year'):
            raise ValueError('Filter only supports doc_type and year')
        if key == 'year' and type(value) is not int:
            raise ValueError('Filter year must be an integer')
        if key == 'doc_type' and (not isinstance(value, str) or not value.strip()):
            raise ValueError('Filter doc_type must be a nonempty string')
    if filters and strategy != 'C':
        raise ValueError('Only strategy C applies metadata filters')
    return filters


def main():
    from dotenv import load_dotenv
    load_dotenv(STARTER/'.env',encoding='utf-8-sig')
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['prepare','ingest','search'],nargs='?',default='prepare')
    parser.add_argument('--question')
    parser.add_argument('--strategy',choices=['A','B','C'],default='C')
    parser.add_argument('--filter',help='JSON metadata supplied before retrieval')
    parser.add_argument('--doc-type',help='Metadata doc_type; PowerShell-friendly alternative to JSON')
    parser.add_argument('--year',type=int,help='Metadata year supplied before retrieval')
    args=parser.parse_args()
    filters = {}
    if args.command == 'search':
        if not args.question:
            parser.error('--question required for search')
        try:
            filters = search_filters(args.filter, args.doc_type, args.year, args.strategy)
        except ValueError as exc:
            parser.error(str(exc))
    RESULTS.mkdir(exist_ok=True)
    logging.basicConfig(filename=RESULTS/'pipeline.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    store=None; embedder=None; report={}
    try:
        chunks, report=prepare()
        if args.command=='prepare':
            print(json.dumps(report['strategies'],ensure_ascii=True,indent=2)); return
        model=report['model']; dimensions=report['dimensions']
        namespace=f'day6-v1:{model}:{dimensions}:nfc-ws-v1'
        # Database preflight before spending API tokens.
        store=PgVectorStore(os.getenv('DATABASE_URL',''),dimensions,namespace)
        store.create_schema()
        report['store']=store.versions(); report['namespace']=namespace
        embedder=MyEmbedder(model,dimensions,RESULTS/'embedding_cache')
        if args.command=='search':
            if not store.snapshot_ids(args.strategy): raise ValueError('Strategy is not ingested')
            vector=embedder.embed_query(args.question)
            hits=store.search(args.strategy,vector,3,filters)
            trace={'question':args.question,'strategy':args.strategy,'filter':filters,'hits':hits}
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            write(RESULTS/'search'/f'{stamp}.json',trace)
            print(json.dumps(trace,ensure_ascii=True,indent=2)); return
        report['status']='running'; report['ingestion']={}
        write(RESULTS/'ingestion.json',report)
        for strategy in ('A','B','C'):
            begin=time.perf_counter(); before=embedder.api_tokens; cached=embedder.cache_hits
            vectors=embedder.embed_documents([c.text for c in chunks[strategy]])
            store.upsert(strategy,chunks[strategy],vectors)
            first=store.snapshot_ids(strategy)
            seconds=time.perf_counter()-begin
            check_start=time.perf_counter()
            store.upsert(strategy,chunks[strategy],vectors)
            second=store.snapshot_ids(strategy)
            expected=sorted(c.chunk_id for c in chunks[strategy])
            if first!=expected or second!=expected: raise ValueError('Re-ingestion IDs/count mismatch')
            rate=os.getenv('EMBEDDING_USD_PER_MILLION','').strip()
            billed=embedder.api_tokens-before
            report['ingestion'][strategy]={'ingest_seconds':seconds,'reingest_check_seconds':time.perf_counter()-check_start,
                'first_count':len(first),'second_count':len(second),'same_ids_after_reingest':True,
                'api_tokens':billed,'cache_hits':embedder.cache_hits-cached,
                'estimated_api_cost_usd':billed*float(rate)/1e6 if rate else None,
                'rate_usd_per_million':float(rate) if rate else None}
            write(RESULTS/'ingestion.json',report)
        report['status']='complete'
        print('Ingest complete. A/B/C persisted; repeated ingestion verified without duplicates.')
    except Exception as exc:
        # Avoid secrets in provider/DSN exception messages. No mock fallback.
        logging.error('command=%s failed; exception_type=%s',args.command,type(exc).__name__)
        report['status']='failed'; report['error_type']=type(exc).__name__
        print(f'Pipeline failed ({type(exc).__name__}). Check OPENAI_API_KEY, DATABASE_URL and Docker; see results/pipeline.log.',file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        if embedder:
            report['api_usage']={'tokens':embedder.api_tokens,'requests':embedder.requests,'cache_hits':embedder.cache_hits}
        if args.command=='ingest': write(RESULTS/'ingestion.json',report)
        if store: store.close()

if __name__=='__main__': main()
