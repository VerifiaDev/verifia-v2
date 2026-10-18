"""Offline security regression tests; existing contract/load suites are unchanged."""
import asyncio
import logging
import threading

import httpx
import pytest

from app import main, security
from app.resources import TrackingExecutor, current_lease, Lease
from app.security import Guard


@pytest.fixture(autouse=True)
def memory_probe(monkeypatch):
    monkeypatch.setattr(security, "memory_mb", lambda: (100, 120))


@pytest.mark.parametrize("repeat", range(2))
def test_guard_is_fresh_and_enforces_default_quota(client, fake, monkeypatch, repeat):
    # Both cases must start empty, including when middleware is already built.
    assert main.guard.clients == {} and main.guard.global_count == (0, 0)
    assert main.guard.active == 0
    assert main.guard.maximum == 2
    assert main.guard.memory_limit == 384
    assert main.guard.limits == [(60, 10), (3600, 100), (86400, 500)]
    assert main.guard.global_daily == 1000
    from types import SimpleNamespace
    monkeypatch.setattr(security, "time", SimpleNamespace(time=lambda: 100000))
    for _ in range(10):
        assert client.post("/verify", json={"text": "test"}).status_code == 200
    calls = dict(fake.calls)
    r = client.post("/verify/stream", json={"text": "test"})
    assert r.status_code == 429 and r.json()["error"] == "RATE_LIMITED"
    assert int(r.headers["retry-after"]) > 0
    assert fake.calls == calls


@pytest.mark.parametrize("path", ["/verify", "/verify/stream"])
def test_body_limit_and_request_id(client, fake, path):
    r = client.post(path, content=b"x" * 65537, headers={"Origin": "http://localhost:3000", "X-Request-ID": "security-test-123"})
    assert r.status_code == 413
    assert r.json()["error"] == "BODY_TOO_LARGE"
    assert r.headers["x-request-id"] == "security-test-123"
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert fake.calls["extract"] == 0


def test_quota_shared_between_endpoints(client, monkeypatch):
    monkeypatch.setattr(main.guard, "limits", [(60, 1)])
    assert client.post("/verify", json={"text": "test"}).status_code == 200
    r = client.post("/verify/stream", json={"text": "test"})
    assert r.status_code == 429 and r.json()["error"] == "RATE_LIMITED"
    assert int(r.headers["retry-after"]) > 0
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize("unavailable", [False, True])
def test_memory_fail_closed(client, fake, monkeypatch, unavailable):
    def measure():
        if unavailable:
            raise OSError("private path")
        return (main.guard.memory_limit + 1, 999)
    monkeypatch.setattr(security, "memory_mb", measure)
    r = client.post("/verify", json={"text": "test"})
    assert r.status_code == 503 and r.json()["error"] == "LOW_MEMORY"
    assert fake.calls["extract"] == 0


def test_busy_and_release(fake, monkeypatch):
    fake.extract_delay = 0.1
    monkeypatch.setattr(main.guard, "maximum", 1)
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as c:
            first = asyncio.create_task(c.post("/verify/stream", json={"text": "first"}))
            await asyncio.sleep(0.02)
            busy = await c.post("/verify", json={"text": "second"})
            assert busy.status_code == 429 and busy.json()["error"] == "BUSY"
            assert (await first).status_code == 200
            assert main.guard.active == 0
            assert (await c.post("/verify", json={"text": "third"})).status_code == 200
    asyncio.run(go())


def test_proxy_spoofing(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "10.0.0.0/8")
    g = Guard()
    def scope(peer, forwarded):
        return {"client": (peer, 1), "headers": [(b"x-forwarded-for", forwarded)]}
    assert g.client_ip(scope("192.0.2.1", b"1.1.1.1")) == "192.0.2.1"
    assert g.client_ip(scope("10.0.0.1", b"spoof, 192.0.2.2, 10.0.0.2")) == "192.0.2.2"
    assert g.client_ip(scope("10.0.0.1", b"invalid")) == "10.0.0.1"


def test_quota_bounded_global_and_rollover(monkeypatch):
    g = Guard()
    g.client_limit = 1
    g.limits = [(60, 1)]
    g.global_daily = 2
    monkeypatch.setattr(security.time, "time", lambda: 100000)
    assert g.quota("a") == 0
    assert g.quota("a") > 0 and g.quota("b") > 0
    monkeypatch.setattr(security.time, "time", lambda: 200000)
    assert g.quota("b") == 0 and len(g.clients) == 1
    g.global_daily = 1
    assert g.quota("b") > 0


def test_logs_redact_exception_and_path(client, fake, caplog):
    caplog.set_level(logging.INFO)
    fake.extract_error = RuntimeError("SECRET-PROVIDER-KEY")
    client.post("/verify", json={"text": "test"})
    client.get("/SECRET-PATH")
    assert "SECRET-PROVIDER-KEY" not in caplog.text
    assert "SECRET-PATH" not in caplog.text


