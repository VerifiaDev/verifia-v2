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
import os
import sys
import time
from threading import Event
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

log = logging.getLogger("verify.retrieval")


_lite_workers = contextvars.ContextVar("lite_invocation_workers", default=None)


def _validated_workers(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value or len(value) > 16 or not value.isascii() or not value.isdecimal():
            return None
        value = int(value)
    if not isinstance(value, int) or value <= 0:
        return None
    return min(value, 8)


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _mark_snippets(sources: list) -> list:
    """Label passages that come from the search provider's summary, not the page itself.

    The frontend shows such passages without quotation marks (`excerpt_kind: "snippet"`).
    Page-text passages keep their shape unchanged.
    """
    for source in sources:
        method = (source.get("metadata") or {}).get("fetch_method") or ""
        if method.startswith("tavily"):
            source["excerpt_kind"] = "snippet"
    return sources


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
                    "excerpt_kind": "snippet",  # Tavily's extracted summary, never fetched page text
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
    """Run Lite page fetches in parallel with the claim's cooperative deadline.

    Each worker receives a separate context copy. Deadline expiry stops waiting
    and cancels queued work, but cannot kill running DNS/network calls.
    """

    name = "lite"

    def __init__(self, max_sources: int = 5, parallel_fetch: bool = True, workers: Optional[int] = None):
        try:
            import search_retrieval_lite as mod
        except ImportError:
            repo = Path(__file__).resolve().parents[2]
            sys.path.insert(0, str(repo / "retrieval_demo_lite"))
            import search_retrieval_lite as mod  # noqa: F811
        self._mod = mod
        self.workers = (_validated_workers(workers)
                        or _validated_workers(os.getenv("LITE_FETCH_WORKERS")) or 4)
        self.max_sources = max_sources
        self.parallel_fetch = False
        if parallel_fetch:
            self.parallel_fetch = self._install_parallel_fetch()

    def _install_parallel_fetch(self) -> bool:
        mod = self._mod
        needed = ("_fetch_page", "_build_candidates", "_is_pdf", "FETCH_SOURCE_LIMIT", "_remaining",
                  "_partial_state", "_process_ready_page", "_merge_candidate_pages")
        if not all(hasattr(mod, n) for n in needed) or getattr(mod, "_verify_parallel", False):
            if not getattr(mod, "_verify_parallel", False):
                log.warning("lite module changed shape; parallel fetch NOT installed")
            return getattr(mod, "_verify_parallel", False)

        orig_fetch = mod._fetch_page
        orig_build = mod._build_candidates

        def fetch_result(url):
            # A worker owns only its result and immutable completion timestamp.
            text = orig_fetch(url)
            return text, time.monotonic()

        def build(claim_text, rows):
            workers = _lite_workers.get()
            if workers is None:
                return orig_build(claim_text, rows)
            rows = rows[:mod.FETCH_SOURCE_LIMIT]
            urls = list(dict.fromkeys(r.get("url") for r in rows
                                     if r.get("url") and not mod._is_pdf(r["url"])))
            pages = {}
            pool = ThreadPoolExecutor(max_workers=min(workers, len(urls))) if urls else None
            futures = {}
            try:
                for url in urls:
                    mod._remaining("parallel_fetch")
                    context = contextvars.copy_context()
                    # copy_context is shallow: never share coordinator partial state.
                    context.run(mod._partial_state.set, None)
                    futures[pool.submit(context.run, fetch_result, url)] = url
                for index, row in enumerate(rows):
                    if not row.get("url") or mod._is_pdf(row["url"]):
                        pages[index] = mod._process_ready_page(claim_text, row, index, "")
                pending = set(futures)
                while pending:
                    remaining = mod._remaining("parallel_fetch")
                    done, pending = wait(
                        pending, timeout=min(0.05, remaining),
                        return_when=FIRST_COMPLETED,
                    )
                    mod._remaining("parallel_fetch")
                    # Consume a ready batch in original source order, not set order.
                    ready = {futures[future]: future.result() for future in done}
                    for index, row in enumerate(rows):
                        if row.get("url") in ready:
                            text, completed_at = ready[row["url"]]
                            pages[index] = mod._process_ready_page(
                                claim_text, row, index, text, completed_at,
                            )
                return mod._merge_candidate_pages(pages)
            finally:
                for future in futures:
                    future.cancel()
                if pool is not None:
                    # Running DNS/network calls cannot be killed or joined here.
                    pool.shutdown(wait=False, cancel_futures=True)

        mod._build_candidates = build
        mod._verify_parallel = True
        return True

    async def __call__(self, claim_text: str) -> list:
        token = _lite_workers.set(self.workers if self.parallel_fetch else None)
        cancellation = Event()
        cancel_token = self._mod._cancellation_event.set(cancellation)
        try:
            return _mark_snippets(await asyncio.to_thread(self._mod.search, claim_text, self.max_sources))
        except asyncio.CancelledError:
            # Signals cooperative stop; does not kill a blocking DNS/SDK/socket call.
            cancellation.set()
            raise
        finally:
            self._mod._cancellation_event.reset(cancel_token)
            _lite_workers.reset(token)


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
