"""
Rules for ai-engine/ai_engine.py, with the Groq client stubbed (no network, no keys).

1. Extraction does not decide truth: a factual claim that looks false is still returned
   with is_verifiable=true, and nothing between extraction and the /verify result drops it.
2. Citations in the explanation are always "[source_N]" / "[source_1, source_2]" with the
   exact evidence id, and used_sources equals the ids cited.
Run:   python tests/test_ai_engine_rules.py        (or: pytest tests)
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "ai-engine"))

import ai_engine as ae  # noqa: E402
from app.pipeline import PipelineConfig, run_pipeline  # noqa: E402

TEXT = ("Everest Dağı dünyanın en yüksek dağıdır ve Nepal ile Çin sınırında yer alır. "
        "İstanbul Türkiye'nin başkentidir.")
THREE_CLAIMS = [
    {"id": "claim1", "text": "Everest Dağı dünyanın en yüksek dağıdır.", "is_verifiable": True},
    {"id": "claim2", "text": "Everest Dağı Nepal ile Çin sınırında yer alır.", "is_verifiable": True},
    {"id": "claim3", "text": "İstanbul Türkiye'nin başkentidir.", "is_verifiable": True},
]
SOURCES = [ae.Source(id=f"source_{i}", url=f"https://s{i}.test", text=f"kanıt {i}") for i in (1, 2, 3)]

CITATION = re.compile(r"\[([^\[\]]+)\]")
BARE_ID = re.compile(r"(?i)\b(source|kaynak)_\d+\b")


class FakeGroq:
    """Stands in for groq.Groq: returns the queued JSON payloads, records each call."""

    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.calls = []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        content = json.dumps(self.payloads.pop(0), ensure_ascii=False)
        return NS(choices=[NS(message=NS(content=content))])


def engine_with(*payloads):
    eng = ae.FactCheckEngine(api_key="test-key-not-real")
    eng.client = FakeGroq(*payloads)
    return eng


def outside_brackets(text):
    return CITATION.sub("", text)


# ---- 1. extraction keeps false-looking factual claims ---------------------------

def test_extraction_prompt_states_the_no_truth_judgement_principle():
    p = ae.EXTRACTION_SYSTEM_PROMPT
    assert "KARAR VERMEZ" in p
    assert "AYNEN ve is_verifiable=true" in p
    assert "hiçbir cümle atlanmaz" in p
    assert "YALNIZCA öznel yargılar" in p          # false only for opinions / predictions / vague
    assert "tamamen yoksay" not in p, "no rule may tell the model to drop sentences"


def test_prompts_have_no_input_specific_special_cases():
    for p in (ae.EXTRACTION_SYSTEM_PROMPT, ae.VERDICT_SYSTEM_PROMPT):
        assert "Everest" not in p and "İstanbul" not in p and "Istanbul" not in p


def test_three_claims_from_extraction_all_reach_the_verify_result():
    eng = engine_with({"claims": THREE_CLAIMS})
    extraction = eng.extract_claims(TEXT)

    sent = eng.client.calls[0]["messages"]
    assert sent[0]["content"] == ae.EXTRACTION_SYSTEM_PROMPT
    assert TEXT in sent[1]["content"], "the user text must reach the model unchanged"
    assert [(c.text, c.is_verifiable) for c in extraction.claims] == \
        [(c["text"], c["is_verifiable"]) for c in THREE_CLAIMS]

    async def extract(_):
        return extraction

    async def retrieve(_):
        return [{"id": "source_1", "url": "https://s1.test", "text": "kanıt"}]

    async def verify(text, sources):
        return NS(verdict="REFUTED", explanation="Kanıt başka bir şey söylüyor [source_1].",
                  used_sources=["source_1"])

    out = asyncio.run(run_pipeline(TEXT, extract=extract, retrieve=retrieve, verify=verify,
                                   cfg=PipelineConfig(total_timeout=10)))
    assert [r["claim"] for r in out["results"]] == [c["text"] for c in THREE_CLAIMS]
    assert all(r["status"] == "ok" and r["is_verifiable"] for r in out["results"])


# ---- verdict rules ----------------------------------------------------------------

def test_verdict_prompt_defines_refuted_for_a_different_fact_and_keeps_evidence_only_rule():
    p = ae.VERDICT_SYSTEM_PROMPT
    refuted = p.split("- REFUTED:")[1].split("- NOT ENOUGH EVIDENCE:")[0]
    assert "başka türlü" in refuted and "NOT ENOUGH EVIDENCE sayma" in refuted
    assert "Kendi içsel bilgini KESİNLİKLE kullanma" in p


# ---- 2. citations -------------------------------------------------------------------

def test_evidence_block_ids_match_the_prompt_example_format():
    eng = engine_with({"claim_id": "claim3", "verdict": "REFUTED",
                       "explanation": "Kanıt başka bir şehir diyor [source_2].",
                       "used_sources": ["source_2"]})
    eng.verify_claim("İddia metni", SOURCES)
    user = eng.client.calls[0]["messages"][1]["content"]
    block = user.split("Kanıtlar:\n", 1)[1].splitlines()
    assert block == [f"[{s.id}]: {s.text}" for s in SOURCES]
    assert "[source_1]" in ae.VERDICT_SYSTEM_PROMPT and "[source_1, source_2]" in ae.VERDICT_SYSTEM_PROMPT
    assert "[kaynak_id]" not in ae.VERDICT_SYSTEM_PROMPT


def test_messy_citations_are_normalised_and_used_sources_match():
    eng = engine_with({
        "claim_id": "claim3", "verdict": "REFUTED",
        "explanation": "Source_2'de başka bir şehir geçiyor [Kaynak_1]. Ayrıca [source_9] ve [SOURCE_3, source_1].",
        "used_sources": ["source_9", "source_2"],
    })
    res = eng.verify_claim("İddia metni", SOURCES)
    valid = {s.id for s in SOURCES}

    groups = CITATION.findall(res.explanation)
    assert groups, "explanation must keep its citations"
    cited = []
    for g in groups:
        ids = [x.strip() for x in g.split(",")]
        assert g == ", ".join(ids), f"citation must be '[id]' or '[id, id]': [{g}]"
        assert all(i in valid for i in ids), f"unknown id in [{g}]"
        cited += [i for i in ids if i not in cited]
    assert not BARE_ID.search(outside_brackets(res.explanation)), res.explanation
    assert res.used_sources == cited == ["source_2", "source_1", "source_3"]


def test_clean_citations_are_left_unchanged():
    expl = "Kanıt iddianın aksini söylüyor [source_1, source_2]."
    eng = engine_with({"claim_id": "c", "verdict": "REFUTED", "explanation": expl,
                       "used_sources": ["source_1", "source_2"]})
    res = eng.verify_claim("İddia metni", SOURCES)
    assert res.explanation == expl and res.used_sources == ["source_1", "source_2"]


def test_no_citation_means_empty_used_sources():
    eng = engine_with({"claim_id": "c", "verdict": "NOT ENOUGH EVIDENCE",
                       "explanation": "Kanıtlar bu konuda bilgi içermiyor.", "used_sources": ["source_1"]})
    assert eng.verify_claim("İddia metni", SOURCES).used_sources == []


# ---- citation edge cases, checked the way the site parses them (lib/citations.ts) ----

_SITE_GROUP = re.compile(r"\[([^\]]+)\]")
_SITE_ID_LIKE = re.compile(r"^[^\W\d_][^\W_]*_\w+$")


def site_citations(text, valid):
    """Python port of lib/citations.ts: (linked ids, ids the site shows as missing)."""
    linked, missing = [], []
    for m in _SITE_GROUP.finditer(text):
        ids = [x.strip() for x in re.split(r"[,;]\s*", m.group(1)) if x.strip()]
        if ids and all(_SITE_ID_LIKE.match(i) or i in valid for i in ids):
            for i in ids:
                (linked if i in valid else missing).append(i)
    return linked, missing


EDGE_CASES = [
    # (model output, expected explanation, expected cited ids)
    ("Ankara başkenttir [source_1 ve source_2].", "Ankara başkenttir [source_1, source_2].", ["source_1", "source_2"]),
    ("Ankara başkenttir [source_1,].", "Ankara başkenttir [source_1].", ["source_1"]),
    ("Ankara başkenttir [source_1, source_x].", "Ankara başkenttir [source_1].", ["source_1"]),
    ("Ankara başkenttir [kanıt_2].", "Ankara başkenttir [source_2].", ["source_2"]),
    ("Bilgi [nasa_overview] kaynağında.", "Bilgi kaynağında.", []),
    ("Ankara başkenttir [[source_1]].", "Ankara başkenttir [source_1].", ["source_1"]),
    ("Ankara başkenttir [1, 2].", "Ankara başkenttir [source_1, source_2].", ["source_1", "source_2"]),
    ("Bkz. https://ornek.com/source_1 sayfası [source_1].",
     "Bkz. https://ornek.com/source_1 sayfası [source_1].", ["source_1"]),
    ("1923 [2023] yılında [source_1].", "1923 [2023] yılında [source_1].", ["source_1"]),
    ("Metin [sic] böyle [...] [source_2].", "Metin [sic] böyle [...] [source_2].", ["source_2"]),
    ("Bilgi [Source-1] ve [Kaynak 2]; SOURCE_3 de öyle.",
     "Bilgi [source_1] ve [source_2]; [source_3] de öyle.", ["source_1", "source_2", "source_3"]),
    ("Ankara ve İstanbul [Ankara ve İstanbul] [source_3].",
     "Ankara ve İstanbul [Ankara ve İstanbul] [source_3].", ["source_3"]),
    # an id that is not in the evidence is never turned into a link (left as plain text)
    ("Bilgi source_9'da yazıyor.", "Bilgi source_9'da yazıyor.", []),
]


def test_citation_edge_cases_match_what_the_site_links():
    valid = [s.id for s in SOURCES]
    for raw, expected, expected_cited in EDGE_CASES:
        out, cited = ae.normalize_citations(raw, valid)
        assert (out, cited) == (expected, expected_cited), raw
        linked, missing = site_citations(out, valid)
        assert missing == [], f"site would show 'Kaynak eşleşmesi bulunamadı' for {missing}: {out}"
        assert list(dict.fromkeys(linked)) == cited, f"used_sources must equal what the site links: {out}"


def test_extraction_prompt_keeps_a_lone_opinion_and_verdict_prompt_ignores_quote_pages():
    ex = ae.EXTRACTION_SYSTEM_PROMPT
    assert "tek bir görüş cümlesinden oluşsa bile" in ex and "liste boş OLMAZ" in ex
    assert "Boş liste YALNIZCA" in ex
    v = ae.VERDICT_SYSTEM_PROMPT
    assert "KENDİ ADINA" in v and "hiçbir yönde kanıt sayılmaz" in v
    assert "REFUTED'dir, CONFLICTING değil" in v


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
