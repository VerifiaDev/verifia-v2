"""Bounded research contracts; synthetic labels do not prove model semantics."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest
from test_evidence_grounding import ae, assessment, result
from test_grounding_refinement import frame
from app.evidence import current_research, current_claim_frame, verifier_budget
from app.pipeline import run_pipeline, PipelineConfig
from app.retrieval import LiteRetriever
from app.llm import LLM

CLAIM = 'Nera has a crystalline structure.'
PRIMARY = ['Nera material properties', 'Nera structure measurements']
FALLBACK = ['Nera laboratory report', 'Nera sample analysis', 'Nera original study']


def plan(**kwargs):
    return {**frame('TIMELESS').model_dump(), 'primary_queries': PRIMARY,
            'fallback_queries': FALLBACK, **kwargs}


@pytest.mark.parametrize('fallback', [FALLBACK, FALLBACK * 3, [CLAIM, PRIMARY[0], 'Nera original study']])
def test_query_plan_budget_and_normalized_uniqueness(fallback):
    mod = LiteRetriever(parallel_fetch=False)._mod
    context = plan(fallback_queries=fallback)
    first = mod.generate_queries(CLAIM, context)
    second = mod.research_fallbacks(CLAIM, context)
    assert first[0] == CLAIM.rstrip('.') and PRIMARY[0] in first
    assert len(first) <= 3 and len(second) <= 3 and len(first + second) <= 6
    assert len(mod._research_unique(first + second)) == len(first + second)
    assert mod._research_unique([' Nera   properties ', 'nera properties.', 'NERA properties?']) == ['Nera properties']


def test_multilingual_and_legacy_plan_and_strict_schema():
    mod = LiteRetriever(parallel_fetch=False)._mod
    queries = mod.generate_queries('Nera kristal yapıdadır.', plan(primary_queries=['Nera yapısı', 'Nera material properties']))
    assert queries == ['Nera kristal yapıdadır', 'Nera yapısı', 'Nera material properties']
    assert mod.research_fallbacks(CLAIM, None) == []
    assert mod.generate_queries(CLAIM)[0] == CLAIM.rstrip('.')
    for field, values in [('primary_queries', ['x'] * 3), ('fallback_queries', ['x'] * 4)]:
        with pytest.raises(ae.ValidationError):
            ae.ResearchClaimFrame.model_validate(plan(**{field: values}))
    assert 'arzu edilen hükmü' in ae.EXTRACTION_SYSTEM_PROMPT


def test_cross_language_passage_needs_entire_multitoken_lookup():
    mod = LiteRetriever(parallel_fetch=False)._mod
    assert mod._passage_hint_score('Nera kristal yapıdadır.', 'Neralite material properties describe lattice structure.', ['Neralite material properties']) > .5
    assert mod._passage_hint_score(CLAIM, 'Unrelated material in an archive.', PRIMARY) == 0
    assert mod._passage_hint_score(CLAIM, 'Nera visited a museum.', PRIMARY) == 0


@pytest.mark.parametrize('first,second,weak,expected,calls', [
    ('SUPPORTS', 'CONTRADICTS', False, 'SUPPORTED', (1, 1)),
    ('CONTRADICTS', 'SUPPORTS', False, 'REFUTED', (1, 1)),
    ('CONTEXT', 'CONTRADICTS', False, 'REFUTED', (2, 2)),
    ('IRRELEVANT', 'SUPPORTS', False, 'SUPPORTED', (2, 2)),
    ('CONTEXT', 'CONTEXT', False, 'NOT ENOUGH EVIDENCE', (2, 2)),
    ('IRRELEVANT', 'IRRELEVANT', True, 'NOT ENOUGH EVIDENCE', (2, 1)),
    ('CONTEXT', 'CONTRADICTS', True, 'REFUTED', (2, 1)),
])
def test_adaptive_pipeline(first, second, weak, expected, calls):
    async def go():
        counts = [0, 0]
        async def extract(_):
            return NS(claims=[NS(id='c', text=CLAIM, is_verifiable=True, claim_frame=plan())])
        async def retrieve(_):
            counts[0] += 1
            state = current_research.get()
            state.update(round=counts[0], fallbacks=FALLBACK, quality_weak=weak)
            return [dict(id=f'source_{i+1}', url=f'https://r{i}.example', text='Nera material record') for i in range(counts[0])]
        async def verify(_, sources):
            counts[1] += 1
            direction = first if len(sources) == 1 else second
            entries = [assessment(s['id'], relation=direction if i == len(sources)-1 else 'CONTEXT',
                         strength='STRONG' if direction in ('SUPPORTS','CONTRADICTS') and i == len(sources)-1 else 'NONE')
                       for i, s in enumerate(sources)]
            return result(entries)
        out = (await run_pipeline(CLAIM, extract=extract, retrieve=retrieve, verify=verify))['results'][0]
        assert tuple(counts) == calls and out['verdict'] == expected
        assert out['used_sources'] == ([f'source_{calls[0]}'] if expected != 'NOT ENOUGH EVIDENCE' else [])
        assert len(out['sources']) == calls[0]
        assert current_research.get() is None and verifier_budget.get() is None
    asyncio.run(go())


@pytest.mark.parametrize('mode', ['no_fallback', 'provider_failure', 'timeout', 'invalid', 'conflict'])
def test_stop_and_failure_conditions(mode):
    async def go():
        calls = [0, 0]
        async def extract(_):
            return NS(claims=[NS(id='c', text=CLAIM, is_verifiable=True, claim_frame=plan())])
        async def retrieve(_):
            calls[0] += 1
            if calls[0] == 2:
                if mode == 'provider_failure': raise RuntimeError('provider unavailable')
                if mode == 'timeout': raise asyncio.TimeoutError()
                pytest.fail('Unexpected second wave')
            current_research.get().update(round=1, fallbacks=[] if mode=='no_fallback' else FALLBACK)
            return [dict(id=f'source_{i}', text='Nera record', url=f'https://r{i}.example') for i in (1,2)]
        async def verify(*_):
            calls[1] += 1
            if mode == 'invalid': return result([assessment()])
            if mode == 'conflict': return result([assessment(), assessment('source_2', relation='CONTRADICTS')])
            return result([assessment(f'source_{i}', relation='CONTEXT', strength='NONE') for i in (1,2)])
        out = (await run_pipeline(CLAIM, extract=extract, retrieve=retrieve, verify=verify))['results'][0]
        if mode in ('provider_failure','invalid'):
            assert out['status']=='error' and out['verdict'] is None
        elif mode=='timeout': assert out['status']=='timeout' and out['verdict'] is None
        else: assert out['verdict'] == ('CONFLICTING' if mode=='conflict' else 'NOT ENOUGH EVIDENCE')
        assert calls == ([2,1] if mode in ('provider_failure','timeout') else [1,1])
    asyncio.run(go())


def test_real_lite_two_waves_reuse_documents_and_bound_queries():
    async def go():
        retriever = LiteRetriever(parallel_fetch=False)
        mod = retriever._mod
        state = {}
        queries, fetches = [], []
        def search(client, _on_start=None, **kwargs):
            q = kwargs['query']; queries.append(q)
            if _on_start: _on_start()
            return {'results':[dict(url='https://neutral.example/record', title='Better record' if q in FALLBACK else 'Record',
                                    content='Nera material properties are measured in a laboratory.', score=.9 if q in FALLBACK else .5),
                               dict(url=f'https://new{len(queries)}.example/record', title='Nera record', content='Nera structure measurements show a lattice.',score=.6)]}
        def fetch(url):
            fetches.append(url)
            return 'Nera material properties are measured in a laboratory. Nera structure measurements show a lattice.' * 8
        st = current_research.set(state); ft = current_claim_frame.set(plan())
        try:
            with patch.object(mod, '_get_tavily_client', return_value=object()), patch.object(mod, '_tavily_search', side_effect=search), \
                 patch.object(mod, '_fetch_page', side_effect=fetch), patch.object(mod._tavily_cache, 'enabled', False):
                first = await retriever(CLAIM)
                second = await retriever(CLAIM)
                with pytest.raises(RuntimeError, match='budget'): await retriever(CLAIM)
            assert len(queries) == 6 and len(set(queries)) == 6 and state['round'] == 2
            assert fetches.count('https://neutral.example/record') == 1
            assert len(state['candidates']) <= 2*mod.FETCH_SOURCE_LIMIT*mod.MAX_CHUNKS_PER_SOURCE
            row = state['rows'][mod._canonical_url('https://neutral.example/record')]
            assert row['title'] == 'Better record' and len(row['discovery_queries']) == 6
            assert len({mod._canonical_url(s['url']) for s in second}) == len(second) <= retriever.max_sources
            assert first and second
            assert all(len(s['text'].split()) <= mod.CHUNK_MAX_WORDS for s in second)
        finally:
            current_research.reset(st); current_claim_frame.reset(ft)
    asyncio.run(go())


def test_empty_first_wave_uses_fallback_before_verifier():
    async def go():
        retriever=LiteRetriever(parallel_fetch=False); mod=retriever._mod
        seen=[]
        async def extract(_): return NS(claims=[NS(id='c',text=CLAIM,is_verifiable=True,claim_frame=plan())])
        def search(client, _on_start=None, **kwargs):
            if _on_start: _on_start()
            seen.append(kwargs['query'])
            return {'results': []}
        async def verify(*_): pytest.fail('No evidence to verify')
        with patch.object(mod,'_get_tavily_client',return_value=object()), patch.object(mod,'_tavily_search',side_effect=search), patch.object(mod._tavily_cache,'enabled',False):
            out=(await run_pipeline(CLAIM,extract=extract,retrieve=retriever,verify=verify))['results'][0]
        assert len(seen)==6 and out['verdict']=='NOT ENOUGH EVIDENCE'
    asyncio.run(go())


def test_structural_repair_shared_between_semantic_passes():
    async def go():
        engine=object.__new__(ae.FactCheckEngine)
        responses=[result([]), result([assessment()]), result([])]
        calls=[]
        def generate(*_): calls.append(1); return responses.pop(0)
        engine._generate=generate
        llm=object.__new__(LLM); llm.engine=engine; llm._ae=ae
        token=verifier_budget.set({'attempts':0,'repairs':0})
        try:
            sources=[dict(id='source_1',text='Nera record')]
            await llm.verify(CLAIM,sources)
            with pytest.raises(ae.AssessmentCoverageError): await llm.verify(CLAIM,sources)
            assert len(calls)==3 and verifier_budget.get()['repairs']==1
        finally: verifier_budget.reset(token)
    asyncio.run(go())


def test_second_wave_cancellation_reaches_cooperative_fetch():
    async def go():
        retriever=LiteRetriever(parallel_fetch=False); mod=retriever._mod
        state={'round':1,'fallbacks':FALLBACK,'used_queries':[CLAIM.rstrip('.')], 'candidates':[]}
        started=asyncio.Event(); events=[]
        def detailed(*args, **kwargs):
            events.append(mod._cancellation_event.get())
            loop.call_soon_threadsafe(started.set)
            events[-1].wait(1)
            return {'status':'cancelled','sources':[],'diagnostics':{}}
        loop=asyncio.get_running_loop(); token=current_research.set(state)
        try:
            with patch.object(mod,'search_detailed',side_effect=detailed):
                task=asyncio.create_task(retriever(CLAIM))
                await started.wait(); task.cancel()
                with pytest.raises(asyncio.CancelledError): await task
            assert state['round']==2 and events[0].is_set()
        finally: current_research.reset(token)
    asyncio.run(go())


def test_shared_deadline_prevents_second_wave_provider_calls():
    import time
    mod=LiteRetriever(parallel_fetch=False)._mod
    state={'queries':FALLBACK,'deadline':time.monotonic()-1}
    with patch.object(mod,'_get_tavily_client') as provider:
        out=mod.search_detailed(CLAIM,research_session=state)
    assert out['diagnostics']['timed_out'] and not provider.called


def test_physical_verifier_attempt_budget_includes_provider_fallback():
    import json
    from app.llm import make_engine
    responses=[]
    class Client:
        def __init__(self): self.chat=NS(completions=NS(create=self.create))
        def with_options(self, **kwargs):
            assert kwargs.get('max_retries') in (0,1)
            return self
        def create(self, **kwargs):
            responses.append(kwargs)
            return NS(choices=[NS(message=NS(content=json.dumps(result([assessment()]).model_dump())))])
    def init(engine, **kwargs):
        engine.client=Client(); engine.model_name='test'; engine.temperature=0
    settings=NS(reasoning_effort=None,groq_api_key='test',model_name='test',llm_timeout=1)
    with patch.object(ae.FactCheckEngine,'__init__',init): engine=make_engine(settings)
    token=verifier_budget.set({'attempts':0,'repairs':0})
    try:
        for _ in range(3): engine._generate('','',ae.VerdictResult,'verdict_result')
        with pytest.raises(ae.AssessmentCoverageError): engine._generate('','',ae.VerdictResult,'verdict_result')
        assert len(responses)==3
    finally: verifier_budget.reset(token)


def test_better_later_snippet_replaces_weak_snippet_without_refetch():
    async def go():
        retriever=LiteRetriever(parallel_fetch=False); mod=retriever._mod
        state={}; calls=[]
        def search(client, _on_start=None, **kwargs):
            if _on_start: _on_start()
            later=kwargs['query'] in FALLBACK
            return {'results':[dict(url='https://neutral.example/record', title='Nera record',
              content=('Nera material properties show crystalline structure. ' if later else 'Nera visitors toured the public archive. ')*10,
              score=.9 if later else .2)]}
        def fetch(url): calls.append(url); return ''
        st=current_research.set(state); ft=current_claim_frame.set(plan())
        try:
            with patch.object(mod,'_get_tavily_client',return_value=object()), patch.object(mod,'_tavily_search',side_effect=search), \
                 patch.object(mod,'_fetch_page',side_effect=fetch), patch.object(mod._tavily_cache,'enabled',False):
                await retriever(CLAIM)
                second=await retriever(CLAIM)
            assert len(calls)==1 and 'crystalline' in second[0]['text']
            assert second[0]['metadata']['fetch_method']=='tavily_snippet'
        finally: current_research.reset(st); current_claim_frame.reset(ft)
    asyncio.run(go())
