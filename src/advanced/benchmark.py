"""Gold-free runtime inputs; offline evidence validation is a separate command."""
from collections import Counter
from .common import ROOT, DATA, PDF, read, sha

BENCH = ROOT/'benchmark/advanced'


def load_inputs(split):
    if split not in ('dev','test'):
        raise ValueError('Invalid split')
    rows=read(BENCH/'inputs'/f'{split}.json')
    if not isinstance(rows,list) or not rows:
        raise ValueError('Expected nonempty input list')
    seen=set()
    for row in rows:
        if set(row)!={'id','question'} or not isinstance(row['id'],str) or not isinstance(row['question'],str) or not row['question'].strip() or row['id'] in seen:
            raise ValueError('Runtime inputs may contain only unique ID and question')
        seen.add(row['id'])
    return rows


def validate():
    manifest=read(BENCH/'manifest.json')
    for path,expected in manifest['sha256'].items():
        if sha(ROOT/path)!=expected:raise ValueError('Frozen advanced asset changed: '+path)
    index=read(DATA/'index.json')
    if len(index)<100 or {r['page'] for r in index}!=set(range(1,len(index)+1)):
        raise ValueError('Index must cover all physical pages')
    seen=set();facts=set();summary={}
    for split,minimum in [('dev',(15,3)),('test',(24,6))]:
        rows=read(BENCH/f'{split}.json');safe=load_inputs(split)
        if safe!=[{'id':r['id'],'question':r['question']} for r in rows]:raise ValueError('Input projection mismatch')
        counts=Counter()
        for row in rows:
            if row['id'] in seen or row['split']!=split or type(row['answerable']) is not bool:raise ValueError('Invalid case')
            if row['fact_key'] in facts:raise ValueError('Repeated fact across benchmark')
            facts.add(row['fact_key']);seen.add(row['id']);counts[row['group']]+=1
            if row['answerable']:
                if row['group']=='unanswerable' or not row['gold'] or not row['expected_answer']:raise ValueError('Missing evidence')
                if row['group']=='multi_hop' and len({g['page'] for g in row['gold']})<2:raise ValueError('Multi-hop needs multiple pages')
                for evidence in row['gold']:
                    if not 1<=evidence['page']<=len(index) or len(evidence['bbox'])!=4 or not evidence['description'] or not evidence['region']:
                        raise ValueError('Missing page/region evidence')
                    box=evidence['bbox']
                    if not (0<=box[0]<box[2]<=1 and 0<=box[1]<box[3]<=1):raise ValueError('Bad bbox')
                    if sha(ROOT/index[evidence['page']-1]['image'])!=evidence['page_image_sha256']:
                        raise ValueError('Evidence image changed')
            elif row['group']!='unanswerable' or row['gold'] or not row['absence_reason'] or not row['absence_check']:
                raise ValueError('Missing absence review')
        if sum(v for k,v in counts.items() if k!='unanswerable')<minimum[0] or counts['unanswerable']<minimum[1]:raise ValueError('Too few cases')
        if split=='test':
            for key,n in {'table':6,'image':5,'chart':5,'multi_hop':4,'text':4}.items():
                if counts[key]<n:raise ValueError('Missing test group coverage')
        summary[split]=dict(counts)
    return {'status':'validated','counts':summary,'pages_indexed':len(index),'cases':len(seen),'gold_at_runtime':False}


if __name__=='__main__':
    print(validate())
