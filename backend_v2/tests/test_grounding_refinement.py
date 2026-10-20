"""General refinement contracts. Stubbed semantic labels are not live model evidence."""
import asyncio
import json
from threading import Event
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest
import ai_engine as ae
from app.evidence import current_claim_frame
from app.llm import LLM
from app.limits import UpstreamGate
from app.pipeline import run_pipeline, TTLCache
from app.retrieval import LiteRetriever
from test_evidence_grounding import assessment, result


def frame(mode='UNKNOWN', **values):
    return ae.ClaimFrame(subject='Nera', predicate='durum', object=None, explicit_time=None,
                        temporal_mode=mode, scope=None, metric=None, neutral_search_hints=[]).model_copy(update=values)


def engine_with(*responses):
    engine=object.__new__(ae.FactCheckEngine)
    calls=[]
    def generate(system, prompt, schema, name):
        calls.append((system,json.loads(prompt.split('\n',1)[1])))
        response=responses[len(calls)-1]
        if isinstance(response,BaseException): raise response
        return response.model_copy(deep=True)
    engine._generate=generate
    return engine,calls


SOURCES=[ae.Source(id=f'source_{i}',text=f'Nötr pasaj {i}',published_date='1990-01-01') for i in [1,2]]


def complete(): return result([assessment(),assessment('source_2','CONTEXT','NONE')])


def test_happy_path_one_call_and_genuine_weak_is_nee():
    response=result([assessment(relation='CONTEXT',strength='NONE'),assessment('source_2','SUPPORTS','LIMITED')])
    engine,calls=engine_with(response)
    out=engine.verify_claim('Nötr iddia',SOURCES)
    assert out.verdict=='NOT ENOUGH EVIDENCE' and out.used_sources==[] and len(calls)==1


@pytest.mark.parametrize('bad', [result([assessment()]),result([assessment(),assessment()])])
def test_missing_or_duplicate_assessment_repairs_once_with_same_evidence(bad):
    engine,calls=engine_with(bad,complete())
    out=engine.verify_claim('Nötr iddia',SOURCES,claim_frame=frame('CURRENT'))
    assert out.verdict=='SUPPORTED' and out.used_sources==['source_1']
    assert len(calls)==2 and calls[0][1]==calls[1][1]
    assert 'HER kimlik' in calls[1][0] and 'AYNI kanıtları' in calls[1][0]


def test_incomplete_repair_is_claim_failure_and_not_cached():
    async def go():
        engine,calls=engine_with(result([assessment()]),result([assessment()]))
        async def extract(_): return NS(claims=[NS(id='c',text='Nötr iddia',is_verifiable=True)])
        async def retrieve(_): return [s.model_dump() for s in SOURCES]
        async def verify(text,sources): return engine.verify_claim(text,[ae.Source(**s) for s in sources])
        cache=TTLCache()
        out=await run_pipeline('x',extract=extract,retrieve=retrieve,verify=verify,cache=cache)
        r=out['results'][0]
        assert r['status']=='error' and r['error_code']=='VERDICT_FAILED'
        assert r['verdict'] is None and r['used_sources']==[]
        assert len(calls)==2 and len(cache)==0
    asyncio.run(go())


def test_structurally_incomplete_response_is_repairable_but_provider_error_is_not():
    with pytest.raises(ae.ValidationError) as exc:
        ae.VerdictResult.model_validate({'claim_id':'c'})
    engine,calls=engine_with(exc.value,complete())
    assert engine.verify_claim('Nötr iddia',SOURCES).verdict=='SUPPORTED' and len(calls)==2
    engine,calls=engine_with(RuntimeError('provider unavailable'))
    with pytest.raises(RuntimeError): engine.verify_claim('Nötr iddia',SOURCES)
    assert len(calls)==1


def test_pipeline_boundary_rejects_incomplete_alternative_verifier():
    async def go():
        async def extract(_): return NS(claims=[NS(id='c',text='İddia',is_verifiable=True)])
        async def retrieve(_): return [s.model_dump() for s in SOURCES]
        async def verify(*_): return result([assessment()])
        r=(await run_pipeline('x',extract=extract,retrieve=retrieve,verify=verify))['results'][0]
        assert r['status']=='error' and r['error_code']=='VERDICT_FAILED' and r['verdict'] is None
    asyncio.run(go())


