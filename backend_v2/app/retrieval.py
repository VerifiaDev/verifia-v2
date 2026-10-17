"""
retrieval.py
------------
Three interchangeable retrievers (RETRIEVER=lite | tavily | arda). All are async callables:

    sources = await retriever(claim_text)   # -> list[dict]

Every source dict has: id, url, text  (+ title, domain, published_date,
retrieval_score for the frontend) - the same shape the old backend produced.

  * LiteRetriever (default): Arda's optimised `retrieval_demo_lite` module
    (multi-query Tavily search, page download with plain `requests`,
    sentence chunking, lexical + structural ranking, diverse selection).
    No torch, no browser. This adapter only adds parallel page downloads.

  * TavilyRetriever: ONE Tavily search, uses the snippets Tavily
    already extracts. No page downloads, no browser, no ML models.
    Typical latency: 1-3 seconds, and it needs ~100 MB of RAM.

  * ArdaRetriever: wraps Arda's OLD full pipeline (page
    download + embeddings + cross-encoder). Better evidence selection in
    theory, but needs torch + sentence-transformers and is much slower.
    Kept so the two can be compared on the same claims.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

log = logging.getLogger("verify.retrieval")


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


class TavilyRetriever:
    name = "tavily"

    def __init__(
        self,
        api_key: str,
        depth: str = "basic",
        max_sources: int = 5,
        max_per_domain: int = 2,
        snippet_chars: int = 1500,
    ):
        from tavily import TavilyClient  # imported lazily so tests don't need it

        self.client = TavilyClient(api_key=api_key)
        self.depth = depth
        self.max_sources = max_sources
        self.max_per_domain = max_per_domain
        self.snippet_chars = snippet_chars

    def _search(self, claim_text: str) -> list:
        resp = self.client.search(
            query=claim_text[:380],  # Tavily rejects queries over 400 chars
            search_depth=self.depth,
            max_results=self.max_sources + 4,
            include_raw_content=False,
        )
        results = resp.get("results", []) if isinstance(resp, dict) else []
        results = sorted(results, key=lambda r: float(r.get("score") or 0.0), reverse=True)

        out: list = []
        seen_urls: set = set()
        per_domain: dict = {}
        for r in results:
            url = (r.get("url") or "").strip()
            text = " ".join((r.get("content") or "").split())
            if not url or not text:
                continue
            key = url.split("#")[0].rstrip("/")
            domain = _domain(url)
            if key in seen_urls or per_domain.get(domain, 0) >= self.max_per_domain:
                continue
            seen_urls.add(key)
            per_domain[domain] = per_domain.get(domain, 0) + 1
            out.append(
                {
                    "id": f"source_{len(out) + 1}",
                    "title": (r.get("title") or "").strip() or domain or "Kaynak",
                    "url": url,
                    "domain": domain,
                    "published_date": r.get("published_date"),
                    "retrieval_score": round(float(r.get("score") or 0.0), 4),
                    "text": text[: self.snippet_chars],
                }
            )
            if len(out) >= self.max_sources:
                break
        return out

    async def __call__(self, claim_text: str) -> list:
        return await asyncio.to_thread(self._search, claim_text)


class ArdaRetriever:
    name = "arda"

    def __init__(self, max_sources: int = 5):
        try:
            import search_retrieval
        except ImportError:
            repo = Path(__file__).resolve().parents[2]
            sys.path.insert(0, str(repo / "search-retrieval"))
            import search_retrieval  # noqa: F811
        self._search = search_retrieval.search
        self.max_sources = max_sources

    async def __call__(self, claim_text: str) -> list:
        return await asyncio.to_thread(self._search, claim_text, self.max_sources)


class LiteRetriever:
    """Adapter for retrieval_demo_lite/search_retrieval_lite.py (not modified).

    The lite module downloads up to FETCH_SOURCE_LIMIT pages ONE AFTER ANOTHER
    (8 s timeout each). This adapter wraps two of its internal functions so the
    downloads for one claim run in parallel threads instead. Nothing in the
    lite file is edited, so `git pull` keeps working. If a future version of
    the lite module renames those functions, the wrapper is skipped (with a
    warning) and the module still works, just slower.
    """

    name = "lite"

    def __init__(self, max_sources: int = 5, parallel_fetch: bool = True, workers: int = 8):
        try:
            import search_retrieval_lite as mod
        except ImportError:
            repo = Path(__file__).resolve().parents[2]
            sys.path.insert(0, str(repo / "retrieval_demo_lite"))
            import search_retrieval_lite as mod  # noqa: F811
        self._mod = mod
        self.max_sources = max_sources
        self.parallel_fetch = False
        if parallel_fetch:
            self.parallel_fetch = self._install_parallel_fetch(workers)

    def _install_parallel_fetch(self, workers: int) -> bool:
        mod = self._mod
        needed = ("_fetch_page", "_build_candidates", "_is_pdf", "FETCH_SOURCE_LIMIT")
        if not all(hasattr(mod, n) for n in needed) or getattr(mod, "_verify_parallel", False):
            if not getattr(mod, "_verify_parallel", False):
                log.warning("lite module changed shape; parallel fetch NOT installed")
            return getattr(mod, "_verify_parallel", False)

        orig_fetch = mod._fetch_page
        orig_build = mod._build_candidates
        prefetched: contextvars.ContextVar = contextvars.ContextVar("lite_prefetched", default=None)

        def fetch(url):
            pre = prefetched.get()
            if pre is not None and url in pre:
                return pre[url]
            return orig_fetch(url)

        def build(claim_text, rows):
            urls = []
            for r in rows[: mod.FETCH_SOURCE_LIMIT]:
                u = r.get("url") or ""
                if u and not mod._is_pdf(u) and u not in urls:
                    urls.append(u)
            pages = {}
            if urls:
                with ThreadPoolExecutor(max_workers=min(workers, len(urls))) as pool:
                    for u, text in zip(urls, pool.map(orig_fetch, urls)):
                        pages[u] = text
            token = prefetched.set(pages)
            try:
                return orig_build(claim_text, rows)
            finally:
                prefetched.reset(token)

        mod._fetch_page = fetch
        mod._build_candidates = build
        mod._verify_parallel = True
        return True

    async def __call__(self, claim_text: str) -> list:
        return await asyncio.to_thread(self._mod.search, claim_text, self.max_sources)


def build_retriever(settings) -> object:
    if settings.retriever == "arda":
        return ArdaRetriever(max_sources=settings.max_sources)
    if settings.retriever == "lite":
        return LiteRetriever(max_sources=settings.max_sources)
    return TavilyRetriever(
        api_key=settings.tavily_api_key,
        depth=settings.tavily_depth,
        max_sources=settings.max_sources,
    )
