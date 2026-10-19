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


if __name__ == "__main__":
    unittest.main()
