"""
Shared fixtures for the API-level tests: the real FastAPI app with a fake LLM and
a fake retriever plugged into `app.main.state` (no network, no keys, no lifespan).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))


class FakeBackend:
    """Behaviour is chosen per claim by keywords in the claim text:
         BOZUK    retrieval raises          KARARSIZ  verdict step raises
         ASILI    retrieval hangs           KAYNAKSIZ no sources found
    """

    def __init__(self) -> None:
        self.claims = [
            NS(id="c1", text="Ankara Türkiye'nin başkentidir.", is_verifiable=True),
            NS(id="c2", text="Bence kahve güzeldir.", is_verifiable=False),
            NS(id="c3", text="İstanbul Türkiye'nin başkentidir.", is_verifiable=True),
        ]
        self.extract_error: Exception | None = None
        self.extract_delay = 0.0
        self.retrieve_delay = 0.0
        self.explanation = "Kaynaklar bunu doğruluyor [source_1]."
        self.used_sources = ["source_1", "source_99"]  # source_99 is hallucinated on purpose
        self.calls = {"extract": 0, "retrieve": 0, "verify": 0}
        self.retrieve_started = 0
        self.retrieve_cancelled = 0

    def set_claims(self, *items):
        self.claims = [NS(id=f"c{i + 1}", text=t, is_verifiable=v) for i, (t, v) in enumerate(items)]

    # --- the three injected steps ---------------------------------------
    async def extract(self, text):
        self.calls["extract"] += 1
        if self.extract_delay:
            await asyncio.sleep(self.extract_delay)
        if self.extract_error:
            raise self.extract_error
        return NS(claims=list(self.claims))

    async def retrieve(self, text):
        self.calls["retrieve"] += 1
        self.retrieve_started += 1
        try:
            if "ASILI" in text:
                await asyncio.sleep(999)
            await asyncio.sleep(self.retrieve_delay)
        except asyncio.CancelledError:
            self.retrieve_cancelled += 1
            raise
        if "BOZUK" in text:
            raise RuntimeError("tavily exploded")
        if "KAYNAKSIZ" in text:
            return []
        return [
            {"id": "source_1", "title": "Haber 1", "domain": "a.example.com", "url": "https://a.example.com/1",
             "published_date": "2024-05-01", "text": "kanıt 1"},
            {"id": "source_2", "title": "Haber 2", "domain": "b.example.com", "url": "https://b.example.com/2",
             "published_date": None, "text": "kanıt 2"},
        ]

    async def verify(self, text, sources):
        self.calls["verify"] += 1
        if "KARARSIZ" in text:
            raise ValueError("groq 500")
        verdict = "REFUTED" if "İstanbul" in text else "SUPPORTED"
        return NS(verdict=verdict, explanation=self.explanation, used_sources=list(self.used_sources))


@pytest.fixture
def fake(monkeypatch):
    from app import main

    fb = FakeBackend()
    llm = NS(extract=fb.extract, verify=fb.verify)
    monkeypatch.setitem(main.state, "llm", llm)
    monkeypatch.setitem(main.state, "retriever", fb.retrieve)
    monkeypatch.setitem(main.state, "cache", None)
    monkeypatch.setitem(main.state, "init_error", None)
    from app.limits import UpstreamGate

    monkeypatch.setattr(main, "upstream", UpstreamGate(8))  # fresh per test (counters, in-flight calls)
    cfg = main.settings.pipeline
    for k, v in dict(max_claims=8, claim_concurrency=4, extract_timeout=5.0, claim_timeout=5.0,
                     total_timeout=10.0, expose_detail=True).items():
        monkeypatch.setattr(cfg, k, v)
    return fb


@pytest.fixture
def client(fake):
    from fastapi.testclient import TestClient

    from app import main

    # no `with`: the lifespan (which would build the real Groq/Tavily clients) does not run
    return TestClient(main.app)
