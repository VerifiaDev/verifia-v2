"""
POST /verify/stream: event order and shape, partial results and errors over SSE,
keep-alive, client disconnect and cancellation.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from contract import parse_sse, validate_stream


def stream(client, text="metin", headers=None):
    with client.stream("POST", "/verify/stream", json={"text": text}, headers=headers or {}) as r:
        raw = "".join(r.iter_text())
        return r, raw


def names(events):
    return [n for n, _ in events]


# ---- order and shape ------------------------------------------------------------

def test_stream_headers(client):
    r, _ = stream(client)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["cache-control"] == "no-cache"
    assert r.headers["x-accel-buffering"] == "no"


def test_happy_path_event_order(client):
    _, raw = stream(client)
    ev = parse_sse(raw)
    assert validate_stream(ev) == []
    n = names(ev)
    assert n[:4] == ["started", "stage", "stage", "claims"]
    assert ev[1][1] == {"type": "stage", "stage": "extract", "status": "started"}
    assert ev[2][1]["stage"] == "extract" and ev[2][1]["status"] == "finished" and isinstance(ev[2][1]["ms"], int)
    assert ev[4][1] == {"type": "stage", "stage": "verify", "status": "started", "total": 3}
    assert n.count("result") == 3
    assert n[-2:] == ["stage", "done"]
    assert ev[-2][1]["stage"] == "verify" and ev[-2][1]["status"] == "finished"
    done = ev[-1][1]
    assert done["partial"] is False and {"extract_ms", "total_ms"} <= set(done["timings"])


def test_unverifiable_claim_is_streamed_first(client, fake):
    fake.retrieve_delay = 0.05
    ev = parse_sse(stream(client)[1])
    first_result = next(d for n, d in ev if n == "result")["result"]
    assert first_result["claim_id"] == "c2" and first_result["verdict"] is None


def test_stream_results_equal_the_verify_results(client):
    body = client.post("/verify", json={"text": "metin"}).json()
    ev = parse_sse(stream(client)[1])
    streamed = {d["result"]["claim_id"]: d["result"] for n, d in ev if n == "result"}
    for c in body["results"]:
        s = streamed[c["claim_id"]]
        for k in ("claim", "is_verifiable", "verdict", "explanation", "used_sources", "sources", "status"):
            assert s[k] == c[k], k


def test_utf8_is_not_escaped(client):
    _, raw = stream(client)
    assert "Türkiye" in raw and "\\u" not in raw


def test_old_event_shapes_are_unchanged(client):
    """claims/result/done/error keep their earlier fields; only additions are allowed."""
    ev = dict((n, d) for n, d in parse_sse(stream(client)[1]) if n in ("claims", "done"))
    assert {"type", "claims", "extract_ms"} <= set(ev["claims"])
    assert {"claim_id", "claim", "is_verifiable"} <= set(ev["claims"]["claims"][0])
    assert {"type", "partial", "timings"} <= set(ev["done"])


# ---- request id ------------------------------------------------------------------------

def test_request_id_in_header_started_and_done(client):
    r, raw = stream(client, headers={"X-Request-ID": "frontend-abc-123"})
    ev = parse_sse(raw)
    assert r.headers["x-request-id"] == "frontend-abc-123"
    assert ev[0][1]["request_id"] == "frontend-abc-123" and ev[-1][1]["request_id"] == "frontend-abc-123"


# ---- partial results and errors ---------------------------------------------------------

def test_partial_results_over_the_stream(client, fake, monkeypatch):
    from app import main

    monkeypatch.setattr(main.settings.pipeline, "max_claims", 2)
    fake.set_claims(("iyi", True), ("BOZUK", True), ("üçüncü", True))
    ev = parse_sse(stream(client)[1])
    assert validate_stream(ev) == []
    st = {d["result"]["claim_id"]: d["result"]["status"] for n, d in ev if n == "result"}
    assert st == {"c1": "ok", "c2": "error", "c3": "skipped"}
    assert ev[-1][1]["partial"] is True


def test_deadline_over_the_stream(client, fake, monkeypatch):
    from app import main

    monkeypatch.setattr(main.settings.pipeline, "total_timeout", 0.5)
    monkeypatch.setattr(main.settings.pipeline, "claim_timeout", 60.0)
    fake.set_claims(("iyi", True), ("ASILI", True))
    ev = parse_sse(stream(client)[1])
    assert validate_stream(ev) == []
    timed_out = [d["result"] for n, d in ev if n == "result" and d["result"]["status"] == "timeout"]
    assert [r["error_code"] for r in timed_out] == ["DEADLINE_EXCEEDED"]


def test_extraction_failure_is_a_single_error_event(client, fake):
    fake.extract_error = ValueError("groq 401")
    r, raw = stream(client)
    ev = parse_sse(raw)
    assert r.status_code == 200  # headers are already sent when the pipeline fails
    assert validate_stream(ev) == []
    assert names(ev) == ["started", "stage", "error"]
    err = ev[-1][1]
    assert err["error"] == "EXTRACTION_FAILED" and err["message"] and err["request_id"]


@pytest.mark.parametrize("expose", [True, False])
def test_error_detail_follows_expose_detail(client, fake, monkeypatch, expose):
    """memory item 3 (stream part): detail used to be sent even with EXPOSE_ERROR_DETAIL=0."""
    from app import main

    monkeypatch.setattr(main.settings.pipeline, "expose_detail", expose)
    monkeypatch.setattr(main, "run_pipeline", _boom)
    err = parse_sse(stream(client)[1])[-1][1]
    assert err["error"] == "VERIFY_FAILED"
    assert ("detail" in err) is expose
    assert ("internal path /srv/x" in json.dumps(err)) is expose


async def _boom(*a, **k):
    raise RuntimeError("internal path /srv/x")


def test_blank_text_is_rejected_before_any_llm_call(client, fake):
    r = client.post("/verify/stream", json={"text": "   "})
    assert r.status_code == 400 and r.json()["error"] == "EMPTY_TEXT"
    assert fake.calls["extract"] == 0


def test_invalid_body_is_422_not_a_stream(client):
    r = client.post("/verify/stream", json={})
    assert r.status_code == 422 and r.json()["error"] == "VALIDATION_ERROR"


def test_no_claims_still_finishes(client, fake):
    fake.set_claims()
    ev = parse_sse(stream(client)[1])
    assert validate_stream(ev) == []
    assert names(ev)[-1] == "done"
    assert next(d for n, d in ev if n == "stage" and d["stage"] == "verify")["total"] == 0


# ---- keep-alive, disconnect, cancellation ----------------------------------------------

def _make_stream(run, keepalive=15.0):
    from app.streaming import VerificationStream

    return VerificationStream(run, request_id="test-request-1", expose_detail=True, keepalive=keepalive)


def test_keep_alive_comment_while_waiting():
    async def slow_run(emit):
        await asyncio.sleep(0.35)
        return {"partial": False, "timings": {}}

    async def go():
        s = _make_stream(slow_run, keepalive=0.1)
        return [chunk async for chunk in s.events()]

    chunks = asyncio.run(go())
    assert chunks.count(": keep-alive\n\n") >= 2
    assert parse_sse("".join(chunks))[-1][0] == "done"


def test_closing_the_stream_cancels_the_pipeline():
    state = {"cancelled": False}

    async def run(emit):
        await emit({"type": "claims", "claims": [], "extract_ms": 1})
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            state["cancelled"] = True
            raise
        return {}

    async def go():
        s = _make_stream(run)
        it = s.events()
        seen = []
        async for chunk in it:
            seen.append(chunk)
            if "event: claims" in chunk:
                break
        await it.aclose()
        await s.aclose(disconnected=True)
        return s, seen

    s, seen = asyncio.run(go())
    assert state["cancelled"] is True and s.cancelled is True


async def _asgi_post_and_disconnect(app, path, body, disconnect_after: bytes, *, use_receive: bool):
    """Drive the ASGI app directly: send the request, then drop the connection as soon as
    `disconnect_after` appears in the body. use_receive=True -> the client signals
    http.disconnect; False -> the next write fails with OSError (ASGI spec >= 2.4 style)."""
    sent_body = False
    gone = asyncio.Event()
    chunks: list = []

    async def receive():
        nonlocal sent_body
        if not sent_body:
            sent_body = True
            return {"type": "http.request", "body": body, "more_body": False}
        await gone.wait()
        if use_receive:
            return {"type": "http.disconnect"}
        await asyncio.sleep(3600)

    async def send(message):
        if gone.is_set() and not use_receive and message["type"] == "http.response.body":
            raise OSError("client gone")
        if message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))
            if disconnect_after in b"".join(chunks):
                gone.set()

    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"}, "http_version": "1.1",
        "method": "POST", "scheme": "http", "path": path, "raw_path": path.encode(), "root_path": "",
        "query_string": b"", "server": ("test", 80), "client": ("127.0.0.1", 1),
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
    }
    await asyncio.wait_for(app(scope, receive, send), timeout=5)
    return b"".join(chunks)


@pytest.mark.parametrize("use_receive", [True, False], ids=["http.disconnect", "write-fails"])
def test_client_disconnect_stops_the_stream_quickly(fake, monkeypatch, use_receive):
    from app import main

    for k, v in dict(total_timeout=30.0, claim_timeout=30.0).items():
        monkeypatch.setattr(main.settings.pipeline, k, v)
    fake.set_claims(("ASILI bir", True), ("ASILI iki", True))

    seen = {}
    real_aclose = main.VerificationStream.aclose

    async def spy(self, *, disconnected=False):
        await real_aclose(self, disconnected=disconnected)
        seen["cancelled"], seen["disconnected"] = self.cancelled, disconnected

    monkeypatch.setattr(main.VerificationStream, "aclose", spy)
    if not use_receive:  # a write must happen after the drop for the OSError path
        monkeypatch.setattr("app.streaming.KEEPALIVE_SECONDS", 0.1)
        orig_init = main.VerificationStream.__init__

        def init(self, *a, **k):
            orig_init(self, *a, **{**k, "keepalive": 0.1})

        monkeypatch.setattr(main.VerificationStream, "__init__", init)

    async def go():
        t = asyncio.get_running_loop().time()
        out = await _asgi_post_and_disconnect(main.app, "/verify/stream", json.dumps({"text": "metin"}).encode(),
                                              b"event: claims", use_receive=use_receive)
        return out, asyncio.get_running_loop().time() - t

    out, took = asyncio.run(go())
    assert b"event: claims" in out and b"event: done" not in out
    assert took < 2, f"handler kept running {took:.1f}s after the client left"
    assert seen == {"cancelled": True, "disconnected": True}


def test_cancelling_the_pipeline_cancels_claim_work(fake):
    """Cancelling run_pipeline must cancel running claims AND claims still waiting on the
    semaphore. (Threads already inside Groq/Tavily calls still cannot be stopped: item 13.)"""
    from app.pipeline import PipelineConfig, run_pipeline

    fake.set_claims(("ASILI bir", True), ("ASILI iki", True), ("bekleyen üç", True))

    async def go():
        task = asyncio.create_task(run_pipeline("x", extract=fake.extract, retrieve=fake.retrieve,
                                                verify=fake.verify, cfg=PipelineConfig(claim_concurrency=2)))
        while fake.retrieve_started < 2:
            await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.sleep(0.05)
        return [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    leftover = asyncio.run(go())
    assert fake.retrieve_cancelled == 2 and leftover == []
    assert fake.retrieve_started == 2, "the queued third claim must not start after cancellation"


def test_disconnect_cancels_claim_work_end_to_end(fake, monkeypatch):
    from app import main

    monkeypatch.setattr(main.settings.pipeline, "total_timeout", 30.0)
    monkeypatch.setattr(main.settings.pipeline, "claim_timeout", 30.0)
    monkeypatch.setattr(main.settings.pipeline, "claim_concurrency", 2)
    fake.set_claims(("ASILI bir", True), ("ASILI iki", True), ("bekleyen üç", True))

    async def go():
        await _asgi_post_and_disconnect(main.app, "/verify/stream", json.dumps({"text": "metin"}).encode(),
                                        b"event: claims", use_receive=True)
        await asyncio.sleep(0.05)
        return [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    leftover = asyncio.run(go())
    assert leftover == []
    assert (fake.retrieve_started, fake.retrieve_cancelled) == (2, 2)