def test_cancellation_of_sync_verifier_prevents_followup_repair():
    async def go():
        entered,release,finished=Event(),Event(),Event()
        engine,calls=engine_with(result([assessment()]),complete())
        original=engine._generate
        def blocked(*args):
            entered.set();release.wait(2)
            return original(*args)
        engine._generate=blocked
        original_verify=engine.verify_claim
        def observe(*args,**kwargs):
            try: return original_verify(*args,**kwargs)
            finally: finished.set()
        engine.verify_claim=observe
        llm=object.__new__(LLM);llm._ae=ae;llm.engine=engine
        task=asyncio.create_task(llm.verify('Nötr iddia',[s.model_dump() for s in SOURCES]))
        try:
            for _ in range(1000):
                if entered.is_set(): break
                await asyncio.sleep(.001)
            assert entered.is_set()
            task.cancel()
            with pytest.raises(asyncio.CancelledError): await task
        finally: release.set()
        for _ in range(1000):
            if finished.is_set(): break
            await asyncio.sleep(.001)
        assert finished.is_set() and len(calls)==1
    asyncio.run(go())


def test_frame_extraction_is_internal_strict_and_optional():
    schema=ae._FramedExtractionResult.model_json_schema()
    for obj in [schema,*schema['$defs'].values()]:
        if obj.get('type')=='object':
            assert obj['additionalProperties'] is False
            assert set(obj['required'])==set(obj['properties'])
    engine=object.__new__(ae.FactCheckEngine)
    seen=[]
    def generate(system,prompt,model,name):
        seen.append(model)
        return model.model_validate({'claims':[dict(id='c',text='Nera bir maddedir.',is_verifiable=True,
                                                   claim_frame={**frame('TIMELESS').model_dump(), 'primary_queries': [], 'fallback_queries': []})]})
    engine._generate=generate
    out=engine.extract_claims('Nera bir maddedir.')
    assert len(seen)==1 and out.claims[0].claim_frame.temporal_mode=='TIMELESS'
    assert ae.Claim(id='c',text='legacy',is_verifiable=True)
    null=ae._FramedClaim(id='c',text='unknown',is_verifiable=True,claim_frame=None)
    assert null.claim_frame is None
    with pytest.raises(ae.ValidationError):
        ae.ClaimFrame.model_validate({**frame().model_dump(),'neutral_search_hints':['a','b','c']})
    for text in ['Bilgi uydurma','istenen hükmü kodlama','karşı iddiaları','KARAR VERME','UNKNOWN']:
        assert text in ae.EXTRACTION_SYSTEM_PROMPT


QUERY_CASES=[
    ('Nera silikattan oluşur.',frame('TIMELESS',predicate='bileşim',object='silikat',neutral_search_hints=['Nera kimyasal bileşimi','Nera malzeme özellikleri'])),
    ('Nera merkezinin yöneticisi Denizdir.',frame('CURRENT',predicate='yönetici',object='Deniz',neutral_search_hints=['Nera merkezi yönetimi'])),
    ('Nera merkezi 1990 yılında açıldı.',frame('HISTORICAL',predicate='açılış',explicit_time='1990',neutral_search_hints=['Nera merkezinin 1990 açılışı'])),
    ('Nera tesisi açıldı.',frame('EVENT',predicate='açılış',neutral_search_hints=['Nera tesisi açılış durumu'])),
    ('Nera geliri 10 milyon birimdir.',frame('UNKNOWN',predicate='gelir',object='10 milyon',metric='yıllık gelir',neutral_search_hints=['Nera yıllık gelir verileri'])),
]


@pytest.mark.parametrize('claim,context',QUERY_CASES)
def test_neutral_queries_preserve_exact_claim_and_bounded_diversity(claim,context):
    mod=LiteRetriever(parallel_fetch=False)._mod
    queries=mod.generate_queries(claim,context.model_dump())
    assert queries[0]==claim.rstrip('.?!')
    assert context.neutral_search_hints[0] in queries
    assert len(queries)<=3 and len(queries)==len(mod._unique(queries))


def test_query_fallback_dedup_property_lookup_and_configured_cap():
    mod=LiteRetriever(parallel_fetch=False)._mod
    base='Nera silikattan oluşur'
    old=mod.generate_queries(base)
    assert old==mod.generate_queries(base,None)==mod.generate_queries(base,{})
    context=frame('TIMELESS',predicate='bileşim',object='silikat',neutral_search_hints=[base,base.upper()]).model_dump()
    queries=mod.generate_queries(base,context)
    assert queries[0]==base and 'Nera bileşim' in queries
    assert len(queries)==len(mod._unique(queries))
    with patch.object(mod,'MAX_QUERY_COUNT',1): assert mod.generate_queries(base,context)==[base]
    with patch.object(mod,'MAX_QUERY_COUNT',20): assert len(mod.generate_queries(base,context))<=3


