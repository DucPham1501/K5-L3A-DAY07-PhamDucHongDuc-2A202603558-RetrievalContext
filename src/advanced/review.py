"""Aggregate explicit human/AI source reviews; errors always remain in denominator."""
import argparse
from collections import Counter
import json
from pathlib import Path
from .common import ROOT, read, write
from .benchmark import BENCH


def score(directory):
    run=read(directory/'run.json')
    cases=read(BENCH/f'{run["split"]}.json')
    traces=[json.loads(x) for x in (directory/'traces.jsonl').read_text(encoding='utf-8').splitlines()]
    reviews=read(directory/'reviews.json')
    if run['status']!='complete' or len(traces)!=len(cases) or len(reviews)!=len(cases):raise ValueError('Review every case, including errors')
    if len({r['query_id'] for r in reviews})!=len(reviews):raise ValueError('Duplicate review')
    by_id={t['query_id']:t for t in traces};labels={r['query_id']:r for r in reviews}
    groups={};audit=[]
    for case in cases:
        trace=by_id[case['id']];review=labels[case['id']]
        if type(review['passed']) is not bool or not review['reason'] or not review['source_checked']:
            raise ValueError('Explicit source review required')
        support=review['citation_support']
        if len(support)!=len(trace['citations']) or any(type(v) is not bool for v in support):raise ValueError('Review every citation')
        if review['passed']:
            if trace['status']=='error':raise ValueError('An error cannot pass')
            if case['answerable']:
                if trace['status']!='answered' or not support or not all(support) or not review['complete_answer'] or not review['complete_evidence']:
                    raise ValueError('Partial or unsupported answer cannot pass')
            elif trace['status'] not in ('abstain','answered') or not review['abstention_without_speculation']:
                raise ValueError('Unanswerable needs clean abstention')
        group=groups.setdefault(case['group'],{'n':0,'N':0})
        group['N']+=1;group['n']+=review['passed']
        audit.append({'query_id':case['id'],'passed':review['passed'],'reason':review['reason']})
    for g in groups.values():g['rate']=g['n']/g['N']
    n=sum(v['n'] for v in groups.values());N=len(cases)
    result={'split':run['split'],'n':n,'N':N,'rate':n/N,'bonus_threshold_met':run['split']=='test' and n*10>=N*9,
        'groups':groups,'errors':sum(t['status']=='error' for t in traces),
        'reviewers':sorted({r['reviewer'] for r in reviews}),
        'note':'AI source review is disclosed; not independent human certification or an instructor grade.',
        'cases':audit}
    write(directory/'evaluation.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);args=parser.parse_args()
    print(json.dumps(score(args.directory),ensure_ascii=True,indent=2))
