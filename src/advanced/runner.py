"""Run real advanced agent; immutable test selection and hash checks precede input loading."""
import argparse
from collections import Counter
import json
import statistics
from .common import ROOT, DATA, PDF, read, write, sha, now, client, cost
from .benchmark import BENCH, load_inputs
from .retrieval import Retriever
from .agent import run


def hashes():
    files=list((ROOT/'src/advanced').glob('*.py'))+[ROOT/'src/retrieval.py',ROOT/'src/day6/embeddings.py']
    return {str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(files)}


def execute(split,config_path,output):
    config=read(config_path)
    manifest=read(BENCH/'manifest.json')
    for path,digest in manifest['sha256'].items():
        if sha(ROOT/path)!=digest:raise ValueError('Frozen asset changed: '+path)
    if split=='test':
        lock=read(ROOT/'results/advanced/selection.json')
        if lock['status']!='locked' or sha(config_path)!=lock['selected_config_sha256'] or hashes()!=lock['code_sha256']:
            raise ValueError('Test requires locked config and code')
        if sha(BENCH/'manifest.json')!=lock['benchmark_manifest_sha256']:raise ValueError('Benchmark changed')
    inputs=load_inputs(split)
    output.mkdir(parents=True,exist_ok=False)
    record={'status':'running','split':split,'started_at':now(),'config':config,
        'config_sha256':sha(config_path),'code_sha256':hashes(),
        'benchmark_manifest_sha256':sha(BENCH/'manifest.json'),'pdf_sha256':sha(PDF),
        'index_sha256':sha(DATA/'index.json'),'vector_sha256':sha(DATA/'vectors.json'),
        'cases':len(inputs),'note':'Runtime does not read gold labels. Semantic reviews are separate.'}
    write(output/'run.json',record)
    api=client();retriever=None;traces=[]
    try:
        retriever=Retriever(config)
        for case in inputs:
            trace=run(case['question'],api,retriever,config)
            trace.update(query_id=case['id'],split=split)
            with (output/'traces.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(trace,ensure_ascii=False)+'\n')
            traces.append(trace)
            print(case['id'],trace['status'],len(trace['model_calls']),'model calls',flush=True)
        record['status']='complete'
    finally:
        api.close()
        if retriever:
            embedder=retriever.embedder
            record['embedding_usage']={'tokens':embedder.api_tokens,'requests':embedder.requests,'cache_hits':embedder.cache_hits,
                'estimated_usd':embedder.api_tokens*config['pricing_usd_per_million']['embedding']/1e6}
            retriever.close()
        usages=[call['usage'] for trace in traces for call in trace['model_calls']]
        record.update(completed_at=now(),completed_cases=len(traces),model_usage=usages,
                      model_estimated_usd=cost(usages,config['pricing_usd_per_million']))
        write(output/'run.json',record)
    write(output/'summary.json',{'split':split,'cases':len(traces),'statuses':dict(Counter(t['status'] for t in traces)),
        'median_ms':statistics.median(t['elapsed_ms'] for t in traces),'model_calls':len(usages),
        'model_estimated_usd':record['model_estimated_usd'],'embedding_usage':record['embedding_usage'],
        'content_review_file':'reviews.json (separate explicit source review)'})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('split',choices=['dev','test'])
    parser.add_argument('--config',type=__import__('pathlib').Path,required=True)
    parser.add_argument('--output',type=__import__('pathlib').Path,required=True)
    args=parser.parse_args()
    execute(args.split,args.config.resolve(),args.output.resolve())
