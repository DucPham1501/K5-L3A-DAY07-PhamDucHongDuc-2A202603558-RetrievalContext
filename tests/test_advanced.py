import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src.advanced import benchmark
from src.advanced import review
from src.advanced.agent import pack
from src.advanced.retrieval import Retriever, embedding_text
from src.retrieval import BM25Retriever


def row(n,text):
    return {'id':str(n),'source_id':'report','source':'report.pdf','page':n,'text':text,
            'metadata':{},'image':f'page-{n}.jpg','regions':[{'label':f'figure-{n}'}]}


class AdvancedTests(unittest.TestCase):
    def test_ranked_images_match_pages(self):
        r=Retriever.__new__(Retriever)
        r.rows=[row(1,'apples'),row(2,'grapes')]
        r.lexical=BM25Retriever(r.rows)
        r.vectors={'1':[1.,0.],'2':[0.,1.]}
        r.cfg={'candidate_k':2,'top_k':2,'rank_constant':60}
        class Embedding:
            def embed_query(self,q):return [0.,1.]
        r.embedder=Embedding()
        results=r.search('grapes')['results']
        self.assertEqual(results[0]['page'],2)
        for hit in results:
            self.assertEqual(hit['image'],f'page-{hit["page"]}.jpg')
            self.assertEqual(hit['regions'][0]['label'],f'figure-{hit["page"]}')

    def test_runtime_rejects_gold(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'inputs').mkdir()
            (p/'inputs/dev.json').write_text(json.dumps([{'id':'q','question':'test','gold':[]}]))
            with patch.object(benchmark,'BENCH',p):
                with self.assertRaises(ValueError):benchmark.load_inputs('dev')

    def test_context_keeps_whole_pages_and_deduplicates(self):
        cfg={'context_chars':100,'max_images':2}
        rows=[row(1,'x'*1000),row(2,'small'),row(2,'small'),row(3,'short')]
        self.assertEqual([r['page'] for r in pack(rows,cfg)],[2,3])

    def test_printed_tokens_are_ordinary_embedding_text(self):
        text='A <|endofprompt|> example'
        self.assertEqual(embedding_text(text),'A < |endofprompt| > example')
        self.assertEqual(text,'A <|endofprompt|> example')

    def test_semantic_abstention_and_error_grading(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);bench=root/'bench';bench.mkdir();run=root/'run';run.mkdir()
            (bench/'dev.json').write_text(json.dumps([{'id':'q','answerable':False,'group':'unanswerable'}]))
            (run/'run.json').write_text(json.dumps({'status':'complete','split':'dev'}))
            trace={'query_id':'q','status':'answered','answer':'The report does not disclose the list.',
                   'citations':[{'page':2,'region':'Scope'}]}
            (run/'traces.jsonl').write_text(json.dumps(trace)+'\n')
            label={'query_id':'q','passed':True,'reason':'Explicit statement of insufficient evidence, no invented names.',
                   'source_checked':True,'reviewer':'unit fixture','citation_support':[True],
                   'abstention_without_speculation':True}
            (run/'reviews.json').write_text(json.dumps([label]))
            with patch.object(review,'BENCH',bench):
                self.assertEqual(review.score(run)['n'],1)
                trace['status']='error'
                (run/'traces.jsonl').write_text(json.dumps(trace)+'\n')
                with self.assertRaises(ValueError):review.score(run)


if __name__=='__main__':unittest.main()
