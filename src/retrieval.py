"""BM25, rank fusion and source-preserving context; no benchmark-label access."""
from collections import Counter
import math
import re
import unicodedata


def validate_search(query, filters, top_k):
    if not isinstance(query, str) or not query.strip():
        raise ValueError('Query must be a nonempty string')
    if type(top_k) is not int or not 1 <= top_k <= 100:
        raise ValueError('top_k must be an integer in 1..100')
    filters = {} if filters is None else filters
    if not isinstance(filters, dict) or set(filters) - {'doc_type', 'year'}:
        raise ValueError('Unsupported filter')
    if 'year' in filters and type(filters['year']) is not int:
        raise ValueError('year must be an integer')
    if 'doc_type' in filters and (not isinstance(filters['doc_type'], str) or not filters['doc_type'].strip()):
        raise ValueError('doc_type must be a nonempty string')
    return filters


def tokenize(text):
    """Vietnamese syllables/numbers: NFC + casefold, accents retained, no stoplist.

    This is NOT a Vietnamese dictionary word segmenter; make that limitation
    explicit when comparing configurations. Underscores and punctuation split.
    """
    return re.findall(r'[^\W_]+', unicodedata.normalize('NFC', text).casefold())


def ranked(results, method, score_type):
    return [{**c, 'rank': i, 'method': method, 'score_type': score_type}
            for i, c in enumerate(results, 1)]


class BM25Retriever:
    """Okapi BM25 with log(1 + (N-df+0.5)/(df+0.5)) positive IDF.

    Global corpus statistics stay fixed when metadata filters restrict eligible
    documents. Query terms are unique (binary query term frequency).
    """
    def __init__(self, chunks, *, k1=1.5, b=0.75):
        if not chunks or len({c['id'] for c in chunks}) != len(chunks):
            raise ValueError('Nonempty corpus with unique IDs required')
        if not math.isfinite(k1) or k1 <= 0 or not math.isfinite(b) or not 0 <= b <= 1:
            raise ValueError('Invalid BM25 parameters')
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.counts = [Counter(tokenize(c['text'])) for c in chunks]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.avgdl = sum(self.lengths) / len(chunks)
        if not self.avgdl:
            raise ValueError('Empty tokenized corpus')
        frequencies = Counter(term for row in self.counts for term in row)
        self.idf = {t: math.log1p((len(chunks) - df + 0.5) / (df + 0.5))
                    for t, df in frequencies.items()}

    def search(self, query, *, filters=None, top_k=3):
        filters = validate_search(query, filters, top_k)
        terms = sorted(set(tokenize(query)))
        results = []
        for chunk, counts, length in zip(self.chunks, self.counts, self.lengths):
            if any(chunk['metadata'].get(k) != v for k, v in filters.items()):
                continue
            norm = self.k1 * (1 - self.b + self.b * length / self.avgdl)
            score = sum(self.idf[t] * counts[t] * (self.k1 + 1) / (counts[t] + norm)
                        for t in terms if counts[t])
            if score > 0:
                results.append({**chunk, 'score': score})
        results.sort(key=lambda c: (-c['score'], c['id']))
        return ranked(results[:top_k], 'bm25', 'bm25_positive_idf')


def reciprocal_rank_fusion(branches, *, top_k=3, rank_constant=60):
    validate_search('fusion', None, top_k)
    if type(rank_constant) is not int or rank_constant < 1:
        raise ValueError('rank_constant must be positive integer')
    combined = {}
    for method, hits in branches.items():
        seen = set()
        for rank, hit in enumerate(hits, 1):
            cid = hit['id']
            if cid in seen:
                raise ValueError('Duplicate chunk ID within a branch')
            seen.add(cid)
            if cid not in combined:
                combined[cid] = {k: hit[k] for k in ('id', 'text', 'source_id', 'source', 'page', 'metadata')}
                combined[cid].update(score=0.0, branch_ranks={}, branch_scores={})
            row = combined[cid]
            if any(row[k] != hit[k] for k in ('text', 'source_id', 'source', 'page', 'metadata')):
                raise ValueError('Same ID has inconsistent content across retrievers')
            row['score'] += 1 / (rank_constant + rank)
            row['branch_ranks'][method] = rank
            row['branch_scores'][method] = hit['score']
    ordered = sorted(combined.values(), key=lambda c: (-c['score'], c['id']))
    return ranked(ordered[:top_k], 'hybrid_rrf', 'sum_reciprocal_ranks')


class HybridRetriever:
    def __init__(self, dense, lexical, *, candidate_k=20, rank_constant=60):
        validate_search('init', None, candidate_k)
        if type(rank_constant) is not int or rank_constant < 1:
            raise ValueError('Invalid rank constant')
        self.dense, self.lexical = dense, lexical
        self.candidate_k, self.rank_constant = candidate_k, rank_constant

    def search(self, query, *, filters=None, top_k=3):
        validate_search(query, filters, top_k)
        if top_k > self.candidate_k:
            raise ValueError('candidate_k must be >= top_k')
        return reciprocal_rank_fusion({
            'dense': self.dense.search(query, filters=filters, top_k=self.candidate_k),
            'bm25': self.lexical.search(query, filters=filters, top_k=self.candidate_k),
        }, top_k=top_k, rank_constant=self.rank_constant)


def pack_context(results, *, budget):
    """Keep full chunks in ranking order; budget counts all source labels too."""
    if type(budget) is not int or budget < 1:
        raise ValueError('Positive character budget required')
    blocks, ids, seen = [], [], set()
    for row in results:
        if row['id'] in seen:
            continue
        seen.add(row['id'])
        block = f"[{row['id']} | {row['source']} | page {row['page']}]\n{row['text']}"
        if len('\n\n'.join(blocks + [block])) <= budget:
            blocks.append(block)
            ids.append(row['id'])
    return '\n\n'.join(blocks), ids
