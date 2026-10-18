"""
Concurrency, memory and performance tests (offline: fake LLM and fake search, no keys).

What these protect:
  * admitted requests overlap without mixed answers; excess requests are rejected
    by the unchanged admission and quota limits
  * a request stuck on a slow claim does not slow down the others, and still answers
    within TOTAL_TIMEOUT
  * /health stays fast while verifications are running (the frontend calls it before
    every submit, docs/API_CONTRACT.md)
  * memory does not grow with the number of requests; the cache stays bounded
  * disconnected streams do not leave tasks behind, even many at once
  * the backend's own overhead per request stays small

The thresholds are generous on purpose (shared CI runners are slow and noisy): they catch
a regression such as an accidental lock or an unbounded list, not a few milliseconds.
For numbers against a real server use `python loadtest.py` (see README, "Yük testi").
"""

from __future__ import annotations

import asyncio
import gc
import json
import statistics
import time
import tracemalloc
from types import SimpleNamespace as NS

import httpx
import pytest

from app.limits import UpstreamGate
from contract import validate_verify_response

pytestmark = pytest.mark.perf


class EchoBackend:
    """Fake steps where the answer depends on the input, so mixed-up responses are visible.

    Each request text becomes `n` claims "<text> #k". Claims containing ASILI hang.
    Tracks how many retrieval calls run at the same time, overall and per request text.
    """

    def __init__(self, n_claims: int = 2, delay: float = 0.0) -> None:
        self.n_claims = n_claims
        self.delay = delay
        self.active = 0
        self.peak = 0
        self.active_by_req: dict = {}
        self.peak_by_req: dict = {}
        self.started = 0
        self.cancelled = 0

    async def extract(self, text):
        return NS(claims=[NS(id=f"c{k + 1}", text=f"{text} #{k + 1}", is_verifiable=True)
                          for k in range(self.n_claims)])

    async def retrieve(self, claim_text):
        req = claim_text.rsplit(" #", 1)[0]
        self.started += 1
        self.active += 1
        self.peak = max(self.peak, self.active)
        self.active_by_req[req] = self.active_by_req.get(req, 0) + 1
        self.peak_by_req[req] = max(self.peak_by_req.get(req, 0), self.active_by_req[req])
        try:
            if "ASILI" in claim_text:
                await asyncio.sleep(999)
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled += 1
            raise
        finally:
            self.active -= 1
            self.active_by_req[req] -= 1
        return [{"id": "source_1", "title": f"Kaynak: {claim_text}", "domain": "a.example.com",
                 "url": "https://a.example.com/1", "published_date": None, "text": f"kanıt: {claim_text}"}]

    async def verify(self, claim_text, sources):
        return NS(verdict="SUPPORTED", explanation=f"{claim_text} [source_1]", used_sources=["source_1"])


@pytest.fixture
def echo(monkeypatch):
    from app import main

    eb = EchoBackend()
    monkeypatch.setitem(main.state, "llm", NS(extract=eb.extract, verify=eb.verify))
    monkeypatch.setitem(main.state, "retriever", eb.retrieve)
    monkeypatch.setitem(main.state, "cache", None)
    monkeypatch.setitem(main.state, "init_error", None)
    monkeypatch.setattr(main, "upstream", UpstreamGate(8))
    cfg = main.settings.pipeline
    for k, v in dict(max_claims=8, claim_concurrency=4, extract_timeout=5.0, claim_timeout=5.0,
                     total_timeout=10.0, expose_detail=True).items():
        monkeypatch.setattr(cfg, k, v)
    return eb


def _client():
    from app import main

    return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test", timeout=30)


async def _verify(c, text):
    t = time.perf_counter()
    r = await c.post("/verify", json={"text": text})
    return r, time.perf_counter() - t


def _p95(xs):
    return statistics.quantiles(xs, n=20)[-1] if len(xs) >= 20 else max(xs)


# ---- concurrency -----------------------------------------------------------------------

def test_concurrent_requests_succeed_overlap_and_do_not_mix(echo, monkeypatch):
    from app import main, security

    # Keep the burst inside one quota window, without changing any limit.
    monkeypatch.setattr(security, "time", NS(time=lambda: 100000))
    echo.delay = 0.2
    n = 25

    async def go():
        async with _client() as c:
            t = time.perf_counter()
            out = await asyncio.gather(*[_verify(c, f"istek-{i}") for i in range(n)])
            return out, time.perf_counter() - t

    out, wall = asyncio.run(go())
    accepted = []
    for i, (r, _) in enumerate(out):
        if r.status_code == 429:
            assert r.json()["error"] in {"BUSY", "RATE_LIMITED"}
            assert int(r.headers["retry-after"]) > 0
            continue
        accepted.append(r)
        assert r.status_code == 200, r.text
        body = r.json()
        assert validate_verify_response(body) == []
        texts = [x["claim"] for x in body["results"]]
        assert texts == [f"istek-{i} #1", f"istek-{i} #2"], "responses were mixed between requests"
        assert all(f"istek-{i} #" in x["explanation"] for x in body["results"])
    assert len(accepted) == main.guard.maximum == 2
    errors = [r.json().get("error") for r, _ in out]
    assert errors.count("BUSY") == 8
    assert errors.count("RATE_LIMITED") == 15
    assert echo.started == 4  # rejected requests did not reach retrieval
    ids = {r.headers["x-request-id"] for r, _ in out}
    assert len(ids) == n, "every request needs its own X-Request-ID"
    # The two admitted requests overlap; the remaining requests fail promptly.
    assert wall < 2.0, f"{n} concurrent requests took {wall:.2f}s: something serialises them"


