"""One-time selection from dev reviews before test; never reads test labels/results."""
from .common import ROOT, read, write, sha, now
from .benchmark import BENCH
from .runner import hashes
from .agent import system_prompt
import json


def select():
    output=ROOT/'results/advanced/selection.json'
    if output.exists():raise ValueError('Preserve selection made before test')
    plan=read(ROOT/'configs/advanced/experiments.json')
    candidates=[]
    for option in plan['experiments']:
        directory=ROOT/option['dev_run'];run=read(directory/'run.json');evaluation=read(directory/'evaluation.json');summary=read(directory/'summary.json')
        if run['status']!='complete' or evaluation['split']!='dev' or evaluation['N']<18:
            raise ValueError('Complete dev evaluation required')
        # Old runs remain immutable after adding an opt-in prompt policy. Permit
        # only the explicitly audited prompt dispatch/selection addition; retrieval,
        # index, runtime and all other source hashes must remain the same.
        changed=[p for p,h in run['code_sha256'].items() if hashes().get(p)!=h]
        if set(changed)-{'src/advanced/agent.py','src/advanced/select.py'}:
            raise ValueError('Candidate used a different runtime/retriever/index implementation')
        cfg=read(ROOT/option['config'])
        for line in (directory/'traces.jsonl').read_text(encoding='utf-8').splitlines():
            trace=json.loads(line)
            if any(call['request_text']['system']!=system_prompt(cfg) for call in trace['model_calls']):
                raise ValueError('Candidate prompt changed after dev')
        if run['config_sha256']!=sha(ROOT/option['config']):raise ValueError('Config changed after dev')
        key=[evaluation['rate'],-evaluation['errors'],-(summary['model_estimated_usd']+summary['embedding_usage']['estimated_usd']),-summary['median_ms']]
        candidates.append({**option,'key':key,'historical_code_changes':changed,
            'run_sha256':sha(directory/'run.json'),'review_sha256':sha(directory/'reviews.json'),'evaluation_sha256':sha(directory/'evaluation.json')})
    winner=max(candidates,key=lambda c:c['key'])
    write(output,{'status':'locked','locked_at':now(),'selected':winner['id'],
        'selected_config':winner['config'],'selected_config_sha256':sha(ROOT/winner['config']),
        'code_sha256':hashes(),'benchmark_manifest_sha256':sha(BENCH/'manifest.json'),
        'criteria':plan['selection_criteria'],'dev_comparisons':candidates,'test_results_used':False})
    print('Locked',winner['id'])


if __name__=='__main__':
    select()
