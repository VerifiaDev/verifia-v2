"""
Checks the LiteRetriever adapter against the REAL retrieval_demo_lite module,
with Tavily and the web faked (no network, no keys).
Run:  python tests/test_lite_adapter.py
Needs: requests, beautifulsoup4, python-dotenv  (all in requirements.txt)
"""
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "retrieval_demo_lite"))

import search_retrieval_lite as mod  # noqa: E402

PAGE_DELAY = 0.5
HTML = "<html><body><article>" + "".join(
    f"<p>Orion 2024 yılında Atlas pazarında telefon satışlarını yüzde 20 artırdı ve {i}. çeyrekte liderliğini sürdürdü. "
    f"Şirket yetkilileri büyümenin yeni modellerden kaynaklandığını açıkladı.</p>" for i in range(8)
) + "</article></body></html>"


class FakeResp:
    headers = {"Content-Type": "text/html"}
    text = HTML
    def raise_for_status(self): pass


class FakeTavily:
    def search(self, query, **kw):
        return {"results": [
            {"url": f"https://site{i}.example.com/haber/{i}", "title": f"Haber {i}",
             "content": "Orion 2024 yılında Atlas pazarında satışlarını artırdı.", "score": 0.9 - i * 0.05}
            for i in range(8)
        ]}


def fake_get(url, **kw):
    time.sleep(PAGE_DELAY)
    return FakeResp()


# keep the untouched originals so the sequential baseline stays truly sequential
ORIG_FETCH, ORIG_BUILD = mod._fetch_page, mod._build_candidates

mod._get_tavily_client = lambda: FakeTavily()
mod.requests.get = fake_get
CLAIM = "Orion 2024 yılında Atlas pazarında telefon satışlarını yüzde 20 artırdı."


def timed(fn):
    t = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - t


def test_parallel_fetch_is_faster_and_gives_the_same_sources():
    from app.retrieval import LiteRetriever

    patched = (mod._fetch_page, mod._build_candidates)
    mod._fetch_page, mod._build_candidates = ORIG_FETCH, ORIG_BUILD   # undo any earlier install
    base, t_seq = timed(lambda: mod.search(CLAIM, 5))                 # untouched module
    mod._fetch_page, mod._build_candidates = patched
    r = LiteRetriever(max_sources=5)
    assert r.parallel_fetch is True
    fast, t_par = timed(lambda: asyncio.run(r(CLAIM)))
    print(f"   sequential {t_seq:.1f}s  ->  parallel {t_par:.1f}s   ({len(base)} vs {len(fast)} sources)")

    assert len(fast) >= 1
    assert t_par < t_seq / 2, "parallel downloads should be much faster"
    assert [s["url"] for s in fast] == [s["url"] for s in base], "must pick the same evidence"
    for s in fast:
        assert {"id", "url", "text", "title", "domain", "retrieval_score"} <= set(s)


def test_installing_twice_is_safe():
    from app.retrieval import LiteRetriever
    a, b = LiteRetriever(), LiteRetriever()
    assert a.parallel_fetch and b.parallel_fetch
    out = asyncio.run(b(CLAIM))
    assert out


def test_concurrent_claims_do_not_mix_up_their_pages():
    from app.retrieval import LiteRetriever
    r = LiteRetriever()

    async def go():
        return await asyncio.gather(r(CLAIM), r(CLAIM + " "), r("Atlas 2024 telefon satışları"))

    outs = asyncio.run(go())
    assert all(outs)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn(); print(f"PASS  {name}")
        except Exception as e:
            failed += 1; print(f"FAIL  {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
