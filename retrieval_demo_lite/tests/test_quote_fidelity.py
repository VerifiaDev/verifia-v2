"""Offline quote-fidelity tests: a passage taken from a page must appear in the text a reader sees.

Each case gives the HTML and the visible text a browser shows. The passage the lite module
builds (_html_to_text -> _chunk_text -> _focus) must be found in that visible text after
whitespace / Unicode normalisation, so a reader can find it on the page with Ctrl+F.
"""
import re
import sys
import unicodedata
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "retrieval_demo_lite"))
import search_retrieval_lite as mod  # noqa: E402

CLAIM = "Ankara'da 5 milyon kişi yaşıyor."


def visible(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def passages(html):
    text = mod._html_to_text(html)
    chunks = mod._chunk_text(text) or [text]
    return [mod._focus(CLAIM, chunk) for chunk in chunks]


class QuoteFidelity(unittest.TestCase):
    def assert_found(self, html, seen):
        for passage in passages(html):
            self.assertIn(visible(passage), visible(seen))

    def test_inline_tags_add_no_spaces(self):
        html = ("<article><p>Ankara<b>'da</b> 5 <a href='#'>milyon</a> kişi yaşıyor. "
                "Şehir 1923'ten beri başkenttir.</p></article>")
        self.assert_found(html, "Ankara'da 5 milyon kişi yaşıyor. Şehir 1923'ten beri başkenttir.")

    def test_block_boundaries_still_separate_words(self):
        html = "<article><p>Birinci paragraf burada bitiyor.</p><p>İkinci paragraf başlıyor.</p><ul><li>bir</li><li>iki</li></ul></article>"
        self.assertEqual(mod._html_to_text(html),
                         "Birinci paragraf burada bitiyor. İkinci paragraf başlıyor. bir iki")

    def test_line_break_separates_words(self):
        self.assertEqual(mod._html_to_text("<article><p>satır bir<br>satır iki</p></article>"),
                         "satır bir satır iki")

    def test_soft_hyphen_is_removed(self):
        text = mod._html_to_text("<article><p>Ankara'da&nbsp;5&nbsp;milyon kişi ya&shy;şıyor.</p></article>")
        self.assertNotIn("­", text)
        self.assertIn("Ankara'da 5 milyon kişi yaşıyor.", text)

    def test_abbreviation_does_not_start_a_new_sentence(self):
        text = "Dr. Ayşe Kaya açıkladı. Ankara'da 5 milyon kişi yaşıyor. Prof. Dr. Ali Can da doğruladı."
        self.assertEqual(mod._sentences(text), [
            "Dr. Ayşe Kaya açıkladı.",
            "Ankara'da 5 milyon kişi yaşıyor.",
            "Prof. Dr. Ali Can da doğruladı.",
        ])

    def test_abbreviation_passage_keeps_the_speaker(self):
        html = ("<article><p>Dr. Ayşe Kaya açıkladı. Ankara'da 5 milyon kişi yaşıyor. "
                "Nüfus her yıl artıyor. Bu veri resmidir. Kaynak TÜİK.</p></article>")
        self.assertTrue(any(p.startswith("Dr. Ayşe Kaya") for p in passages(html)), passages(html))

    def test_every_top_level_article_is_read(self):
        html = ("<body><article><p>Eski haber: hava güzel ve bugün yağmur yok efendim.</p></article>"
                "<article><p>Ankara'da 5 milyon kişi yaşıyor. Güncel veri budur ve doğrudur.</p></article></body>")
        self.assertIn("Ankara'da 5 milyon kişi yaşıyor.", mod._html_to_text(html))

    def test_nested_article_is_not_duplicated(self):
        html = "<article><p>Dış metin.</p><article><p>İç metin.</p></article></article>"
        self.assertEqual(mod._html_to_text(html), "Dış metin. İç metin.")

    def test_removed_tags_stay_removed(self):
        html = "<body><nav>Menü</nav><main><p>Ana içerik.</p><script>x=1</script></main><footer>Alt</footer></body>"
        self.assertEqual(mod._html_to_text(html), "Ana içerik.")


class AdjacentFidelity(unittest.TestCase):
    def test_nested_inline_punctuation_and_links_preserve_continuity(self):
        cases = [
            ('<p>Ne<span><strong>ra</strong></span>\'nın <em>kaydı</em>.</p>', "Nera'nın kaydı."),
            ('<p>pre<a href="#"><i>fix</i></a> and <span>two</span> words</p>', 'prefix and two words'),
            ('<p>(<em>Nera</em>)<b>,</b> kayıt<span>!</span></p>', '(Nera), kayıt!'),
            ('<p>one <b> two </b> three</p>', 'one two three'),
        ]
        for html, expected in cases:
            with self.subTest(html=html):
                self.assertEqual(mod._html_to_text(html), expected)

    def test_visible_boundaries_and_removed_content(self):
        html = ('<main><h2>Başlık</h2><section><div>Bir<br/>İki</div>'
                '<ul><li>Üç</li><li>Dört</li></ul></section>'
                '<table><tr><th>Ad</th><th>Değer</th></tr><tr><td>Nera</td><td>5</td></tr></table>'
                '<script>BAD_SCRIPT</script><style>BAD_STYLE</style><nav>BAD_NAV</nav>'
                '<footer>BAD_FOOTER</footer><!-- BAD_COMMENT --></main>')
        self.assertEqual(mod._html_to_text(html), 'Başlık Bir İki Üç Dört Ad Değer Nera 5')

    def test_article_roots_document_order_and_fallbacks(self):
        cases = [
            ('<body>outside<article>A<section><article>B</article></section>C</article><div><article>D</article></div></body>', 'A B C D'),
            ('<body>outside<main><p>main</p></main>after</body>', 'main'),
            ('<body><p>body</p><p>next</p></body>', 'body next'),
            ('<span>fragment</span><div>next</div>', 'fragment next'),
        ]
        for html, expected in cases:
            with self.subTest(html=html):
                self.assertEqual(mod._html_to_text(html), expected)

    def test_only_soft_hyphen_removed_and_unicode_punctuation_preserved(self):
        self.assertEqual(mod._html_to_text('<p>Ne&shy;<b>ra</b>&nbsp;A-B – C—D “x”’y</p>'),
                         'Nera A-B – C—D “x”’y')

    def test_title_chains_decimals_and_real_boundaries(self):
        cases = [
            ('Dr. Nera açıkladı. Yeni kayıt geldi!', ['Dr. Nera açıkladı.', 'Yeni kayıt geldi!']),
            ('Prof. Nera ölçtü. Bitti.', ['Prof. Nera ölçtü.', 'Bitti.']),
            ('Prof. Dr. Nera 3.14 ölçtü. Sonuç 2.5 oldu.', ['Prof. Dr. Nera 3.14 ölçtü.', 'Sonuç 2.5 oldu.']),
            ('Doç. Dr. Nera geldi. Mr. Vale left. Mrs. Zed stayed.', ['Doç. Dr. Nera geldi.', 'Mr. Vale left.', 'Mrs. Zed stayed.']),
            ('Uzm. Nera geldi? Evet! Son.', ['Uzm. Nera geldi?', 'Evet!', 'Son.']),
            ('Normal son. Başlangıç. etc. Next.', ['Normal son.', 'Başlangıç.', 'etc.', 'Next.']),
            ('A literal <DOT> stays. Done.', ['A literal <DOT> stays.', 'Done.']),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(mod._sentences(text), expected)

    def test_many_articles_still_use_existing_candidate_and_source_bounds(self):
        from unittest.mock import patch
        html = ''.join(f'<article><p>Nera record {i} describes measured physical properties of this sample.</p></article>' for i in range(80))
        text = mod._html_to_text(html)
        self.assertIn('record 79', text)
        rows = [dict(url='https://synthetic.example/record', title='Nera record', content='', search_score=.7)]
        with patch.object(mod, '_source_text', return_value=(text, 'requests')):
            candidates, _ = mod._build_candidates_batch('Nera measured properties', rows)
        self.assertLessEqual(len(candidates), mod.MAX_CHUNKS_PER_SOURCE)
        selected = mod._select_diverse(candidates, 2)
        self.assertEqual(len(selected), 1)
        self.assertTrue(all(len(c['text'].split()) <= mod.CHUNK_MAX_WORDS for c in candidates))


if __name__ == "__main__":
    unittest.main()
