"""
Checks the LiteRetriever adapter against the REAL retrieval_demo_lite module.
Only Tavily, DNS and Session.get are faked (no network, no keys).
Run: python -B backend_v2/tests/test_lite_adapter.py
Needs: requests, beautifulsoup4, python-dotenv.
"""
import asyncio
import os
from copy import deepcopy
import socket
import sys
import time
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Lock
from unittest.mock import patch
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
_original_path = sys.path[:]
try:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT.parent / "retrieval_demo_lite"))
    import search_retrieval_lite as mod
    from app.retrieval import LiteRetriever
    import app.retrieval as adapter
finally:
    sys.path[:] = _original_path

PAGE_DELAY = 0.5
MARKERS = ("claimalpha", "claimbeta", "claimgamma")
CLAIM = "claimalpha 2024 yılında üretim yüzde 20 arttı."


class FakeResp:
    encoding = "utf-8"
    status_code = 200
    headers = {"Content-Type": "text/html"}

    def __init__(self, marker):
        self.closed = False
        self.text = "<html><body><article>" + "".join(
            f"<p>{marker} 2024 yılında üretim yüzde 20 arttı ve {i}. çeyrekte büyüdü. "
            f"{marker} yıllık raporu üretim artışını yeni yatırımlarla açıkladı.</p>"
            for i in range(8)
        ) + "</article></body></html>"

    def iter_content(self, chunk_size):
        body = self.text.encode(self.encoding)
        for offset in range(0, len(body), chunk_size):
            yield body[offset:offset + chunk_size]

    def raise_for_status(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True
        if hasattr(self, "on_close"):
            self.on_close()


class FakeTavily:
    def search(self, query, timeout=5, **kw):
        marker, = [m for m in MARKERS if m in query.casefold()]
        return {"results": [
            {"url": f"https://site{i}.example.com/{marker}/haber/{i}",
             "title": f"{marker} üretim raporu {i}",
             "content": f"{marker} 2024 üretim arttı.", "score": 0.9 - i * 0.05}
            for i in range(8)
        ]}


@contextmanager
def fake_external_services(block_marker=None, entered=None, release=None, fast_delay=None,
                           block_index=None, single_chunk=False):
    # The adapter installs real wrappers globally; restore its state even on failure.
    original_fetch, original_build = mod._fetch_page, mod._build_candidates
    missing = object()
    original_flag = getattr(mod, "_verify_parallel", missing)
    calls, dns_hosts = [], []
    active = Counter()
    lock = Lock()

    def fake_dns(host, port, family=0, type=0, **kwargs):
        with lock:
            dns_hosts.append(host)
        if host not in {f"site{i}.example.com" for i in range(8)}:
            raise socket.gaierror("unexpected test hostname")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    def fake_get(session, url, **kwargs):
        marker = urlparse(url).path.split("/")[1]
        result = FakeResp(marker)
        if single_chunk:
            result.text = "<p>" + (marker + " üretim büyüme ") * 35 + "</p>"
        result.worker_partial_state = mod._partial_state.get()
        result.worker_setting = adapter._lite_workers.get()
        result.stream_requested = kwargs.get("stream")
        result.deadline = mod._total_deadline.get()
        # Check outside _fetch_page, whose exception handler would swallow assertions.
        with lock:
            active[marker] += 1
            result.observed_active = active[marker]
            calls.append((url, session.trust_env, kwargs.get("allow_redirects"), result))
        def finished():
            with lock:
                active[marker] -= 1
        result.on_close = finished
        if marker == block_marker and (block_index is None or url.endswith(f"/{block_index}")):
            entered.set()
            release.wait(3)
        else:
            time.sleep(PAGE_DELAY if fast_delay is None else fast_delay)
        return result

    try:
        with patch.object(mod, "_tavily_client", FakeTavily()), \
             patch.object(mod.socket, "getaddrinfo", side_effect=fake_dns), \
             patch.object(mod.requests.Session, "get", new=fake_get):
            yield calls
            assert calls, "the real page-fetch path must reach Session.get"
            assert dns_hosts, "the real validator must resolve destinations"
            assert all(trust is False and redirects is False for _, trust, redirects, _ in calls)
            assert all(result.closed for _, _, _, result in calls)
            assert all(result.stream_requested is True for _, _, _, result in calls)
            assert Counter(dns_hosts) == Counter(urlparse(url).hostname for url, *_ in calls)
    finally:
        mod._fetch_page, mod._build_candidates = original_fetch, original_build
        if original_flag is missing:
            if hasattr(mod, "_verify_parallel"):
                del mod._verify_parallel
        else:
            mod._verify_parallel = original_flag


def timed(fn):
    t = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - t


def assert_page_sources(sources):
    assert sources
    for source in sources:
        assert {"id", "url", "text", "title", "domain", "retrieval_score"} <= set(source)
        assert source["metadata"]["fetch_method"] == "requests"


def test_parallel_fetch_is_faster_and_gives_the_same_sources():
    with fake_external_services():
        base, t_seq = timed(lambda: mod.search(CLAIM, 5))
        r = LiteRetriever(max_sources=5)
        assert r.parallel_fetch is True
        fast, t_par = timed(lambda: asyncio.run(r(CLAIM)))
        print(f"   sequential {t_seq:.1f}s  ->  parallel {t_par:.1f}s   ({len(base)} vs {len(fast)} sources)")
        assert_page_sources(base)
        assert_page_sources(fast)
        assert t_par < t_seq / 2, "parallel downloads should be much faster"
        assert [s["url"] for s in fast] == [s["url"] for s in base]
        assert fast == base, "all evidence and metadata must match"
        assert fast == BASELINE_SOURCES, "normal output must match the canonical-page baseline exactly"


def test_installing_twice_is_safe():
    with fake_external_services() as calls:
        a = LiteRetriever()
        first_fetch, first_build = mod._fetch_page, mod._build_candidates
        b = LiteRetriever()
        assert a.parallel_fetch and b.parallel_fetch
        assert mod._fetch_page is first_fetch and mod._build_candidates is first_build
        out = asyncio.run(b(CLAIM))
        assert_page_sources(out)
        assert len(calls) == min(8, mod.FETCH_SOURCE_LIMIT, mod.PREFILTER_SOURCE_LIMIT)
        assert len({url for url, *_ in calls}) == len(calls)


def test_concurrent_claims_do_not_mix_up_their_pages():
    with fake_external_services() as calls:
        r = LiteRetriever()
        claims = [f"{marker} 2024 yılında üretim yüzde 20 arttı." for marker in MARKERS]

        async def go():
            return await asyncio.gather(*(r(claim) for claim in claims))

        outs = asyncio.run(go())
        for marker, sources in zip(MARKERS, outs):
            assert_page_sources(sources)
            for source in sources:
                assert f"/{marker}/" in source["url"]
                assert marker in source["text"]
                assert all(other not in source["text"] for other in MARKERS if other != marker)
        counts = Counter(urlparse(url).path.split("/")[1] for url, *_ in calls)
        expected = min(8, mod.FETCH_SOURCE_LIMIT, mod.PREFILTER_SOURCE_LIMIT)
        assert counts == {marker: expected for marker in MARKERS}


async def detailed_for(retriever, claim):
    token = adapter._lite_workers.set(retriever.workers if retriever.parallel_fetch else None)
    try:
        return await asyncio.to_thread(mod.search_detailed, claim, retriever.max_sources)
    finally:
        adapter._lite_workers.reset(token)


def test_concurrent_deadline_isolation_and_nonblocking_cleanup():
    entered, release = Event(), Event()
    with fake_external_services("claimalpha", entered, release, 0.01) as calls, \
         patch.object(mod, "TOTAL_DEADLINE", 0.25):
        r = LiteRetriever(workers=1)
        async def go():
            slow = asyncio.create_task(detailed_for(r, CLAIM))
            while not entered.is_set():
                await asyncio.sleep(0.001)
            fast = await detailed_for(r, "claimbeta 2024 yılında üretim yüzde 20 arttı.")
            started = time.monotonic()
            expired = await slow
            assert time.monotonic() - started < 0.5
            assert not release.is_set(), "timeout must return before blocked worker finishes"
            assert expired["sources"] == []
            assert expired["diagnostics"]["timed_out"] is True
            assert expired["diagnostics"]["timeout_stage"] == "parallel_fetch"
            assert_page_sources(fast["sources"])
            assert fast["diagnostics"]["timed_out"] is False
            assert fast["diagnostics"]["timeout_stage"] is None
        try:
            asyncio.run(go())
            slow_calls = [row for row in calls if "/claimalpha/" in row[0]]
            fast_calls = [row for row in calls if "/claimbeta/" in row[0]]
            assert len(slow_calls) == 1, "queued jobs must be cancelled at deadline"
            assert len({row[3].deadline for row in fast_calls}) == 1
            assert slow_calls[0][3].deadline != fast_calls[0][3].deadline
        finally:
            release.set()
            end = time.monotonic() + 2
            while not all(row[3].closed for row in calls) and time.monotonic() < end:
                time.sleep(0.005)
        assert mod._total_deadline.get() is None


def test_partial_two_committed_pages_and_concurrent_claim_isolation():
    entered, release = Event(), Event()
    with fake_external_services("claimalpha", entered, release, 0.01,
                                block_index=2, single_chunk=True) as calls, \
         patch.object(mod, "TOTAL_DEADLINE", 0.4), \
         patch.object(mod, "FETCH_SOURCE_LIMIT", 3):
        r = LiteRetriever(max_sources=2, workers=3)
        async def go():
            slow = asyncio.create_task(detailed_for(r, CLAIM))
            while not entered.is_set():
                await asyncio.sleep(0.001)
            fast = await detailed_for(r, "claimbeta 2024 üretim büyüme")
            partial = await slow
            assert not release.is_set()
            assert len(partial["sources"]) == 2
            assert len({s["url"] for s in partial["sources"]}) == 2
            assert partial["diagnostics"]["partial_result"] is True
            assert partial["diagnostics"]["completed_source_count"] == 2
            assert partial["diagnostics"]["timed_out"] is True
            assert partial["diagnostics"]["timeout_stage"] == "parallel_fetch"
            assert fast["diagnostics"]["timed_out"] is False
            assert fast["diagnostics"]["partial_result"] is False
            for result, marker, other in ((partial, "claimalpha", "claimbeta"),
                                           (fast, "claimbeta", "claimalpha")):
                assert_page_sources(result["sources"])
                assert all(marker in source["text"] and other not in source["text"]
                           for source in result["sources"])
            return partial, fast
        try:
            results = asyncio.run(go())
            frozen = deepcopy(results)
            assert all(row[3].worker_partial_state is None for row in calls)
        finally:
            release.set()
            end = time.monotonic() + 2
            while not all(row[3].closed for row in calls) and time.monotonic() < end:
                time.sleep(0.005)
        assert results == frozen, "late workers must not mutate either response"
        assert mod._partial_state.get() is None


def test_worker_validation_and_environment_precedence():
    with fake_external_services(fast_delay=0):
        with patch.dict(os.environ, {}, clear=True):
            assert LiteRetriever().workers == 4
        for value in ("1", "2", "4", "8", "9", "9999999999999999"):
            with patch.dict(os.environ, {"LITE_FETCH_WORKERS": value}):
                assert LiteRetriever().workers == min(int(value), 8)
                assert LiteRetriever(workers=2).workers == 2
        invalid = [True, False, 0, -1, 1.0, 1.5, float("nan"), float("inf"),
                   "", "bad", "1.5", "NaN", "Infinity", "-1", "0", "9" * 10000]
        for value in invalid:
            with patch.dict(os.environ, {"LITE_FETCH_WORKERS": "3"}):
                assert LiteRetriever(workers=value).workers == 3
            with patch.dict(os.environ, {"LITE_FETCH_WORKERS": str(value)}):
                assert LiteRetriever().workers == 4
        with patch.dict(os.environ, {"LITE_FETCH_WORKERS": "bad"}):
            assert LiteRetriever(workers=10**100).workers == 8
            assert_page_sources(asyncio.run(LiteRetriever()(CLAIM)))


def test_per_instance_limits_both_install_orders_and_concurrent():
    for order in ((2, 4), (4, 2)):
        with fake_external_services(fast_delay=0.03) as calls:
            instances = [LiteRetriever(workers=n) for n in order]
            for instance in instances:
                start = len(calls)
                assert_page_sources(asyncio.run(instance(CLAIM)))
                assert max(row[3].observed_active for row in calls[start:]) == instance.workers
                assert all(row[3].worker_setting == instance.workers for row in calls[start:])
            start = len(calls)
            async def together():
                return await asyncio.gather(instances[0](CLAIM),
                    instances[1]("claimbeta 2024 üretim büyüme"))
            assert all(asyncio.run(together()))
            for marker, instance in zip(("claimalpha", "claimbeta"), instances):
                matching = [row[3] for row in calls[start:] if marker in row[0]]
                assert max(result.observed_active for result in matching) == instance.workers
                assert all(result.worker_setting == instance.workers for result in matching)


def test_sequential_instance_and_direct_module_after_install():
    with fake_external_services(fast_delay=0.01) as calls:
        parallel = LiteRetriever(workers=4)
        sequential = LiteRetriever(workers=8, parallel_fetch=False)
        assert_page_sources(asyncio.run(parallel(CLAIM)))
        start = len(calls)
        seq = asyncio.run(sequential(CLAIM))
        assert max(row[3].observed_active for row in calls[start:]) == 1
        assert all(row[3].worker_setting is None for row in calls[start:])
        start = len(calls)
        direct = mod.search(CLAIM, 5)
        assert max(row[3].observed_active for row in calls[start:]) == 1
        assert direct == seq == BASELINE_SOURCES


def test_unique_url_count_caps_pool():
    from concurrent.futures import ThreadPoolExecutor
    with fake_external_services(fast_delay=0.01), \
         patch.object(mod, "FETCH_SOURCE_LIMIT", 2), \
         patch.object(adapter, "ThreadPoolExecutor", wraps=ThreadPoolExecutor) as pool:
        assert_page_sources(asyncio.run(LiteRetriever(workers=8)(CLAIM)))
        assert pool.call_args.kwargs["max_workers"] == 2


def test_context_cleanup_on_timeout_exception_and_cancellation():
    with fake_external_services(fast_delay=0.03):
        r = LiteRetriever(workers=2)
        async def go():
            with patch.object(mod, "TOTAL_DEADLINE", 0.01):
                assert await r(CLAIM) == []
            assert adapter._lite_workers.get() is None
            await asyncio.sleep(0.05)  # let timed-out fixture workers close
            with patch.object(mod, "search", side_effect=RuntimeError("test failure")):
                try:
                    await r(CLAIM)
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("expected failure")
            assert adapter._lite_workers.get() is None
            entered, release = Event(), Event()
            def blocked(*args):
                entered.set()
                release.wait(2)
                return []
            async def cancelled_call():
                try:
                    await r(CLAIM)
                except asyncio.CancelledError:
                    assert adapter._lite_workers.get() is None
                    raise
            with patch.object(mod, "search", side_effect=blocked):
                task = asyncio.create_task(cancelled_call())
                while not entered.is_set():
                    await asyncio.sleep(0.001)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                finally:
                    release.set()
            assert adapter._lite_workers.get() is None
            assert_page_sources(await r(CLAIM))
        asyncio.run(go())


# Offline fixture baseline: best retrieval-scoring chunk per canonical page.
# Source 2 formerly used a lower-scoring chunk chosen for MMR novelty.
BASELINE_SOURCES = [{'id': 'source_1',
  'url': 'https://site0.example.com/claimalpha/haber/0',
  'text': 'claimalpha 2024 yılında üretim yüzde 20 arttı ve 0. çeyrekte büyüdü.',
  'title': 'claimalpha üretim raporu 0',
  'domain': 'site0.example.com',
  'published_date': None,
  'retrieval_score': 0.888,
  'candidate_type': 'lite_chunk',
  'metadata': {'retrieval_version': '5.2-lite-512mb',
               'api_version': 'search-v1',
               'scoring_mode': 'lite_lexical',
               'lexical_score': 0.916,
               'search_score': 0.7397,
               'structural_score': 1.0,
               'mmr_score': 0.746,
               'fetch_method': 'requests'}},
 {'id': 'source_2',
  'url': 'https://site1.example.com/claimalpha/haber/1',
  'text': 'claimalpha 2024 yılında üretim yüzde 20 arttı ve 0. çeyrekte büyüdü.',
  'title': 'claimalpha üretim raporu 1',
  'domain': 'site1.example.com',
  'published_date': None,
  'retrieval_score': 0.8818,
  'candidate_type': 'lite_chunk',
  'metadata': {'retrieval_version': '5.2-lite-512mb',
               'api_version': 'search-v1',
               'scoring_mode': 'lite_lexical',
               'lexical_score': 0.916,
               'search_score': 0.7127,
               'structural_score': 1.0,
               'mmr_score': 0.5807,
               'fetch_method': 'requests'}},
 {'id': 'source_3',
  'url': 'https://site2.example.com/claimalpha/haber/2',
  'text': 'claimalpha 2024 yılında üretim yüzde 20 arttı ve 0. çeyrekte büyüdü.',
  'title': 'claimalpha üretim raporu 2',
  'domain': 'site2.example.com',
  'published_date': None,
  'retrieval_score': 0.8756,
  'candidate_type': 'lite_chunk',
  'metadata': {'retrieval_version': '5.2-lite-512mb',
               'api_version': 'search-v1',
               'scoring_mode': 'lite_lexical',
               'lexical_score': 0.916,
               'search_score': 0.6857,
               'structural_score': 1.0,
               'mmr_score': 0.5755,
               'fetch_method': 'requests'}},
 {'id': 'source_4',
  'url': 'https://site3.example.com/claimalpha/haber/3',
  'text': 'claimalpha 2024 yılında üretim yüzde 20 arttı ve 0. çeyrekte büyüdü.',
  'title': 'claimalpha üretim raporu 3',
  'domain': 'site3.example.com',
  'published_date': None,
  'retrieval_score': 0.8694,
  'candidate_type': 'lite_chunk',
  'metadata': {'retrieval_version': '5.2-lite-512mb',
               'api_version': 'search-v1',
               'scoring_mode': 'lite_lexical',
               'lexical_score': 0.916,
               'search_score': 0.6587,
               'structural_score': 1.0,
               'mmr_score': 0.5703,
               'fetch_method': 'requests'}},
 {'id': 'source_5',
  'url': 'https://site4.example.com/claimalpha/haber/4',
  'text': 'claimalpha 2024 yılında üretim yüzde 20 arttı ve 0. çeyrekte büyüdü.',
  'title': 'claimalpha üretim raporu 4',
  'domain': 'site4.example.com',
  'published_date': None,
  'retrieval_score': 0.8632,
  'candidate_type': 'lite_chunk',
  'metadata': {'retrieval_version': '5.2-lite-512mb',
               'api_version': 'search-v1',
               'scoring_mode': 'lite_lexical',
               'lexical_score': 0.916,
               'search_score': 0.6317,
               'structural_score': 1.0,
               'mmr_score': 0.5651,
               'fetch_method': 'requests'}}]


def test_cancellation_running_worker_queued_futures_and_claim_isolation():
    entered, release = Event(), Event()
    stopped = Event()
    observed = []
    original = mod.search
    def observe(*args, **kwargs):
        event = mod._cancellation_event.get()
        try:
            return original(*args, **kwargs)
        finally:
            observed.append(event)
            if event is not None and event.is_set(): stopped.set()
    with fake_external_services("claimalpha", entered, release, 0.001) as calls, \
         patch.object(mod, "search", side_effect=observe):
        retriever = LiteRetriever(workers=1)
        async def go():
            slow = asyncio.create_task(retriever(CLAIM))
            limit = time.monotonic() + 2
            while not entered.is_set():
                assert time.monotonic() < limit
                await asyncio.sleep(.001)
            started = time.monotonic()
            slow.cancel()
            try:
                await slow
                raise AssertionError("async cancellation must propagate")
            except asyncio.CancelledError:
                pass
            assert time.monotonic() - started < .5
            limit = time.monotonic() + 1
            while not stopped.is_set():
                assert time.monotonic() < limit, "coordinator waited for blocked worker"
                await asyncio.sleep(.005)
            assert not release.is_set()
            assert len([c for c in calls if "/claimalpha/" in c[0]]) == 1
            fast = await retriever("claimbeta 2024 yılında üretim yüzde 20 arttı.")
            assert_page_sources(fast)
            assert mod._cancellation_event.get() is None
            assert adapter._lite_workers.get() is None
            assert len(observed) == 2 and observed[0] is not observed[1]
            assert observed[0].is_set() and not observed[1].is_set()
            release.set()
            limit = time.monotonic() + 2
            while not all(row[3].closed for row in calls):
                assert time.monotonic() < limit
                await asyncio.sleep(.005)
        try:
            asyncio.run(go())
        finally:
            release.set()


def test_upstream_gate_cancellation_reaches_lite_event():
    from app.limits import UpstreamGate
    entered, release = Event(), Event()
    stopped = Event()
    observed = []
    original = mod.search
    def observe(*args, **kwargs):
        event = mod._cancellation_event.get()
        try:
            return original(*args, **kwargs)
        finally:
            observed.append(event)
            if event is not None and event.is_set(): stopped.set()
    with fake_external_services("claimalpha", entered, release, 0.001) as calls, \
         patch.object(mod, "search", side_effect=observe):
        retriever = LiteRetriever(workers=1)
        gate = UpstreamGate(2)
        gated = gate.retrieve(retriever)
        async def go():
            slow = asyncio.create_task(gated(CLAIM))
            limit = time.monotonic() + 2
            while not entered.is_set():
                assert time.monotonic() < limit
                await asyncio.sleep(.001)
            second = asyncio.create_task(gated(CLAIM))
            limit = time.monotonic() + 1
            while gate.shared_hits != 1:
                assert time.monotonic() < limit
                await asyncio.sleep(.001)
            started = time.monotonic()
            slow.cancel()
            try:
                await slow
                raise AssertionError("async cancellation must propagate")
            except asyncio.CancelledError:
                pass
            assert time.monotonic() - started < .5
            assert not stopped.is_set(), "remaining waiter must retain shared retrieval"
            second.cancel()
            try:
                await second
                raise AssertionError("last waiter cancellation must propagate")
            except asyncio.CancelledError:
                pass
            limit = time.monotonic() + 1
            while not stopped.is_set():
                assert time.monotonic() < limit, "coordinator waited for blocked worker"
                await asyncio.sleep(.005)
            assert not release.is_set()
            assert len([c for c in calls if "/claimalpha/" in c[0]]) == 1
            fast = await gated("claimbeta 2024 yılında üretim yüzde 20 arttı.")
            assert_page_sources(fast)
            assert mod._cancellation_event.get() is None
            assert adapter._lite_workers.get() is None
            assert len(observed) == 2 and observed[0] is not observed[1]
            assert observed[0].is_set() and not observed[1].is_set()
            release.set()
            limit = time.monotonic() + 2
            while not all(row[3].closed for row in calls):
                assert time.monotonic() < limit
                await asyncio.sleep(.005)
        try:
            asyncio.run(go())
        finally:
            release.set()


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
