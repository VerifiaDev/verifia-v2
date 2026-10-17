"""
Pipeline tests with fake extract / retrieve / verify steps (no network, no keys).
Run:   python tests/test_pipeline.py        (or: pytest tests)
"""

import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline import NO_EVIDENCE, PipelineConfig, PipelineError, TTLCache, run_pipeline  # noqa: E402


def claim(i, text=None, verifiable=True):
    return NS(id=f"c{i}", text=text or f"iddia {i}", is_verifiable=verifiable)


def make_steps(claims, *, retrieve_delay=0.0, verify_delay=0.0, fail_on=None, hang_on=None, no_sources_for=None):
    calls = {"retrieve": 0, "verify": 0}

    async def extract(text):
        return NS(claims=claims)

    async def retrieve(text):
        calls["retrieve"] += 1
        if hang_on and hang_on in text:
            await asyncio.sleep(999)
        if fail_on and fail_on in text:
            raise RuntimeError("tavily exploded")
        await asyncio.sleep(retrieve_delay)
        if no_sources_for and no_sources_for in text:
            return []
        return [{"id": "source_1", "url": "https://a.test", "text": "kanit"},
                {"id": "source_2", "url": "https://b.test", "text": "kanit 2"}]

    async def verify(text, sources):
        calls["verify"] += 1
        await asyncio.sleep(verify_delay)
        # includes one hallucinated id on purpose
        return NS(verdict="SUPPORTED", explanation="ok [source_1]", used_sources=["source_1", "source_99"])

    return extract, retrieve, verify, calls


def run(coro):
    return asyncio.run(coro)


def test_claims_run_concurrently():
    cl = [claim(i) for i in range(6)]
    ex, rt, vf, _ = make_steps(cl, retrieve_delay=0.5, verify_delay=0.5)
    cfg = PipelineConfig(claim_concurrency=6)
    t = time.perf_counter()
    out = run(run_pipeline("x", extract=ex, retrieve=rt, verify=vf, cfg=cfg))
    elapsed = time.perf_counter() - t
    assert len(out["results"]) == 6
    assert elapsed < 1.6, f"should be ~1s (parallel), took {elapsed:.2f}s (sequential would be 6s)"
    assert all(r["status"] == "ok" for r in out["results"])


def test_concurrency_limit_is_respected():
    cl = [claim(i) for i in range(4)]
    ex, rt, vf, _ = make_steps(cl, retrieve_delay=0.4)
    cfg = PipelineConfig(claim_concurrency=2)
    t = time.perf_counter()
    run(run_pipeline("x", extract=ex, retrieve=rt, verify=vf, cfg=cfg))
    assert 0.75 < time.perf_counter() - t < 1.5  # two waves of 0.4s


def test_order_preserved_and_hallucinated_source_dropped():
    cl = [claim(0), claim(1, verifiable=False), claim(2)]
    ex, rt, vf, _ = make_steps(cl)
    out = run(run_pipeline("x", extract=ex, retrieve=rt, verify=vf))
    assert [r["claim_id"] for r in out["results"]] == ["c0", "c1", "c2"]
    assert out["results"][1]["verdict"] is None and out["results"][1]["is_verifiable"] is False
    assert out["results"][0]["used_sources"] == ["source_1"]  # source_99 removed


def test_one_failing_claim_does_not_kill_the_others():
    cl = [claim(0, "iyi"), claim(1, "BOZUK"), claim(2, "iyi iki")]
    ex, rt, vf, _ = make_steps(cl, fail_on="BOZUK")
    out = run(run_pipeline("x", extract=ex, retrieve=rt, verify=vf))
    st = [r["status"] for r in out["results"]]
    assert st == ["ok", "error", "ok"]
    bad = out["results"][1]
    assert bad["error_code"] == "RETRIEVAL_FAILED" and bad["failed_stage"] == "retrieval"
    assert "tavily exploded" in bad["detail"]  # the real cause is visible
    assert out["partial"] is True


def test_detail_can_be_hidden():
    cl = [claim(0, "BOZUK")]
    ex, rt, vf, _ = make_steps(cl, fail_on="BOZUK")
    out = run(run_pipeline("x", extract=ex, retrieve=rt, verify=vf, cfg=PipelineConfig(expose_detail=False)))
    assert out["results"][0]["detail"] is None


def test_per_claim_timeout():
    cl = [claim(0, "iyi"), claim(1, "ASILI")]
    ex, rt, vf, _ = make_steps(cl, hang_on="ASILI")
    cfg = PipelineConfig(claim_timeout=0.3, total_timeout=5)
    t = time.perf_counter()
    out = run(run_pipeline("x", extract=ex, retrieve=rt, verify=vf, cfg=cfg))
    assert time.perf_counter() - t < 1.5
    assert out["results"][0]["status"] == "ok"
    assert out["results"][1]["status"] == "timeout"
    assert out["results"][1]["failed_stage"] == "retrieval"


