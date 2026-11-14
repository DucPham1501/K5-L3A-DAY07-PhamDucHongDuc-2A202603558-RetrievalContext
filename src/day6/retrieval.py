"""Dense adapter for LAB07; accepts query and user filters, never benchmark gold."""
import json
import os
from pathlib import Path
from src.retrieval import ranked, validate_search

ROOT = Path(__file__).resolve().parents[2]


class DenseRetriever:
    def __init__(self):
        from dotenv import load_dotenv
        from .embeddings import MyEmbedder
        from .store import PgVectorStore
        load_dotenv(ROOT / '.env', encoding='utf-8-sig')
        config = json.loads((ROOT / 'configs/inherited.json').read_text(encoding='utf-8'))
        model = os.getenv('EMBEDDING_MODEL', config['model'])
        dimensions = int(os.getenv('EMBEDDING_DIMENSIONS', str(config['dimensions'])))
        if (model, dimensions) != (config['model'], config['dimensions']):
            raise ValueError('Model/dimensions must match the inherited index')
        self.store = PgVectorStore(os.getenv('DATABASE_URL', ''), dimensions, config['namespace'])
        try:
            # Check the index before constructing the API client or spending query tokens.
            dimensions_present = self.store.conn.execute('''SELECT DISTINCT vector_dims(embedding)
                FROM day6_chunks WHERE namespace=%s AND strategy='C' ''', (config['namespace'],)).fetchall()
            if dimensions_present != [(dimensions,)]:
                raise ValueError('Missing or incompatible index; run scripts/day6_setup.py restore-store')
            self.embedder = MyEmbedder(model, dimensions, ROOT / 'results/embedding_cache')
        except Exception:
            self.store.close()
            raise

    def search(self, query, *, filters=None, top_k=3):
        filters = validate_search(query, filters, top_k)
        return self.search_vector(self.embedder.embed_query(query), filters=filters, top_k=top_k)

    def search_vector(self, vector, *, filters=None, top_k=3):
        """Reuse one real query embedding across compared pipelines."""
        filters = validate_search('embedded query', filters, top_k)
        hits = self.store.search('C', vector, top_k, filters)
        return ranked([dict(id=c['chunk_id'], source_id=c['document_id'], source=c['source'],
                            page=c['page'], text=c['text'], metadata=c['metadata'], score=c['score'])
                       for c in hits], 'dense', 'cosine_similarity')

    def verify_snapshot(self, chunks):
        rows = self.store.conn.execute('''SELECT chunk_id,document_id,source,page,content,metadata
            FROM day6_chunks WHERE namespace=%s AND strategy='C' ORDER BY chunk_id''',
            (self.store.namespace,)).fetchall()
        expected = [(c['id'], c['source_id'], c['source'], c['page'], c['text'], c['metadata'])
                    for c in sorted(chunks, key=lambda c: c['id'])]
        if rows != expected:
            raise ValueError('Dense and lexical snapshots differ')

    def close(self):
        self.store.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
