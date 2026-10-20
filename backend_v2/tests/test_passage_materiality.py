"""Lightweight passage selection and claim-relative applicability regressions."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest
from test_evidence_grounding import ae, assessment, result
from app.retrieval import LiteRetriever
from app.pipeline import run_pipeline
from test_grounding_refinement import frame


@pytest.mark.parametrize('context,dimension,strong', [
    (frame('HISTORICAL'), 'metric', True),
    (frame('HISTORICAL', metric='annual revenue'), 'metric', False),
    (frame('TIMELESS'), 'temporal', True),
    (frame('CURRENT'), 'temporal', False),
    (frame('EVENT'), 'temporal', False),
    (frame('HISTORICAL'), 'temporal', False),
    (frame('TIMELESS', explicit_time='1990'), 'temporal', False),
    (frame('EVENT'), 'scope', True),
    (frame('EVENT', scope='total population'), 'scope', False),
    (frame('EVENT', predicate='reported speech'), 'modality', False),
    (frame('TIMELESS', predicate='depicted in a work'), 'modality', False),
    (frame('EVENT'), 'entity', False),
    (frame('EVENT'), 'predicate', False),
    (None, 'metric', False),
    ({}, 'scope', False),
])
def test_material_unknown_pairs(context, dimension, strong):
    out = ae.normalize_assessments(result([assessment(**{dimension: 'UNKNOWN'})]), ['source_1'], context)
    assert out.source_assessments[0].strength == ('STRONG' if strong else 'LIMITED')
    assert out.used_sources == (['source_1'] if strong else [])
    assert out.source_assessments[0].compatibility.model_dump()[dimension] == 'UNKNOWN'


def test_material_mismatch_stays_limited_and_no_frame_is_conservative():
    assert all(ae.compatibility_materiality().values())
    out = ae.normalize_assessments(result([assessment(metric='MISMATCH')]), ['source_1'], frame(metric='rate'))
    assert out.verdict == 'NOT ENOUGH EVIDENCE'


def test_pipeline_revalidation_and_frontend_metadata_agree_on_materiality():
    async def go():
        async def extract(_):
            return NS(claims=[NS(id='c', text='Nera opened in 1990.', is_verifiable=True,
                                 claim_frame=frame('HISTORICAL', explicit_time='1990'))])
        async def retrieve(_):
            return [{'id':'source_1', 'url':'https://neutral.example', 'text':'Nera opened in 1990.'}]
        async def verify(*_):
            return ae.normalize_assessments(result([assessment(metric='UNKNOWN', scope='UNKNOWN')]),
                                            ['source_1'], frame('HISTORICAL', explicit_time='1990'))
        out = (await run_pipeline('input', extract=extract, retrieve=retrieve, verify=verify))['results'][0]
        assert out['verdict'] == 'SUPPORTED' and out['used_sources'] == ['source_1']
        assert out['compatibility_materiality'] == dict(entity=True, temporal=True, predicate=True,
                                                       scope=False, metric=False, modality=True)
    asyncio.run(go())


CLAIM = 'Nera is made from ceramic.'
HINT = 'Nera material properties'
PROPERTY = 'Nera material properties describe a crystalline structure and measured physical characteristics of the sample.'
UNRELATED = 'Nera visitors arrived at the building and reviewed photographs of journeys and public ceremonies in the archive.'
EXACT = 'Nera is made from ceramic. The technical record explicitly identifies the material used for the complete item.'


def candidates(mod, chunks, hints=None):
    row = dict(url='https://neutral.example/reference', title='Nera reference', search_score=.7,
               discovery_queries=[HINT] if hints else [])
    with patch.object(mod, '_source_text', return_value=(' '.join(chunks), 'requests')), \
         patch.object(mod, '_chunk_text', return_value=chunks):
        return mod._build_candidates_batch(CLAIM, [row])[0]


def test_property_hint_finds_correct_passage_beyond_chunk_limit():
    mod = LiteRetriever(parallel_fetch=False)._mod
    chunks = [f'Nera visitor archive section {i}.' for i in range(20)] + [PROPERTY]
    old = mod._select_diverse(candidates(mod, chunks), 1)
    assert old[0]['text'] != PROPERTY
    selected = mod._select_diverse(candidates(mod, chunks, hints=True), 1)
    assert selected[0]['text'] == PROPERTY
    assert len(mod._sources_from_selected(selected)) == 1


def test_exact_claim_passage_still_wins():
    mod = LiteRetriever(parallel_fetch=False)._mod
    selected = mod._select_diverse(candidates(mod, [UNRELATED, PROPERTY, EXACT], hints=True), 1)
    assert selected[0]['text'] == EXACT


def test_frame_hint_and_focus_choose_the_property_sentence():
    mod = LiteRetriever(parallel_fetch=False)._mod
    token = mod._passage_frame.set(frame('TIMELESS', neutral_search_hints=[HINT]).model_dump())
    try:
        hints = mod._passage_hints(CLAIM, {})
        assert HINT in hints
        text = ' '.join([UNRELATED] * 6 + [PROPERTY] + [UNRELATED] * 2)
        assert PROPERTY in mod._focus(CLAIM, text, hints=hints)
    finally:
        mod._passage_frame.reset(token)


def test_single_query_word_or_unanchored_document_cannot_boost():
    mod = LiteRetriever(parallel_fetch=False)._mod
    assert mod._passage_hint_score(CLAIM, 'Nera opened its archive to visitors.', [HINT]) == 0
    assert mod._passage_hint_score(CLAIM, 'Material properties of unrelated objects.', [HINT]) == 0
    ordinary = candidates(mod, [UNRELATED])[0]
    hinted = candidates(mod, [UNRELATED], hints=True)[0]
    assert ordinary['retrieval_score'] == hinted['retrieval_score']
    assert ordinary['passage_score'] == hinted['passage_score']
    good = candidates(mod, [EXACT])[0]
    assert mod._select_diverse([good, {**hinted, 'url':'https://other.example'}], 1)[0]['text'] == EXACT


def test_hint_bonus_only_selects_within_page_not_document_rank():
    mod = LiteRetriever(parallel_fetch=False)._mod
    property_plain = candidates(mod, [PROPERTY])[0]
    property_hinted = candidates(mod, [PROPERTY], hints=True)[0]
    assert property_hinted['passage_score'] > property_plain['passage_score']
    assert property_hinted['retrieval_score'] == property_plain['retrieval_score']


def test_query_provenance_merges_canonical_duplicates_without_extra_calls():
    mod = LiteRetriever(parallel_fetch=False)._mod
    queries = [CLAIM.rstrip('.'), HINT, 'Nera technical specification']
    calls = []
    def search(client, _on_start=None, **kwargs):
        calls.append(kwargs['query'])
        if _on_start: _on_start()
        return {'results':[{'url':'https://neutral.example/page?query='+str(len(calls)),
                            'title':'Nera', 'content':PROPERTY, 'score':.8}]}
    with patch.object(mod, 'generate_queries', return_value=queries), \
         patch.object(mod, '_get_tavily_client', return_value=object()), \
         patch.object(mod, '_tavily_search', side_effect=search), \
         patch.object(mod._tavily_cache, 'enabled', False):
        rows, used = mod._search_web(CLAIM)
    assert calls == used == queries and len(rows) == 1
    assert rows[0]['discovery_queries'] == queries
    assert len(mod.generate_queries(CLAIM, frame(neutral_search_hints=[HINT,'Nera technical specification']).model_dump())) <= 3


def test_frame_context_cleanup_and_provenance_survive_public_output():
    mod = LiteRetriever(parallel_fetch=False)._mod
    row = dict(url='https://neutral.example', title='Nera reference', search_score=.7,
               content=PROPERTY, discovery_queries=[HINT])
    with patch.object(mod, '_search_web', return_value=([row], [HINT])), \
         patch.object(mod, '_source_text', return_value=(PROPERTY, 'tavily_snippet')):
        out = mod.search(CLAIM, claim_frame=frame(neutral_search_hints=[HINT]).model_dump())
    assert out[0]['metadata']['discovery_queries'] == [HINT]
    assert mod._passage_frame.get() is None
