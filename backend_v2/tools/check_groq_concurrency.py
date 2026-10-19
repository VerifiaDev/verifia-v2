"""Offline concurrency check for the Groq path: 429 (per-minute / daily), timeouts, 5xx,
retries, capacity (BUSY) and error-text leaks - WITHOUT any real Groq or Tavily call.

How it works: a fake Groq server runs on 127.0.0.1 and the real backend (security middleware,
UpstreamGate, pipeline, FastEngine + the real groq SDK) is pointed at it via GROQ_BASE_URL.
Retrieval is a local fake. Fake keys are set before the app is imported (load_dotenv never
overrides them) and every non-loopback network connection is blocked, so a mistake cannot
reach a real provider or spend credits.

Run from backend_v2 (no server needed, ~15 s):
    python tools/check_groq_concurrency.py            # summary
    python tools/check_groq_concurrency.py --verbose  # also every call the fake Groq received
Exit code 0 = all scenarios OK. Not collected by pytest (lives in tools/).
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import socket
import sys
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

VERBOSE = "--verbose" in sys.argv
SECRET = "org_SECRET_should_never_leak"


# ---- 1. block every non-loopback connection (same idea as tools/offline_guard.py) ----------
def _local_only(host):
    if host in {None, "localhost", b"localhost"}:
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise AssertionError(f"external network blocked in this check: {host!r}")


_dns, _connect, _connect_ex = socket.getaddrinfo, socket.socket.connect, socket.socket.connect_ex
socket.getaddrinfo = lambda host, *a, **k: (_local_only(host), _dns(host, *a, **k))[1]
socket.socket.connect = lambda s, addr: (_local_only(addr[0]) if isinstance(addr, tuple) else None, _connect(s, addr))[1]
socket.socket.connect_ex = lambda s, addr: (_local_only(addr[0]) if isinstance(addr, tuple) else None, _connect_ex(s, addr))[1]


# ---- 2. fake Groq ------------------------------------------------------------------------
class FakeGroq:
    mode = "ok"            # ok | tpm429 | tpd429 | slow | error500
    slow_seconds = 4.0
    every = 2              # tpm429: every Nth verdict call gets a 429
    lock = threading.Lock()
    calls: Counter = Counter()
    log: list = []
    inflight = 0
    max_inflight = 0

    @classmethod
    def reset(cls, mode):
        with cls.lock:
            cls.mode, cls.calls, cls.log, cls.inflight, cls.max_inflight = mode, Counter(), [], 0, 0


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, headers=None):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        kind = req.get("response_format", {}).get("json_schema", {}).get("name", "?")
        user = next((m.get("content", "") for m in req.get("messages", []) if m.get("role") == "user"), "")
        with FakeGroq.lock:
            FakeGroq.calls[kind] += 1
            n = FakeGroq.calls[kind]
            FakeGroq.log.append((kind, str(user).replace("\n", " ")[:50]))
            FakeGroq.inflight += 1
            FakeGroq.max_inflight = max(FakeGroq.max_inflight, FakeGroq.inflight)
        try:
            mode = FakeGroq.mode
            period = "day (TPD)" if mode == "tpd429" else "minute (TPM)"
            limit_msg = {"error": {"message": f"Rate limit reached for model `openai/gpt-oss-20b` in organization "
                                              f"`{SECRET}` on tokens per {period}: Limit 200000, Used 199999",
                                   "type": "tokens", "code": "rate_limit_exceeded"}}
            if mode == "tpd429" or (mode == "tpm429" and kind == "verdict_result" and n % FakeGroq.every == 0):
                return self._send(429, limit_msg, {"retry-after": "7"})
            if mode == "error500" and kind == "verdict_result":
                return self._send(500, {"error": {"message": f"internal error {SECRET}"}})
            if mode == "slow" and kind == "verdict_result":
                time.sleep(FakeGroq.slow_seconds)
            if kind == "extraction_result":
                # claims depend on the input, so different users never share (deduplicated) calls
                tag = str(user).replace("<metin>", "").replace("</metin>", "").replace("Metin:", "").strip()[:60]
                content = {"claims": [{"id": "claim1", "text": f"{tag} birinci iddia.", "is_verifiable": True},
                                      {"id": "claim2", "text": f"{tag} ikinci iddia.", "is_verifiable": True}]}
            else:
                content = {"claim_id": "c", "verdict": "SUPPORTED",
                           "explanation": "Kanıtlar bunu doğruluyor [source_1].", "used_sources": ["source_1"]}
            self._send(200, {"id": "x", "object": "chat.completion", "created": 0, "model": "openai/gpt-oss-20b",
                             "choices": [{"index": 0, "finish_reason": "stop",
                                          "message": {"role": "assistant",
                                                      "content": json.dumps(content, ensure_ascii=False)}}],
                             "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
        finally:
            with FakeGroq.lock:
                FakeGroq.inflight -= 1


class QuietServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # the backend deliberately abandons slow calls (timeout scenario): not an error here
        if isinstance(sys.exc_info()[1], (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


server = QuietServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()

# ---- 3. the real app, pointed at the fake -----------------------------------------------
os.environ.update({
    "GROQ_BASE_URL": f"http://127.0.0.1:{server.server_address[1]}",
    "GROQ_API_KEY": "gsk_fake_local_test_key", "TAVILY_API_KEY": "tvly-fake-local",
    "LLM_TIMEOUT": "2", "EXTRACT_TIMEOUT": "5", "CLAIM_TIMEOUT": "6", "TOTAL_TIMEOUT": "10",
    "CACHE_TTL_SECONDS": "0", "EXPOSE_ERROR_DETAIL": "0", "LOG_LEVEL": "WARNING",
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx                                   # noqa: E402
from app import main                           # noqa: E402
from app.limits import UpstreamGate            # noqa: E402
from app.llm import LLM                        # noqa: E402
from app.resources import TrackingExecutor     # noqa: E402

try:                                           # present once the Groq error handling (PR #12) is in
    import app.upstream_errors  # noqa: F401
    TYPED_ERRORS = True
except ImportError:
    TYPED_ERRORS = False

llm = LLM(main.settings)
assert "127.0.0.1" in str(llm.engine.client.base_url), "Groq client is not pointed at the fake server"

app_calls: Counter = Counter()


async def counted_extract(text):
    app_calls["extract"] += 1
    return await llm.extract(text)


async def counted_verify(claim_text, sources):
    app_calls["verify"] += 1
    return await llm.verify(claim_text, sources)


async def fake_retrieve(text):
    await asyncio.sleep(0.3)
    return [{"id": "source_1", "title": "K1", "domain": "a.test", "url": "https://a.test/1",
             "published_date": None, "text": "kanıt 1"},
            {"id": "source_2", "title": "K2", "domain": "b.test", "url": "https://b.test/2",
             "published_date": None, "text": "kanıt 2"}]


main.state.update({"llm": type("CountingLLM", (), {"extract": staticmethod(counted_extract),
                                                   "verify": staticmethod(counted_verify)})(),
                   "retriever": fake_retrieve, "cache": None, "init_error": None})
_user_no = [10]


async def one_user():
    _user_no[0] += 1
    ip = f"203.0.113.{_user_no[0]}"            # every simulated user has its own IP (rate limit is per IP)
    transport = httpx.ASGITransport(app=main.app, client=(ip, 40000))
    async with httpx.AsyncClient(transport=transport, base_url="http://verifia.test", timeout=60) as c:
        t = time.perf_counter()
        r = await c.post("/verify", json={"text": f"Kullanıcı {_user_no[0]} metni."})
        try:
            data = r.json()
        except ValueError:
            data = {}
        return {"http": r.status_code, "ms": int((time.perf_counter() - t) * 1000), "body": r.text,
                "code": data.get("error"),
                "claims": [(x.get("status"), x.get("error_code")) for x in data.get("results") or []]}


async def scenario(name, mode, users, checks):
    FakeGroq.reset(mode)
    app_calls.clear()
    main.upstream = UpstreamGate(main.settings.upstream_concurrency)
    t = time.perf_counter()
    res = await asyncio.gather(*(one_user() for _ in range(users)))
    wall = time.perf_counter() - t
    await asyncio.sleep(FakeGroq.slow_seconds + 0.5 if mode == "slow" else 0.2)  # let abandoned calls end
    s = {
        "res": res,
        "http": Counter(r["http"] for r in res),
        "codes": Counter(r["code"] for r in res if r["code"]),
        "claims": Counter(f"{st}/{c}" if c else st for r in res for st, c in r["claims"]),
        "leak": any(SECRET in r["body"] or "Rate limit reached" in r["body"] for r in res),
        "no_retry": FakeGroq.calls["extraction_result"] == app_calls["extract"]
                    and FakeGroq.calls["verdict_result"] == app_calls["verify"],
    }
    print(f"\n=== {name}  ({users} users at once, fake Groq: {mode})")
    print(f"  HTTP: {dict(s['http'])}   request codes: {dict(s['codes'])}")
    print(f"  per-claim: {dict(s['claims'])}")
    print(f"  app -> LLM calls: {dict(app_calls)}   fake Groq received: {dict(FakeGroq.calls)}   "
          f"max parallel at Groq: {FakeGroq.max_inflight}")
    print(f"  slowest response: {max(r['ms'] for r in res)} ms   wall: {wall:.1f} s   provider text leaked: {s['leak']}")
    if VERBOSE:
        for kind, snippet in FakeGroq.log:
            print(f"     groq <- {kind}: {snippet}")
    problems = [msg for ok, msg in checks(s) + [(not s["leak"], "provider error text reached the client"),
                                               (s["no_retry"], "Groq received more calls than the app made (retries)")]
                if not ok]
    for p in problems:
        print("  !!", p)
    print("  OK" if not problems else "  FAILED")
    return not problems


async def run():
    asyncio.get_running_loop().set_default_executor(TrackingExecutor(max_workers=8))
    print(f"Guard: MAX_ACTIVE_VERIFICATIONS={main.guard.maximum}, per-IP limits={main.guard.limits}, "
          f"MAX_UPSTREAM_CONCURRENCY={main.settings.upstream_concurrency}, "
          f"CLAIM_CONCURRENCY={main.settings.pipeline.claim_concurrency}, LLM_TIMEOUT={main.settings.llm_timeout}s (test), "
          f"typed upstream errors: {TYPED_ERRORS}")
    m = main.guard.maximum
    ok = [
        await scenario("1. Groq healthy, more users than MAX_ACTIVE_VERIFICATIONS", "ok", m + 4, lambda s: [
            (s["http"].get(200, 0) == m, f"expected {m} results"),
            (s["codes"].get("BUSY", 0) == 4, "expected the rest to get BUSY")]),
        await scenario("2. Groq per-minute 429 on some verdict calls", "tpm429", 2, lambda s: [
            (s["http"].get(200, 0) == 2, "requests should still answer 200 (partial results)"),
            (any(k.startswith("error") for k in s["claims"]), "no claim marked as failed"),
            (not TYPED_ERRORS or any("UPSTREAM_RATE_LIMITED" in k for k in s["claims"]),
             "claim not marked UPSTREAM_RATE_LIMITED")]),
        await scenario("3. Groq daily quota used up (429 on everything)", "tpd429", 2, lambda s: [
            (all(r["http"] >= 500 for r in s["res"]), "expected a 5xx for every request"),
            (not TYPED_ERRORS or s["codes"].get("UPSTREAM_RATE_LIMITED", 0) == 2, "expected 503 UPSTREAM_RATE_LIMITED"),
            (max(r["ms"] for r in s["res"]) < 3000, "should fail fast")]),
        await scenario("4. Groq slower than LLM_TIMEOUT on verdicts", "slow", 2, lambda s: [
            (s["http"].get(200, 0) == 2, "requests should answer 200 with unfinished claims"),
            (all(k.startswith(("timeout", "error")) for k in s["claims"]), "claims should be timeout/error"),
            (max(r["ms"] for r in s["res"]) <= 10_500, "response exceeded TOTAL_TIMEOUT")]),
        await scenario("5. Groq 500 errors on verdicts", "error500", 2, lambda s: [
            (s["http"].get(200, 0) == 2, "requests should answer 200 with failed claims"),
            (all(k.startswith("error") for k in s["claims"]), "claims should be marked error")]),
        await scenario("6. Healthy again right after the slow scenario (BUSY slots released?)", "ok", 2, lambda s: [
            (s["http"].get(200, 0) == 2, "slots still held after timeouts")]),
    ]
    print("\nALL OK" if all(ok) else f"\n{ok.count(False)} scenario(s) FAILED")
    return all(ok)


if __name__ == "__main__":
    passed = asyncio.run(run())
    server.shutdown()
    raise SystemExit(0 if passed else 1)