def test_upstream_calls_are_capped_across_all_requests(echo, monkeypatch):
    """CLAIM_CONCURRENCY limits claims inside ONE request; MAX_UPSTREAM_CONCURRENCY limits the
    paid search/verdict calls of ALL requests together (app/limits.py)."""
    from app import main

    monkeypatch.setattr(main.settings.pipeline, "claim_concurrency", 3)
    monkeypatch.setattr(main, "upstream", UpstreamGate(5))
    echo.n_claims, echo.delay = 6, 0.1
    requests = 2

    async def go():
        async with _client() as c:
            return await asyncio.gather(*[_verify(c, f"r{i}") for i in range(requests)])

    out = asyncio.run(go())
    assert all(r.status_code == 200 for r, _ in out)
    assert all(x["status"] == "ok" for r, _ in out for x in r.json()["results"])
    assert max(echo.peak_by_req.values()) <= 3, echo.peak_by_req
    assert echo.peak == 5, f"global cap not applied (peak {echo.peak})"
    assert main.upstream.peak == 5
    assert echo.started == requests * 6


def test_identical_claims_in_flight_are_searched_once(echo):
    """Two admitted users share one search and one verdict per claim."""
    from app import main

    echo.delay = 0.2

    async def go():
        async with _client() as c:
            return await asyncio.gather(*[_verify(c, "aynı metin") for _ in range(2)])

    out = asyncio.run(go())
    bodies = [r.json() for r, _ in out]
    assert all(r.status_code == 200 for r, _ in out)
    assert echo.started == 2, f"{echo.started} searches for 2 distinct claims"
    def same(results):  # timings are measured per request, everything else must be equal
        return [{k: v for k, v in x.items() if k != "timings_ms"} for x in results]

    assert all(same(b["results"]) == same(bodies[0]["results"]) for b in bodies)
    assert main.upstream.shared_hits >= 2


def test_one_user_leaving_does_not_cancel_a_shared_call(echo, monkeypatch):
    """A stream that disconnects must not break the answer of another request waiting on the
    same in-flight call; the call is cancelled only when nobody is left."""
    from app import main
    from test_stream import _asgi_post_and_disconnect

    monkeypatch.setattr(main.settings.pipeline, "total_timeout", 30.0)
    monkeypatch.setattr(main.settings.pipeline, "claim_timeout", 30.0)
    echo.delay = 0.4

    async def go():
        async with _client() as c:
            stays = asyncio.create_task(_verify(c, "ortak metin"))
            await asyncio.sleep(0.05)
            await _asgi_post_and_disconnect(main.app, "/verify/stream", json.dumps({"text": "ortak metin"}).encode(),
                                            b"event: claims", use_receive=True)
            return await stays

    r, _ = asyncio.run(go())
    assert r.status_code == 200
    assert [x["status"] for x in r.json()["results"]] == ["ok", "ok"]
    assert echo.cancelled == 0 and echo.started == 2


def test_a_hanging_request_does_not_slow_down_the_others(echo, monkeypatch):
    from app import main

    monkeypatch.setattr(main.settings.pipeline, "total_timeout", 1.5)
    monkeypatch.setattr(main.settings.pipeline, "claim_timeout", 30.0)
    echo.delay = 0.05

    async def go():
        async with _client() as c:
            slow = asyncio.create_task(_verify(c, "ASILI istek"))
            await asyncio.sleep(0.05)
            fast = await asyncio.gather(*[_verify(c, f"hızlı-{i}") for i in range(1)])
            slow_done_early = slow.done()
            return fast, slow_done_early, await slow

    fast, slow_done_early, (slow_r, slow_t) = asyncio.run(go())
    assert not slow_done_early
    assert all(r.status_code == 200 for r, _ in fast)
    assert max(t for _, t in fast) < 0.8
    body = slow_r.json()
    assert slow_r.status_code == 200 and body["partial"] is True
    assert {x["status"] for x in body["results"]} == {"timeout"}
    assert slow_t < 1.5 + 1.0, f"TOTAL_TIMEOUT not respected under load ({slow_t:.2f}s)"


