"""Offline core evaluation; explicit --verifier --allow-network opts into Groq.
Gold stance/verdict metadata is never passed to either evaluated component.
"""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, datetime
import hashlib
from html import escape
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import socket
import statistics
import sys
from urllib.parse import urlparse
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DATA = HERE / 'data/turkish_core_eval.jsonl'
sys.path.insert(0, str(ROOT / 'retrieval_demo_lite'))
import search_retrieval_lite as lite
LABELS = ('SUPPORTED','REFUTED','NOT_ENOUGH_EVIDENCE','CONFLICTING')
MAPPING = {v: v.replace('_',' ') if v=='NOT_ENOUGH_EVIDENCE' else v for v in LABELS}
RELEVANCE = {'irrelevant':0,'partially_relevant':1,'relevant':2}


def validate(cases):
    assert len(cases)>=32, 'at least 32 cases required'
    assert len({c['id'] for c in cases})==len(cases), 'duplicate case id'
    for c in cases:
        assert c['claim'].strip() and c['category'].strip()
        assert c['expected_verdict'] in LABELS
        assert c['difficulty'] in ('easy','medium','hard')
        assert isinstance(c['tags'],list) and isinstance(c['notes'],str)
        evidence=c['evidence'];assert evidence
        assert len({e['source_id'] for e in evidence})==len(evidence)
        assert len({e['url'] for e in evidence})==len(evidence)
        for e in evidence:
            assert all(isinstance(e[k],str) and e[k].strip() for k in ('source_id','title','text','domain','published_date'))
            url=urlparse(e['url'])
            assert url.scheme=='https' and url.hostname and (url.hostname=='example.test' or url.hostname.endswith('.example.test'))
            assert not url.username and not url.password and url.port is None
            assert url.hostname==e['domain'] and url.path
            assert date.fromisoformat(e['published_date']).isoformat()==e['published_date']
            assert e['source_type'] in ('primary','official','secondary','aggregator')
            assert e['relevance_label'] in RELEVANCE
            assert e['stance'] in ('supports','refutes','neutral')
            assert type(e['provider_score']) in (int,float) and 0<=e['provider_score']<=1
        strong=[e for e in evidence if e['relevance_label']=='relevant' and e['source_type'] in ('primary','official')]
        stances={e['stance'] for e in strong}
        verdict=c['expected_verdict']
        if verdict=='SUPPORTED': assert 'supports' in stances and 'refutes' not in stances
        if verdict=='REFUTED': assert 'refutes' in stances and 'supports' not in stances
        if verdict=='CONFLICTING': assert {'supports','refutes'}<=stances and len(strong)>=2
        if verdict=='NOT_ENOUGH_EVIDENCE': assert all(e['stance']=='neutral' for e in evidence)
    return dict(passed=True,total_cases=len(cases),
                semantic_scope='Automated schema/stance consistency; text meaning and same-scope contradictions are manually authored/reviewed, not machine-proven.')


def validation_negative_tests(cases):
    mutations=[lambda c:c[1].update(id=c[0]['id']),lambda c:c[0].update(claim=''),
               lambda c:c[0]['evidence'][0].update(url='http://real.example/'),
               lambda c:c[0]['evidence'][0].update(published_date='2025-02-30'),
               lambda c:c[0].update(expected_verdict='CONFLICTING'),
               lambda c:c[16]['evidence'][0].update(stance='supports')]
    for mutate in mutations:
        bad=deepcopy(cases);mutate(bad)
        try:validate(bad)
        except (AssertionError,ValueError):continue
        raise AssertionError('invalid fixture accepted')
    return len(mutations)


class Response:
    status_code=200
    headers={'Content-Type':'text/html'}
    encoding='utf-8'
    def __init__(self,text):self.body=('<article>'+escape(text)+'</article>').encode()
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def raise_for_status(self):pass
    def iter_content(self,chunk_size):
        for i in range(0,len(self.body),chunk_size):yield self.body[i:i+chunk_size]