def test_total_deadline_returns_partial_results():
    cl = [claim(0, "iyi"), claim(1, "ASILI")]
    ex, rt, vf, _ = make_steps(cl, hang_on="ASILI")
    cfg = PipelineConfig(claim_timeout=60, total_timeout=0.5)  # deadline hits first
    t = time.perf_counter()
    out = run(run_pipeline("x", extract=ex, retrieve=rt, verify=vf, cfg=cfg))
    assert time.perf_counter() - t < 1.5, "must answer by the deadline, not hang"
    assert out["results"][0]["status"] == "ok"
    assert out["results"][1]["status"] == "timeout" and out["results"][1]["error_code"] == "DEADLINE_EXCEEDED"
    assert out["partial"] is True


def test_claim_cap_skips_extras():
    cl = [claim(i) for i in range(5)]
    ex, rt, vf, calls = make_steps(cl)
    out = run(run_pipeline("x", extract=ex, retrieve=rt, verify=vf, cfg=PipelineConfig(max_claims=3)))
    assert [r["status"] for r in out["results"]] == ["ok", "ok", "ok", "skipped", "skipped"]
    assert calls["retrieve"] == 3


def test_no_sources_skips_the_llm_call():
    cl = [claim(0, "hic kaynak yok")]
    ex, rt, vf, calls = make_steps(cl, no_sources_for="hic kaynak")
    out = run(run_pipeline("x", extract=ex, retrieve=rt, verify=vf))
    assert out["results"][0]["verdict"] == NO_EVIDENCE
    assert calls["verify"] == 0


def test_cache_hit_skips_work_and_normalizes_text():
    cache = TTLCache()
    ex, rt, vf, calls = make_steps([claim(0, "Aynı   İddia")])
    run(run_pipeline("x", extract=ex, retrieve=rt, verify=vf, cache=cache))
    ex2, rt2, vf2, calls2 = make_steps([claim(7, "aynı iddia")])
    out = run(run_pipeline("y", extract=ex2, retrieve=rt2, verify=vf2, cache=cache))
    assert calls["retrieve"] == 1 and calls2["retrieve"] == 0 and calls2["verify"] == 0
    r = out["results"][0]
    assert r["cached"] is True and r["claim_id"] == "c7" and r["verdict"] == "SUPPORTED"


def test_failures_are_not_cached():
    cache = TTLCache()
    ex, rt, vf, _ = make_steps([claim(0, "BOZUK")], fail_on="BOZUK")
    run(run_pipeline("x", extract=ex, retrieve=rt, verify=vf, cache=cache))
    assert len(cache) == 0


def test_cache_ttl_expiry():
    cache = TTLCache(ttl=0.05)
    cache.set("k", {"a": 1})
    assert cache.get("k") == {"a": 1}
    time.sleep(0.1)
    assert cache.get("k") is None


def test_extraction_failure_is_a_pipeline_error_with_cause():
    async def extract(text):
        raise ValueError("groq 401 invalid api key")

    try:
        run(run_pipeline("x", extract=extract, retrieve=None, verify=None))
        assert False, "should raise"
    except PipelineError as e:
        assert e.code == "EXTRACTION_FAILED" and "invalid api key" in e.detail


def test_extraction_timeout():
    async def extract(text):
        await asyncio.sleep(5)

    try:
        run(run_pipeline("x", extract=extract, retrieve=None, verify=None, cfg=PipelineConfig(extract_timeout=0.2)))
        assert False
    except PipelineError as e:
        assert e.code == "EXTRACTION_TIMEOUT" and e.http_status == 504


def test_events_are_streamed_in_a_sensible_order():
    cl = [claim(0), claim(1, verifiable=False), claim(2)]
    ex, rt, vf, _ = make_steps(cl, retrieve_delay=0.05)
    events = []

    async def emit(ev):
        events.append(ev)

    run(run_pipeline("x", extract=ex, retrieve=rt, verify=vf, emit=emit))
    assert events[0]["type"] == "claims" and len(events[0]["claims"]) == 3
    results = [e for e in events if e["type"] == "result"]
    assert len(results) == 3
    assert results[0]["result"]["claim_id"] == "c1"  # unverifiable is emitted immediately


def test_broken_emit_callback_does_not_break_the_request():
    cl = [claim(0)]
    ex, rt, vf, _ = make_steps(cl)

    async def emit(ev):
        raise RuntimeError("client disconnected")

    out = run(run_pipeline("x", extract=ex, retrieve=rt, verify=vf, emit=emit))
    assert out["results"][0]["status"] == "ok"


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        t = time.perf_counter()
        try:
            fn()
            print(f"PASS  {name}  ({time.perf_counter() - t:.2f}s)")
        except Exception as e:
            failed += 1
            print(f"FAIL  {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