TEMPORAL_CASES=[
    ('CURRENT','1990 yılında Deniz yöneticiydi.','UNKNOWN','LIMITED'),
    ('HISTORICAL','1990 yılında Deniz yöneticiydi.','MATCH','STRONG'),
    ('EVENT','Aynı kişinin başka bir kurumdaki eski anlaşması tamamlandı.','MISMATCH','LIMITED'),
    ('EVENT','Anlaşma yapılacağı söylentileri var.','UNKNOWN','LIMITED'),
    ('CURRENT','Yeni yayımlanan yazı önceki dönemin yönetimini anlatıyor.','UNKNOWN','LIMITED'),
    ('TIMELESS','Maddenin bileşimi ölçüldü.','NOT_APPLICABLE','STRONG'),
]


@pytest.mark.parametrize('mode,passage,temporal,expected',TEMPORAL_CASES)
def test_stubbed_temporal_pairs_and_explicit_verifier_input(mode,passage,temporal,expected):
    context=frame(mode,explicit_time='1990' if mode=='HISTORICAL' else None)
    engine,calls=engine_with(result([assessment(temporal=temporal)]))
    source=ae.Source(id='source_1',text=passage,published_date='2026-01-01')
    out=engine.verify_claim('Nera hakkında iddia',[source],claim_frame=context)
    data=calls[0][1]
    assert data['claim_frame']==context.model_dump()
    assert data['sources'][0]['published_date']=='2026-01-01' and data['sources'][0]['text']==passage
    assert data['reference_time'] and out.source_assessments[0].strength==expected
    assert out.used_sources==(['source_1'] if expected=='STRONG' else [])
    for rule in ['Olay kimliği/zamanı','UNKNOWN kullan, MATCH varsayma','Yakın tarihli yayın eski',
                 'güncel durum','tarihsel durum','duyuru','tamamlanmış olay','önceki FARKLI']:
        assert rule in calls[0][0]


def test_frame_propagation_context_cleanup_and_cache_identity():
    async def go():
        cache=TTLCache(); observations=[];mode=['CURRENT'];calls=[]
        async def extract(_):
            return NS(claims=[NS(id='c',text='Aynı iddia',is_verifiable=True,claim_frame=frame(mode[0]))])
        async def retrieve(_):
            observations.append(current_claim_frame.get())
            return [SOURCES[0].model_dump()]
        async def verify(*_):
            observations.append(current_claim_frame.get());calls.append(1)
            return result([assessment()])
        for value in ['CURRENT','CURRENT','HISTORICAL']:
            mode[0]=value
            out=await run_pipeline('x',extract=extract,retrieve=retrieve,verify=verify,cache=cache)
            assert out['results'][0]['status']=='ok'
        assert len(calls)==2
        assert [o['temporal_mode'] for o in observations]==['CURRENT','CURRENT','CURRENT','HISTORICAL','HISTORICAL']
        assert current_claim_frame.get() is None
    asyncio.run(go())


def test_frame_reaches_lite_and_llm_without_public_callable_signature_change():
    async def go():
        context=frame('HISTORICAL',explicit_time='1990').model_dump()
        token=current_claim_frame.set(context)
        try:
            retriever=LiteRetriever(parallel_fetch=False)
            with patch.object(retriever._mod,'search_detailed',return_value={'status':'not_enough_evidence','sources':[],'diagnostics':{}}) as search:
                assert await retriever('İddia')==[]
                assert search.call_args.kwargs['claim_frame']==context
            llm=object.__new__(LLM);llm._ae=ae
            llm.engine,calls=engine_with(result([assessment()]))
            await llm.verify('İddia',[SOURCES[0].model_dump()])
            assert calls[0][1]['claim_frame']==context
        finally:current_claim_frame.reset(token)
    asyncio.run(go())


def test_inflight_frames_are_isolated_for_search_and_verification():
    async def go():
        gate=UpstreamGate(8);calls=[]
        async def upstream(*_):
            calls.append(current_claim_frame.get()['temporal_mode'])
            await asyncio.sleep(.01)
            return current_claim_frame.get()['temporal_mode']
        for is_verify,wrapper in [(False,gate.retrieve(upstream)),(True,gate.verify(upstream))]:
            async def invoke(mode,is_verify):
                token=current_claim_frame.set(frame(mode).model_dump())
                try:return await wrapper('same',[]) if is_verify else await wrapper('same')
                finally:current_claim_frame.reset(token)
            values=await asyncio.gather(*(invoke(m,is_verify) for m in ['CURRENT','HISTORICAL','CURRENT']))
            assert values==['CURRENT','HISTORICAL','CURRENT']
        assert calls==['CURRENT','HISTORICAL','CURRENT','HISTORICAL']
    asyncio.run(go())
