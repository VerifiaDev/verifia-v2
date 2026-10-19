"""
Passages that come from the search provider's summary (not the fetched page) are labelled
`excerpt_kind: "snippet"`, so the frontend does not show them as a quotation.
Offline: Tavily and the web are faked.
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "retrieval_demo_lite"))

from app.retrieval import LiteRetriever, TavilyRetriever, _mark_snippets  # noqa: E402

CLAIM = "Orion 2024 yılında Atlas pazarında telefon satışlarını yüzde 20 artırdı."


def test_mark_snippets_labels_only_provider_text():
    sources = [
        {"id": "source_1", "metadata": {"fetch_method": "requests"}},
        {"id": "source_2", "metadata": {"fetch_method": "requests_short"}},
        {"id": "source_3", "metadata": {"fetch_method": "tavily_snippet"}},
        {"id": "source_4", "metadata": {"fetch_method": "tavily_pdf_snippet"}},
        {"id": "source_5"},
    ]
    out = _mark_snippets(sources)
    assert [s.get("excerpt_kind") for s in out] == [None, None, "snippet", "snippet", None]


def test_lite_source_from_unfetchable_page_is_a_snippet(monkeypatch):
    # Sequential fetch path: it reads mod._fetch_page at call time, so the fake below applies.
    r = LiteRetriever(max_sources=5, parallel_fetch=False)
    mod = r._mod
    rows = [{"url": "https://site.example.com/haber", "title": "Haber",
             "content": "Orion 2024 yılında Atlas pazarında telefon satışlarını yüzde 20 artırdı, deniyor.",
             "score": 0.9}]
    def search(*, timeout=None, **kw):  # the lite module requires an explicit timeout parameter
        return {"results": rows}

    monkeypatch.setattr(mod, "_get_tavily_client", lambda: NS(search=search))
    monkeypatch.setattr(mod, "_fetch_page", lambda url: "")  # JS-rendered / blocked page: no text

    sources = asyncio.run(r(CLAIM))

    assert sources, "the Tavily summary is still used as evidence"
    assert all(s["metadata"]["fetch_method"].startswith("tavily") for s in sources)
    assert all(s.get("excerpt_kind") == "snippet" for s in sources)


def test_tavily_retriever_always_returns_snippets():
    r = TavilyRetriever.__new__(TavilyRetriever)  # skip __init__: no real client
    r.client = NS(search=lambda **kw: {"results": [
        {"url": "https://a.example.com/1", "title": "A", "content": "kanıt bir", "score": 0.9},
        {"url": "https://b.example.com/2", "title": "B", "content": "kanıt iki", "score": 0.8},
    ]})
    r.depth, r.max_sources, r.max_per_domain, r.snippet_chars = "basic", 5, 2, 1500

    sources = asyncio.run(r(CLAIM))

    assert len(sources) == 2
    assert all(s["excerpt_kind"] == "snippet" for s in sources)
