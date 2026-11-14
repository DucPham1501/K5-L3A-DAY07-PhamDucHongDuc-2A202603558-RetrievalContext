import math
from pathlib import Path
import sys
import unicodedata
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.retrieval import BM25Retriever, HybridRetriever, pack_context, reciprocal_rank_fusion, tokenize
from src.retrieval_benchmark import evidence_hit


def chunk(cid, text, year=2023):
    return {'id': cid, 'text': text, 'source_id': 'doc', 'source': 'doc.pdf',
            'page': 1, 'metadata': {'doc_type': 'Nghị định', 'year': year}, 'score': 1.0}


class RetrievalTests(unittest.TestCase):
    def test_bm25_known_score_and_tf_saturation(self):
        rows = [chunk('a', 'x x z z'), chunk('b', 'x z z z'), chunk('c', 'y y y y')]
        hits = BM25Retriever(rows).search('x x', top_k=3)
        self.assertEqual([r['id'] for r in hits], ['a', 'b'])
        idf = math.log(1.6)  # N=3, df=2: log(1 + 1.5/2.5)
        self.assertAlmostEqual(hits[0]['score'], idf * 10 / 7)
        self.assertAlmostEqual(hits[1]['score'], idf)
        self.assertEqual(hits, BM25Retriever(rows).search('x', top_k=3))

    def test_length_normalization_and_common_term_positive(self):
        index = BM25Retriever([chunk('a', 'x y y y'), chunk('b', 'x')])
        self.assertEqual([r['id'] for r in index.search('x')], ['b', 'a'])
        self.assertTrue(all(r['score'] > 0 for r in index.search('x')))
        self.assertEqual(index.search('unseen'), [])

    def test_filters_do_not_change_global_bm25_statistics(self):
        index = BM25Retriever([chunk('a', 'dữ liệu', 2018), chunk('b', 'dữ liệu cá nhân')])
        before = {r['id']: r['score'] for r in index.search('dữ liệu')}
        filtered = index.search('dữ liệu', filters={'year': 2023})
        self.assertEqual([r['id'] for r in filtered], ['b'])
        self.assertEqual(filtered[0]['score'], before['b'])
        for invalid in ({'page': 1}, {'year': True}, {'doc_type': {}}):
            with self.assertRaises(ValueError):
                index.search('x', filters=invalid)

    def test_unicode_tokens_preserve_accents_and_split_punctuation(self):
        self.assertEqual(tokenize(unicodedata.normalize('NFD', 'DỮ_LIỆU, 72!')), ['dữ', 'liệu', '72'])
        self.assertNotEqual(tokenize('dữ liệu'), tokenize('du lieu'))

    def test_rrf_combines_ranks_instead_of_incompatible_scores(self):
        a, b, c = chunk('a', 'A'), chunk('b', 'B'), chunk('c', 'C')
        hits = reciprocal_rank_fusion({'dense': [{**a, 'score': 1e20}, b], 'bm25': [c, {**b, 'score': 1e-20}]})
        self.assertEqual(hits[0]['id'], 'b')
        self.assertEqual(hits[0]['branch_ranks'], {'dense': 2, 'bm25': 2})
        self.assertAlmostEqual(hits[0]['score'], 2 / 62)
        self.assertEqual(len({h['id'] for h in hits}), len(hits))

    def test_rrf_rejects_duplicate_or_inconsistent_identity(self):
        a = chunk('a', 'A')
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion({'dense': [a, a]})
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion({'dense': [a], 'bm25': [{**a, 'text': 'Changed'}]})

    def test_hybrid_propagates_errors_without_sparse_fallback(self):
        class Broken:
            def search(self, *args, **kwargs):
                raise ConnectionError('offline')
        with self.assertRaises(ConnectionError):
            HybridRetriever(Broken(), BM25Retriever([chunk('a', 'x')])).search('x')

    def test_context_budget_includes_sources_and_does_not_truncate(self):
        row = chunk('a', 'Bằng chứng có điều kiện.')
        full, ids = pack_context([row, row], budget=200)
        self.assertEqual(ids, ['a'])
        self.assertIn('doc.pdf', full)
        self.assertIn(row['text'], full)
        self.assertEqual(pack_context([row], budget=len(full) - 1), ('', []))

    def test_evidence_needs_correct_source_page_and_complete_quote(self):
        gold = [{'source_id': 'doc', 'page': 1, 'evidence': 'có điều kiện'}]
        row = chunk('a', 'Bằng chứng có điều kiện.')
        self.assertTrue(evidence_hit(row, gold))
        self.assertFalse(evidence_hit({**row, 'page': 2}, gold))
        self.assertFalse(evidence_hit({**row, 'source_id': 'wrong'}, gold))
        self.assertFalse(evidence_hit({**row, 'text': 'Bằng chứng'}, gold))


if __name__ == '__main__':
    unittest.main()