def test_cancelled_thread_retains_admission():
    async def go():
        g = Guard()
        g.active = 1
        lease = Lease(g)
        gate = threading.Event()
        executor = TrackingExecutor(max_workers=1)
        token = current_lease.set(lease)
        try:
            future = executor.submit(gate.wait)
            lease.finished = True
            lease.release_if_done()
            assert g.active == 1
            gate.set()
            await asyncio.wrap_future(future)
            await asyncio.sleep(0)
            assert g.active == 0
        finally:
            gate.set()
            current_lease.reset(token)
            executor.shutdown(wait=True)
    asyncio.run(go())


def test_chunked_body_limit_without_content_length(fake):
    async def go():
        async def chunks():
            yield b"x" * 40000
            yield b"y" * 40000
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as c:
            r = await c.post("/verify/stream", content=chunks())
            assert r.status_code == 413
            assert fake.calls["extract"] == 0
    asyncio.run(go())


@pytest.mark.parametrize("length", ["-1", "invalid"])
def test_invalid_content_length(client, fake, length):
    r = client.post("/verify", content=b"{}", headers={"Content-Length": length})
    assert r.status_code == 400 and fake.calls["extract"] == 0


def test_generic_error_before_response_is_safe(monkeypatch):
    from fastapi.testclient import TestClient
    from app.observability import RequestContextMiddleware
    async def broken(scope, receive, send):
        raise RuntimeError("PRIVATE-ERROR")
    app = RequestContextMiddleware(security.SecurityMiddleware(broken, Guard()))
    r = TestClient(app).get("/")
    assert r.status_code == 500 and r.json()["error"] == "INTERNAL_ERROR"
    assert "PRIVATE" not in r.text and r.headers["x-request-id"]


def test_sdk_child_log_is_redacted():
    from app.safe_logging import SafeOutputLog
    record = logging.LogRecord("httpcore.connection", logging.DEBUG, __file__, 1,
                               "provider key=%s", ("PRIVATE-KEY",), None)
    assert SafeOutputLog().filter(record)
    assert "PRIVATE-KEY" not in record.getMessage()


def test_real_memory_probe():
    from app.resources import memory_mb
    rss, peak = memory_mb()
    assert rss > 0 and peak >= rss


@pytest.mark.parametrize("os_peak_kib, expected_peak", [(70444, 69.046875), (102400, 100.0)])
def test_linux_memory_peak_includes_current_sample(monkeypatch, os_peak_kib, expected_peak):
    import sys
    from pathlib import Path
    from types import SimpleNamespace
    from app import resources

    # Exercise Linux conversion/accounting on Windows too. These values reproduce
    # the CI mismatch: current 69.046875 MiB versus OS peak 68.79296875 MiB.
    monkeypatch.setattr(resources, "os", SimpleNamespace(
        name="posix", sysconf=lambda name: 4096,
    ))
    monkeypatch.setitem(sys.modules, "resource", SimpleNamespace(
        RUSAGE_SELF=0, getrusage=lambda who: SimpleNamespace(ru_maxrss=os_peak_kib),
    ))

    def statm(path):
        assert path.as_posix() == "/proc/self/statm"
        return "20000 17676 0 0 0 0 0\n"

    monkeypatch.setattr(Path, "read_text", statm)
    rss, peak = resources.memory_mb()
    assert rss == 69.046875  # Never lower the current RSS used by admission control.
    assert peak == expected_peak


def test_thread_cancellation_retains_slot_until_worker_finishes():
    async def go():
        g = Guard()
        g.active = 1
        lease = Lease(g)
        started, stop = threading.Event(), threading.Event()
        executor = TrackingExecutor(max_workers=1)
        asyncio.get_running_loop().set_default_executor(executor)
        def worker():
            started.set()
            stop.wait()
        token = current_lease.set(lease)
        try:
            task = asyncio.create_task(asyncio.to_thread(worker))
            while not started.is_set():
                await asyncio.sleep(0.001)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            lease.finished = True
            lease.release_if_done()
            assert g.active == 1
            stop.set()
            for _ in range(100):
                if g.active == 0:
                    break
                await asyncio.sleep(0.001)
            assert g.active == 0
        finally:
            stop.set()
            current_lease.reset(token)
            executor.shutdown(wait=True)
    asyncio.run(go())


def test_stream_disconnect_releases_admission(fake):
    from test_stream import _asgi_post_and_disconnect
    fake.set_claims(("ASILI claim", True))
    async def go():
        await _asgi_post_and_disconnect(main.app, "/verify/stream", b'{"text":"test"}',
                                        b"event: claims", use_receive=True)
        await asyncio.sleep(0)
        assert main.guard.active == 0
    asyncio.run(go())