def dcg(grades):return sum((2**g-1)/math.log2(i+2) for i,g in enumerate(grades))


def retrieval(case):
    # Only non-gold provider fields enter the real pipeline.
    by_url={e['url']:e for e in case['evidence']}
    class Client:
        def search(self,query,timeout=5,**params):
            return {'results':[dict(url=e['url'],title=e['title'],content=e['text'],
                                    published_date=e['published_date'],score=e['provider_score'])
                               for e in case['evidence']]}
    def get(session,url,**kwargs):
        assert session.trust_env is False and kwargs['stream'] and not kwargs['allow_redirects']
        return Response(by_url[url]['text'])
    cache=lite._TavilyQueryCache();cache.enabled=False
    with patch.object(lite,'_tavily_cache',cache),patch.object(lite,'_get_tavily_client',return_value=Client()), \
         patch.object(lite.socket,'getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))]), \
         patch.object(lite.requests.Session,'get',get):
        result=lite.search_detailed(case['claim'],max_sources=5)
    assert not result['diagnostics']['timed_out'] and not result['diagnostics']['cancelled']
    sources=result['sources'];seen=set();unique=[]
    for s in sources:
        if s['url'] not in seen:unique.append(s);seen.add(s['url'])
    grades=[RELEVANCE[by_url[s['url']]['relevance_label']] for s in unique]
    relevant=sum(e['relevance_label']=='relevant' for e in case['evidence'])
    ideal=sorted([RELEVANCE[e['relevance_label']] for e in case['evidence']],reverse=True)[:5]
    domains={s['domain'] for s in sources};n=len(sources)
    return dict(id=case['id'],category=case['category'],difficulty=case['difficulty'],sources=sources,
        metrics=dict(recall_at_5=sum(g==2 for g in grades)/relevant if relevant else None,
            precision_at_5=sum(g==2 for g in grades)/5,
            mrr=next((1/(i+1) for i,g in enumerate(grades) if g==2),0),
            ndcg_at_5=dcg(grades)/dcg(ideal) if dcg(ideal) else None,
            irrelevant_evidence_rate=sum(by_url[s['url']]['relevance_label']=='irrelevant' for s in sources)/n if n else 0,
            primary_official_source_rate=sum(by_url[s['url']]['source_type'] in ('primary','official') for s in sources)/n if n else 0,
            unique_domain_count=len(domains),duplicate_domain_rate=(n-len(domains))/n if n else 0,
            selected_count=n),fetch_methods=dict(Counter(s['metadata']['fetch_method'] for s in sources)))


def aggregate(runs):
    return {k:statistics.mean(vals) if (vals:=[r['metrics'][k] for r in runs if r['metrics'][k] is not None]) else None
            for k in runs[0]['metrics']}


def classification_metrics(expected,predicted):
    matrix={a:{b:0 for b in LABELS} for a in LABELS}
    for a,b in zip(expected,predicted):matrix[a][b]+=1
    per={}
    for label in LABELS:
        tp=matrix[label][label];actual=sum(matrix[label].values());pred=sum(matrix[a][label] for a in LABELS)
        p=tp/pred if pred else 0;r=tp/actual if actual else 0
        per[label]=dict(precision=p,recall=r,f1=2*p*r/(p+r) if p+r else 0)
    return dict(accuracy=sum(a==b for a,b in zip(expected,predicted))/len(expected),
                macro_f1=statistics.mean(v['f1'] for v in per.values()),per_class=per,confusion_matrix=matrix)


def verifier(cases,runs,args):
    skip=lambda reason:dict(status='skipped',message='verifier evaluation skipped',reason=reason,metrics=None)
    if not args.verifier:return skip('retrieval-only; verifier requires real Groq network')
    if not args.allow_network:return skip('explicit --allow-network required, even if credentials exist')
    if not os.getenv('GROQ_API_KEY'):return skip('GROQ_API_KEY unavailable in environment')
    try:
        spec=importlib.util.spec_from_file_location('core_eval_ai_engine',ROOT/'ai-engine/ai_engine.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    except ImportError:return skip('verifier dependencies unavailable')
    unsupported=[v for v in LABELS if MAPPING[v] not in module.VALID_VERDICTS]
    if unsupported:return dict(status='skipped',reason='unsupported verifier label',labels=unsupported,metrics=None)
    engine=module.FactCheckEngine();predictions=[]
    reverse={v:k for k,v in MAPPING.items()}
    for c,run in zip(cases,runs):
        evidence=run['sources'] if args.verifier_input=='retrieved' else c['evidence']
        srcs=[module.Source(id=e.get('source_id',e.get('id')),url=e['url'],text=e['text']) for e in evidence]
        try:answer=engine.verify_claim(c['claim'],srcs)
        except Exception:return dict(status='incomplete',reason='verifier call failed; no raw exception logged',completed_count=len(predictions),metrics=None)
        if answer.verdict not in reverse:return dict(status='incomplete',reason='unsupported returned verdict',metrics=None)
        predictions.append(reverse[answer.verdict])
    return dict(status='completed',input=args.verifier_input,model=engine.model_name,predictions=predictions,
                metrics=classification_metrics([c['expected_verdict'] for c in cases],predictions))


def main():
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--retrieval-only',action='store_true');mode.add_argument('--verifier',action='store_true')
    parser.add_argument('--allow-network',action='store_true')
    parser.add_argument('--verifier-input',choices=['fixture','retrieved'],default='fixture')
    parser.add_argument('--output',type=Path,default=HERE/'benchmark_results_turkish_core.json')
    args=parser.parse_args()
    protected=[ROOT/'retrieval_demo_lite/search_retrieval_lite.py',*sorted((ROOT/'backend_v2/app').glob('*.py')),
               *sorted((ROOT/'ai-engine').glob('*.py')),HERE/'benchmark_retrieval_quality.py',HERE/'benchmark_results_retrieval_quality.json']
    hashes=lambda:{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    before=hashes();cases=[json.loads(line) for line in DATA.read_text().splitlines() if line.strip()]
    validation=validate(cases);validation['negative_tests_passed']=validation_negative_tests(cases)
    runs=[retrieval(c) for c in cases]
    # Repeat offline retrieval to verify stability, without invoking a fake verifier.
    repeat=[retrieval(c) for c in cases]
    assert [r['sources'] for r in runs]==[r['sources'] for r in repeat]
    v=verifier(cases,runs,args)
    report=dict(dataset=dict(path=str(DATA.relative_to(ROOT)),sha256=hashlib.sha256(DATA.read_bytes()).hexdigest(),
                synthetic=True,canonical_to_implementation=MAPPING),total_cases=len(cases),
                verdict_distribution=dict(Counter(c['expected_verdict'] for c in cases)),
                category_distribution=dict(Counter(c['category'] for c in cases)),
                difficulty_distribution=dict(Counter(c['difficulty'] for c in cases)),
                methodology='Fixed candidate pool; real Lite query/fetch/ranking, mocked Tavily/DNS/HTTP, cache off. Gold verdict/stance/relevance excluded from provider inputs. Macro metrics; P@5 denominator=5; recall excludes no-relevant cases; MRR includes them as zero. URL-dedup ranks for recall/P@5/MRR/nDCG; evidence-item rates for irrelevant/source/domain metrics. No live web or truth accuracy claim.',
                retrieval_metrics=aggregate(runs),
                per_category={k:aggregate([r for r in runs if r['category']==k]) for k in sorted({c['category'] for c in cases})},
                per_difficulty={k:aggregate([r for r in runs if r['difficulty']==k]) for k in ('easy','medium','hard')},
                raw_results=runs,verifier=v,validation=validation,deterministic_repeat_equal=True,
                evaluation_timestamp=datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(),
                environment=dict(python=sys.version,platform=platform.platform()),protected_hashes=before)
    assert hashes()==before;report['production_and_stress_unchanged']=True
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('total_cases','verdict_distribution','difficulty_distribution','retrieval_metrics','verifier','validation')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