def test_health_stays_fast_while_verifications_run(echo):
    echo.delay = 0.5

    async def go():
        async with _client() as c:
            busy = [asyncio.create_task(_verify(c, f"yük-{i}")) for i in range(2)]
            await asyncio.sleep(0.1)
            lat = []
            for _ in range(10):
                t = time.perf_counter()
                r = await c.get("/health")
                lat.append(time.perf_counter() - t)
                assert r.status_code == 200
            still_busy = sum(not b.done() for b in busy)
            results = await asyncio.gather(*busy)
            assert all(r.status_code == 200 for r, _ in results)
            return lat, still_busy

    lat, still_busy = asyncio.run(go())
    assert still_busy == 2, "the health checks must have run while the verifications were in flight"
    assert max(lat) < 0.25, f"/health took {max(lat) * 1000:.0f} ms under load"


# ---- memory --------------------------------------------------------------------------

def test_memory_does_not_grow_with_request_count(echo):
    # Test pipeline allocations directly: 500 HTTP successes in a minute would
    # contradict the production quota, and measuring 429s would not test its memory.
    from app import main

    async def batch(start, count):
        for k in range(0, count, 20):
            rs = await asyncio.gather(*[main._run(f"m-{start + k + j}") for j in range(20)])
            assert all(validate_verify_response(r) == [] for r in rs)

    async def go():
        await batch(0, 100)
        gc.collect()
        tracemalloc.start()
        before = tracemalloc.take_snapshot()
        await batch(1000, 400)
        gc.collect()
        after = tracemalloc.take_snapshot()
        tracemalloc.stop()
        return sum(s.size_diff for s in after.compare_to(before, "filename"))

    growth = asyncio.run(go())
    assert growth < 1_000_000, f"memory grew by {growth / 1e6:.2f} MB over 400 requests"


def test_cache_is_bounded_under_many_distinct_claims(echo, monkeypatch):
    from app import main
    from app.pipeline import TTLCache

    cache = TTLCache(ttl=3600, max_items=50)
    monkeypatch.setitem(main.state, "cache", cache)

    async def go():
        # Cache eviction is a pipeline property, independent of HTTP quotas.
        for k in range(0, 200, 25):
            results = await asyncio.gather(*[main._run(f"farklı-{k + j}") for j in range(25)])
            assert all(validate_verify_response(r) == [] for r in results)
        return await main._run("farklı-199")

    again = asyncio.run(go())
    assert len(cache) == 50
    assert all(x.get("cached") is True for x in again["results"]), "recent entries must still be served"


def test_many_disconnected_streams_leave_no_tasks_behind(echo, monkeypatch):
    from app import main
    from test_stream import _asgi_post_and_disconnect

    monkeypatch.setattr(main.settings.pipeline, "total_timeout", 30.0)
    monkeypatch.setattr(main.settings.pipeline, "claim_timeout", 30.0)
    echo.n_claims = 3
    monkeypatch.setattr(main, "upstream", UpstreamGate(8))

    async def go():
        responses = await asyncio.gather(*[
            _asgi_post_and_disconnect(main.app, "/verify/stream", json.dumps({"text": f"ASILI {i}"}).encode(),
                                      b"event: claims", use_receive=True)
            for i in range(20)
        ])
        assert sum(b"event: claims" in body for body in responses) == 2
        for body in responses:
            if b"event: claims" not in body:
                assert json.loads(body)["error"] in {"BUSY", "RATE_LIMITED"}
        await asyncio.sleep(0.05)
        return [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    t = time.perf_counter()
    leftover = asyncio.run(go())
    assert time.perf_counter() - t < 5
    assert leftover == []
    # queued calls never start; every call that did start was cancelled
    assert 0 < echo.started == echo.cancelled <= main.upstream.max_concurrency


# ---- performance ---------------------------------------------------------------------

def test_backend_overhead_per_request_is_small(echo):
    """With instant fakes everything measured is the backend's own work (validation,
    middleware, pipeline, JSON). Locally p95 is a few ms; the limit leaves room for CI."""

    async def go():
        async with _client() as c:
            for i in range(2):
                r, _ = await _verify(c, f"ısınma-{i}")
                assert r.status_code == 200
            lat = []
            for i in range(8):
                r, t = await _verify(c, f"ölçüm-{i}")
                assert r.status_code == 200
                assert r.json()["timings"]["total_ms"] >= 0
                lat.append(t)
            return lat

    lat = asyncio.run(go())
    p50, p95 = statistics.median(lat), _p95(lat)
    print(f"\n/verify overhead: p50={p50 * 1000:.1f} ms p95={p95 * 1000:.1f} ms")
    assert p95 < 0.1, f"p95 {p95 * 1000:.0f} ms"


def test_stream_overhead_per_request_is_small(echo):
    async def go():
        async with _client() as c:
            lat = []
            for i in range(10):
                t = time.perf_counter()
                r = await c.post("/verify/stream", json={"text": f"akış-{i}"})
                lat.append(time.perf_counter() - t)
                assert r.status_code == 200 and "event: done" in r.text
            return lat

    lat = asyncio.run(go())
    assert _p95(lat) < 0.15, f"stream p95 {_p95(lat) * 1000:.0f} ms"
