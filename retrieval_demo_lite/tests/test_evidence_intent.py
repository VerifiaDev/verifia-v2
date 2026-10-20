"""Offline, synthetic regressions for mention-versus-evidence ranking."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import search_retrieval_lite as mod

CLAIM = "Arden ülkesinin başkenti Lora'dır."
FACT = CLAIM + " Ülkenin yönetim kurumları bu şehirde bulunmaktadır."
QUESTION = CLAIM + " Doğru mu yanlış mı? Cevabınızı işaretleyiniz."


class EvidenceIntentTests(unittest.TestCase):
    def intent(self, path='/article', title='Başkent bilgisi', text=FACT):
        return mod._evidence_intent('https://unlisted.example' + path, title, text)

    def test_path_only_and_normalization(self):
        for path in ('/soru-cozum/12', '/soru_cozum/12', '/ödev/12',
                     '/doğru-mu-yanlış-mı', '/%C3%B6dev/12', '/homework/12'):
            with self.subTest(path=path):
                self.assertEqual(self.intent(path=path), (.04, ['question_path']))
        self.assertEqual(self.intent(path='/contest/testing-methods'), (0, []))

    def test_title_only(self):
        self.assertEqual(self.intent(title='Doğru mu yanlış mı?'), (.10, ['exercise_title']))
        self.assertEqual(self.intent(title='Hangisi başkenttir?'), (.04, ['question_title']))

    def test_text_only(self):
        for text in (QUESTION, 'Aşağıdaki cümlelerin doğru veya yanlış olduğunu yazınız: ' + CLAIM,
                     'Soru: ' + CLAIM, 'Choose the correct answer: ' + CLAIM):
            with self.subTest(text=text):
                self.assertEqual(self.intent(text=text), (.14, ['exercise_text']))

    def test_combined_bounded_and_not_keyword_counted(self):
        penalty, flags = self.intent('/quiz', 'Doğru mu yanlış mı?', QUESTION)
        self.assertEqual(penalty, .25)
        self.assertEqual(len(flags), 3)
        self.assertGreater(penalty, self.intent(text=QUESTION)[0])
        self.assertEqual(self.intent(text=QUESTION * 20), self.intent(text=QUESTION))

    def test_explanatory_question_title(self):
        self.assertEqual(self.intent(title="Arden'in başkenti neden Lora'dır?"),
                         (.02, ['question_mark_title']))

    def test_ordinary_and_quoted_counter_evidence(self):
        self.assertEqual(self.intent(), (0, []))
        self.assertEqual(self.intent(text='"' + CLAIM + '" iddiası yanlıştır.'), (0, []))
        # Domain and quoted claim alone carry no intent signal.
        self.assertEqual(mod._evidence_intent('https://homework.example/article',
                                             'İddianın incelenmesi', '"' + CLAIM + '"'), (0, []))

    def test_structural_path_categories(self):
        for path in ('/sorucevap/', '/soru-cevap/', '/soru_cevap/', '/soru/cozum/',
                     '/questions/', '/question-answer/', '/questionanswer/',
                     '/sorucozum/', '/exercises/', '/tests/'):
            with self.subTest(path=path):
                self.assertEqual(self.intent(path=path), (.04, ['question_path']))

    def test_classification_and_instruction_categories(self):
        title = '"' + CLAIM + '" cümlesi nesnel yargı mı öznel yargı mıdır?'
        self.assertEqual(self.intent(title=title), (.10, ['exercise_title']))
        self.assertEqual(self.intent(text=title), (.14, ['exercise_text']))
        for text in ('Nesnel mi öznel mi?', 'Hangisi doğrudur?', 'Hangisi yanlıştır?',
                     'Cümleleri sınıflandırınız.', 'Kelimeleri eşleştiriniz.',
                     'Boşluğu doldurunuz.',
                     'Aşağıdaki cümleleri doğru veya yanlış olarak işaretleyiniz.'):
            with self.subTest(text=text):
                self.assertEqual(self.intent(text=text), (.14, ['exercise_text']))
        self.assertEqual(self.intent(text='Nesnel ve öznel yargı kavramları burada açıklanmaktadır.'), (0, []))
        penalty, flags = self.intent('/questionanswer/', title, title)
        self.assertEqual(penalty, .25)
        self.assertTrue(set(flags).isdisjoint({'supported', 'refuted', 'true', 'false'}))

    def test_canonical_page_uniqueness_and_best_chunk(self):
        template = self.candidates()[0]
        rows = [dict(template, url='https://reference.example/page#one', text='low', retrieval_score=.5),
                dict(template, url='https://REFERENCE.example/page/?utm_source=test', text='best', retrieval_score=.9),
                dict(template, url='https://reference.example/page', text='tie', retrieval_score=.9),
                dict(template, url='https://reference.example/other', text='other', retrieval_score=.8)]
        selected = mod._select_diverse(rows, 5)
        self.assertEqual([c['text'] for c in selected], ['best', 'other'])
        self.assertEqual(len({mod._canonical_url(c['url']) for c in selected}), 2)
        sources = mod._sources_from_selected(selected)
        self.assertEqual([s['id'] for s in sources], ['source_1', 'source_2'])
        self.assertEqual(mod._select_diverse(rows, 5), selected)

    def test_duplicate_chunks_do_not_crowd_out_other_pages(self):
        template = self.candidates()[0]
        rows = [dict(template, retrieval_score=.9)] * 35
        rows.append(dict(template, url='https://reference.example/other', retrieval_score=.7))
        self.assertEqual(len(mod._select_diverse(rows, 5)), 2)

    def test_classification_page_ranks_below_assertion(self):
        exercise = '"' + CLAIM + '" cümlesi nesnel yargı mı öznel yargı mıdır?'
        rows = [dict(url='https://unknown.example/questionanswer/', title=exercise,
                     body=exercise, search_score=.99),
                dict(url='https://reference.example/article', title='Arden başkent bilgisi',
                     body=FACT, search_score=.85)]
        with patch.object(mod, '_source_text', side_effect=lambda row, fetched: (row['body'], 'tavily_snippet')):
            candidates = mod._build_candidates_batch(CLAIM, rows)[0]
        self.assertEqual(candidates[0]['domain'], 'reference.example')
        self.assertEqual(candidates[1]['evidence_intent_penalty'], .25)

    def test_partial_snapshot_has_one_best_chunk_per_page(self):
        template = dict(self.candidates()[0], fetch_method='requests')
        candidates = [dict(template, retrieval_score=.7), dict(template, retrieval_score=.9)]
        state = dict(pages={}, diagnostics={}, snapshot=[], max_sources=5)
        token = mod._partial_state.set(state)
        try:
            with patch.object(mod, '_build_candidates_batch', return_value=(candidates,
                              dict(requests_sources=1, snippet_sources=0))):
                mod._process_ready_page(CLAIM, {}, 0)
            self.assertEqual(len(state['snapshot']), 1)
            self.assertEqual(state['snapshot'][0]['retrieval_score'], .9)
        finally:
            mod._partial_state.reset(token)

    def test_single_channels_and_counter_evidence_remain_eligible(self):
        cases = [dict(), dict(title='Başkent bilgisi?'),
                 dict(title="Arden ülkesinin başkenti neden Mira'dır?"),
                 dict(path='/questions/'), dict(title='Hangisi başkenttir?'),
                 dict(title=QUESTION), dict(text=QUESTION),
                 dict(text='"' + CLAIM + '" iddiası yanlıştır.'), dict(text=CLAIM * 3),
                 dict(path='/quiz/', title='Başkent bilgisi?')]
        for case in cases:
            with self.subTest(case=case):
                _, flags = self.intent(**case)
                quality = mod._evidence_quality(flags)
                self.assertTrue(quality['evidence_eligible'])
                candidate = dict(self.candidates()[0], **quality,
                                 evidence_intent_flags=flags)
                self.assertEqual(len(mod._select_diverse([candidate], 5)), 1)

    def test_strong_combinations_are_ineligible_independent_of_score(self):
        for case in (dict(path='/quiz/', title=QUESTION),
                     dict(title=QUESTION, text=QUESTION),
                     dict(path='/questions/', text=QUESTION)):
            with self.subTest(case=case):
                _, flags = self.intent(**case)
                quality = mod._evidence_quality(flags)
                self.assertEqual(quality, dict(evidence_intent_level='strong_exercise', evidence_eligible=False))
                candidate = dict(self.candidates()[0], **quality, retrieval_score=1)
                self.assertEqual(mod._select_diverse([candidate], 5), [])
        # Repeating one channel cannot turn it into independent corroboration.
        self.assertTrue(mod._evidence_quality(['exercise_text'] * 3)['evidence_eligible'])

    def test_quality_threshold_beats_quota_and_preserves_candidates(self):
        from copy import deepcopy
        factual, exercise = self.candidates()
        for count in (0, 2, 4):
            rows = [dict(factual, url=f'https://reference.example/page/{i}') for i in range(count)]
            rows += [dict(exercise, url=f'https://unknown.example/quiz/{i}', retrieval_score=1) for i in range(6)]
            before = deepcopy(rows)
            for maximum in (1, 3, 5):
                selected = mod._select_diverse(rows, maximum)
                self.assertEqual(len(selected), min(count, maximum))
                self.assertTrue(all(c['evidence_eligible'] for c in selected))
                self.assertEqual(selected, mod._select_diverse(rows, maximum))
            self.assertEqual(rows, before)

    def test_ineligible_chunk_does_not_hide_eligible_chunk_on_same_page(self):
        factual, exercise = self.candidates()
        exercise = dict(exercise, url=factual['url'], retrieval_score=1)
        self.assertEqual(mod._select_diverse([exercise, factual], 5)[0]['text'], factual['text'])

    def test_timeout_snapshot_excludes_exercises(self):
        factual, exercise = [dict(c, fetch_method='requests') for c in self.candidates()]
        def interrupted_search(*args, **kwargs):
            for i, candidate in enumerate((factual, exercise)):
                with patch.object(mod, '_build_candidates_batch', return_value=([candidate],
                                  dict(requests_sources=1, snippet_sources=0))):
                    mod._process_ready_page(CLAIM, {}, i)
            # Snapshot must be independent of later candidate mutations.
            factual['text'] = 'mutated after commit'
            raise mod._RetrievalTimeout('fetch')
        with patch.object(mod, '_search_detailed_impl', side_effect=interrupted_search):
            result = mod.search_detailed(CLAIM, 5)
        self.assertTrue(result['diagnostics']['partial_result'])
        self.assertEqual(len(result['sources']), 1)
        self.assertEqual(result['sources'][0]['text'], FACT)

    def test_weak_quality_metadata_and_stance_neutral_levels(self):
        factual = self.candidates()[0]
        flags = ['question_mark_title']
        candidate = dict(factual, evidence_intent_flags=flags, evidence_intent_penalty=.02,
                         **mod._evidence_quality(flags))
        meta = mod._sources_from_selected([candidate])[0]['metadata']
        self.assertTrue(meta['evidence_eligible'])
        self.assertEqual(meta['evidence_intent_level'], 'weak_question')
        self.assertEqual(mod._evidence_quality([])['evidence_intent_level'], 'normal')

    def test_public_search_returns_fewer_sources_and_keeps_candidate_diagnostics(self):
        for count in (0, 2, 4):
            rows = [dict(url=f'https://reference.example/page/{i}', title='Başkent bilgisi',
                         search_score=.85, body=FACT) for i in range(count)]
            rows.append(dict(url='https://unknown.example/quiz', title=QUESTION,
                             search_score=.99, body=QUESTION))
            with patch.object(mod, '_search_web', return_value=(rows, [])), \
                 patch.object(mod, '_source_text', side_effect=lambda row, fetched: (row['body'], 'tavily_snippet')):
                result = mod.search_detailed(CLAIM, 5)
                self.assertEqual(len(result['sources']), count)
                self.assertEqual(result['diagnostics']['candidate_count'], count + 1)
                self.assertEqual(mod.search(CLAIM, 5), result['sources'])
                self.assertEqual(result['status'], 'evidence_found' if count else 'quality_filtered_empty')

    def candidates(self):
        rows = [dict(url='https://unknown.example/quiz', title=CLAIM + ' Doğru mu yanlış mı?',
                     search_score=.99, body=QUESTION),
                dict(url='https://reference.example/article', title='Arden başkent bilgisi',
                     search_score=.85, body=FACT)]
        with patch.object(mod, '_source_text', side_effect=lambda row, fetched: (row['body'], 'tavily_snippet')):
            return mod._build_candidates_batch(CLAIM, rows)[0]

    def test_high_overlap_question_ranks_below_assertion_and_is_retained(self):
        candidates = self.candidates()
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]['domain'], 'reference.example')
        question = candidates[1]
        self.assertGreaterEqual(question['lexical_score'], candidates[0]['lexical_score'])
        selected = mod._sources_from_selected(mod._select_diverse(candidates, 2))
        self.assertEqual(selected[0]['domain'], 'reference.example')
        self.assertNotIn('evidence_intent_penalty', selected[0]['metadata'])
        self.assertEqual(len(selected), 1)
        self.assertEqual(question['evidence_intent_penalty'], .25)
        self.assertFalse(question['evidence_eligible'])
        self.assertEqual(mod._select_diverse([question], 1), [])

    def test_unflagged_score_unchanged_and_adjustment_exact(self):
        for candidate in self.candidates():
            base = (mod.LEXICAL_WEIGHT * candidate['lexical_score']
                    + mod.SEARCH_WEIGHT * candidate['search_score']
                    + mod.STRUCTURAL_WEIGHT * candidate['structural_score'])
            self.assertAlmostEqual(candidate['retrieval_score'],
                                   max(0, min(1, base - candidate['evidence_intent_penalty'])))


if __name__ == '__main__':
    unittest.main(verbosity=2)
