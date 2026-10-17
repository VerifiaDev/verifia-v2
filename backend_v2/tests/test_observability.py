"""Request ids, request logs, stage-timing logs, and what must never be logged."""

from __future__ import annotations

import logging
import re

import pytest

from app.observability import LOG_FORMAT, accept_request_id, log_pipeline_result


@pytest.mark.parametrize("raw,kept", [
    ("frontend-abc-123", True),
    ("a1b2c3d4", True),
    ("x" * 64, True),
    ("short", False),                 # < 8 chars
    ("x" * 65, False),                # too long
    ("bad id with spaces", False),
    ("evil\nrid=admin", False),       # log injection
    ("ünicode-id-123", False),
    (None, False),
])
def test_accept_request_id(raw, kept):
    rid = accept_request_id(raw)
    assert (rid == raw) is kept
    assert re.fullmatch(r"[A-Za-z0-9._-]{8,64}", rid)


def test_every_response_has_a_request_id(client):
    ids = set()
    for method, path in (("GET", "/"), ("GET", "/health"), ("POST", "/verify")):
        r = client.request(method, path, json={"text": "metin"} if method == "POST" else None)
        ids.add(r.headers["x-request-id"])
    assert len(ids) == 3  # a fresh id per request


def test_error_responses_have_a_request_id_too(client):
    r = client.post("/verify", json={})
    assert r.status_code == 422 and r.headers.get("x-request-id")


def test_valid_incoming_request_id_is_echoed(client):
    r = client.get("/health", headers={"X-Request-ID": "frontend-abc-123"})
    assert r.headers["x-request-id"] == "frontend-abc-123"


def test_invalid_incoming_request_id_is_replaced(client):
    r = client.get("/health", headers={"X-Request-ID": "bad id"})
    assert r.headers["x-request-id"] != "bad id"
    assert len(r.headers.get_list("x-request-id")) == 1


def test_cors_preflight_has_a_request_id(client):
    r = client.options("/verify", headers={"Origin": "https://verify-test-swart.vercel.app",
                                           "Access-Control-Request-Method": "POST"})
    assert r.headers.get("x-request-id")


def test_browser_javascript_may_read_the_request_id(client):
    """Without Access-Control-Expose-Headers the frontend's fetch() cannot see X-Request-ID."""
    r = client.post("/verify", json={"text": "metin"}, headers={"Origin": "https://verify-test-swart.vercel.app"})
    exposed = [h.strip().lower() for h in r.headers.get("access-control-expose-headers", "").split(",")]
    assert "x-request-id" in exposed


def test_logs_carry_request_id_and_stage_timings(client, caplog):
    caplog.set_level(logging.INFO)
    rid = "trace-me-12345"
    client.post("/verify", json={"text": "metin"}, headers={"X-Request-ID": rid})

    mine = [r for r in caplog.records if getattr(r, "request_id", None) == rid]
    msgs = [r.getMessage() for r in mine]
    assert any(r.name == "verify.request" and "POST /verify -> 200" in r.getMessage() for r in mine)
    claim_lines = [m for m in msgs if m.startswith("claim ")]
    assert len(claim_lines) == 2  # one per verifiable claim
    assert all(re.search(r"retrieval_ms=\d+ verify_ms=\d+", m) for m in claim_lines)
    assert any(m.startswith("verify summary") and "extract_ms=" in m for m in msgs)


def test_stream_logs_carry_the_same_request_id(client, caplog):
    caplog.set_level(logging.INFO)
    rid = "stream-trace-999"
    with client.stream("POST", "/verify/stream", json={"text": "metin"}, headers={"X-Request-ID": rid}) as r:
        "".join(r.iter_text())
    msgs = [r.getMessage() for r in caplog.records if getattr(r, "request_id", None) == rid]
    assert any(m.startswith("verify summary") for m in msgs)
    assert any("POST /verify/stream -> 200" in m for m in msgs)


def test_failed_claims_are_logged_with_code_and_stage(client, fake, caplog):
    caplog.set_level(logging.INFO)
    fake.set_claims(("BOZUK iddia", True))
    client.post("/verify", json={"text": "metin"})
    assert any("error=RETRIEVAL_FAILED@retrieval" in r.getMessage() for r in caplog.records)


def test_user_text_and_claim_text_are_never_logged(client, fake, caplog):
    caplog.set_level(logging.DEBUG)
    secret_text = "GIZLI-KULLANICI-METNI-42"
    fake.set_claims((f"{secret_text} iddiası", True), ("BOZUK " + secret_text, True))
    client.post("/verify", json={"text": secret_text})
    with client.stream("POST", "/verify/stream", json={"text": secret_text}) as r:
        "".join(r.iter_text())
    for rec in caplog.records:
        assert secret_text not in rec.getMessage(), f"{rec.name} logged user text"
        assert not rec.exc_text or secret_text not in rec.exc_text


def test_log_format_has_request_id_and_works_outside_requests():
    rec = logging.getLogger("verify.test").makeRecord("verify.test", logging.INFO, __file__, 1, "hi", (), None)
    line = logging.Formatter(LOG_FORMAT).format(rec)
    assert "rid=-" in line


def test_log_pipeline_result_handles_minimal_input(caplog):
    caplog.set_level(logging.INFO)
    log_pipeline_result({"results": [], "partial": False, "timings": {}})
    assert any("verify summary claims=0" in r.getMessage() for r in caplog.records)
