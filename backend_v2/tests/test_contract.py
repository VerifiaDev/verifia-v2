"""
API-level contract tests for POST /verify (and the shared error shape), through the
real FastAPI app with fake LLM/retrieval. What the frontend relies on is listed in
tests/contract.py; these tests make sure every outcome still satisfies it.
"""

from __future__ import annotations

import asyncio

import pytest

from contract import (
    CLAIM_ERROR_CODES,
    KNOWN_ERROR_CODES,
    invalid_citations,
    validate_error_body,
    validate_verify_response,
)


def post(client, text, **kw):
    return client.post("/verify", json={"text": text}, **kw)


# ---- happy path --------------------------------------------------------------

def test_ok_response_matches_frontend_contract(client):
    r = post(client, "metin")
    assert r.status_code == 200
    body = r.json()
    assert validate_verify_response(body) == []
    assert [c["claim_id"] for c in body["results"]] == ["c1", "c2", "c3"]  # original order
    assert body["partial"] is False
    by_id = {c["claim_id"]: c for c in body["results"]}
    assert by_id["c1"]["verdict"] == "SUPPORTED" and by_id["c3"]["verdict"] == "REFUTED"


def test_opinion_is_listed_but_not_judged(client):
    c2 = post(client, "metin").json()["results"][1]
    assert c2["is_verifiable"] is False and c2["verdict"] is None and c2["status"] == "ok"
    assert c2["sources"] == [] and c2["used_sources"] == []


def test_response_is_utf8_json(client):
    r = post(client, "metin")
    assert r.headers["content-type"].startswith("application/json")
    assert "Türkiye" in r.content.decode("utf-8")


# ---- sources -----------------------------------------------------------------

def test_sources_have_every_field_the_report_shows(client):
    c1 = post(client, "metin").json()["results"][0]
    assert len(c1["sources"]) == 2
    for s in c1["sources"]:
        assert {"id", "title", "domain", "url", "published_date", "text"} <= set(s)
    assert [s["published_date"] for s in c1["sources"]] == ["2024-05-01", None]


def test_hallucinated_source_ids_are_removed_from_used_sources(client):
    c1 = post(client, "metin").json()["results"][0]
    assert c1["used_sources"] == ["source_1"]  # source_99 dropped


def test_no_sources_gives_not_enough_evidence_without_llm_call(client, fake):
    fake.set_claims(("KAYNAKSIZ bir iddia", True))
    body = post(client, "metin").json()
    c = body["results"][0]
    assert validate_verify_response(body) == []
    assert c["verdict"] == "NOT ENOUGH EVIDENCE" and c["sources"] == [] and c["used_sources"] == []
    assert fake.calls["verify"] == 0


@pytest.mark.known_gap
@pytest.mark.xfail(reason="Mert / item 12: invalid [source_N] markers in the explanation are not cleaned")
def test_explanation_cites_only_existing_sources(client, fake):
    fake.explanation = "Doğru [source_1], ayrıca [source_7]."
    c1 = post(client, "metin").json()["results"][0]
    assert invalid_citations(c1) == []


# ---- partial results -----------------------------------------------------------

def test_one_failing_claim_gives_partial_result_not_a_500(client, fake):
    fake.set_claims(("iyi iddia", True), ("BOZUK iddia", True), ("KARARSIZ iddia", True))
    r = post(client, "metin")
    assert r.status_code == 200
    body = r.json()
    assert validate_verify_response(body) == []
    a, b, c = body["results"]
    assert a["status"] == "ok" and a["verdict"] == "SUPPORTED"
    assert (b["status"], b["error_code"], b["failed_stage"]) == ("error", "RETRIEVAL_FAILED", "retrieval")
    assert (c["status"], c["error_code"], c["failed_stage"]) == ("error", "VERDICT_FAILED", "verdict")
    assert b["verdict"] is None and c["verdict"] is None
    assert body["partial"] is True


def test_deadline_returns_partial_results_in_time(client, fake, monkeypatch):
    from app import main

    monkeypatch.setattr(main.settings.pipeline, "total_timeout", 0.5)
    monkeypatch.setattr(main.settings.pipeline, "claim_timeout", 60.0)
    fake.set_claims(("iyi iddia", True), ("ASILI iddia", True))
    body = post(client, "metin").json()
    assert validate_verify_response(body) == []
    assert body["results"][1]["status"] == "timeout"
    assert body["results"][1]["error_code"] == "DEADLINE_EXCEEDED"
    assert body["partial"] is True and body["timings"]["total_ms"] < 2000


def test_per_claim_timeout_names_the_stage(client, fake, monkeypatch):
    from app import main

    monkeypatch.setattr(main.settings.pipeline, "claim_timeout", 0.3)
    fake.set_claims(("ASILI iddia", True))
    c = post(client, "metin").json()["results"][0]
    assert (c["status"], c["error_code"], c["failed_stage"]) == ("timeout", "CLAIM_TIMEOUT", "retrieval")


def test_claims_over_the_cap_are_skipped_not_dropped(client, fake, monkeypatch):
    from app import main

    monkeypatch.setattr(main.settings.pipeline, "max_claims", 2)
    fake.set_claims(*[(f"iddia {i}", True) for i in range(4)])
    body = post(client, "metin").json()
    assert validate_verify_response(body) == []
    assert [c["status"] for c in body["results"]] == ["ok", "ok", "skipped", "skipped"]
    assert all(c["verdict"] is None for c in body["results"][2:])
    assert body["partial"] is True and fake.calls["retrieve"] == 2


def test_claim_error_codes_are_all_known():
    from app import pipeline

    src = open(pipeline.__file__, encoding="utf-8").read()
    import re

    used = set(re.findall(r'error_code="([A-Z_]+)"', src)) | {"RETRIEVAL_FAILED", "VERDICT_FAILED"}
    assert used <= CLAIM_ERROR_CODES, f"new per-claim code(s) {used - CLAIM_ERROR_CODES}: add to contract + frontend"


# ---- request-level errors ------------------------------------------------------

@pytest.mark.parametrize("payload,status,code", [
    ({}, 422, "VALIDATION_ERROR"),
    ({"text": ""}, 422, "VALIDATION_ERROR"),
    ({"text": 123}, 422, "VALIDATION_ERROR"),
    ({"text": "   \n  "}, 400, "EMPTY_TEXT"),
])
def test_bad_input_errors(client, payload, status, code):
    r = client.post("/verify", json=payload)
    assert r.status_code == status
    assert validate_error_body(r.json()) == []
    assert r.json()["error"] == code


def test_text_over_the_limit_is_rejected_with_a_known_code(client, fake):
    r = post(client, "a" * 10001)
    assert r.status_code in (413, 422)
    assert validate_error_body(r.json()) == []
    assert fake.calls["extract"] == 0


def test_malformed_json_body(client):
    r = client.post("/verify", content=b"{not json", headers={"content-type": "application/json"})
    assert r.status_code == 422 and r.json()["error"] == "VALIDATION_ERROR"


def test_extraction_failure_is_502_with_known_code(client, fake):
    fake.extract_error = ValueError("groq 401 invalid api key")
    r = post(client, "metin")
    assert r.status_code == 502
    assert validate_error_body(r.json()) == [] and r.json()["error"] == "EXTRACTION_FAILED"


def test_extraction_timeout_is_504(client, fake, monkeypatch):
    from app import main

    monkeypatch.setattr(main.settings.pipeline, "extract_timeout", 0.2)
    fake.extract_delay = 2
    r = post(client, "metin")
    assert r.status_code == 504 and r.json()["error"] == "EXTRACTION_TIMEOUT"
    assert validate_error_body(r.json()) == []


def test_unexpected_crash_is_500_verify_failed(client, monkeypatch):
    from app import main

    async def boom(*a, **k):
        raise KeyError("surprise")

    monkeypatch.setattr(main, "run_pipeline", boom)
    r = post(client, "metin")
    assert r.status_code == 500 and r.json()["error"] == "VERIFY_FAILED"


def test_error_detail_hidden_when_expose_detail_is_off(client, fake, monkeypatch):
    from app import main

    monkeypatch.setattr(main.settings.pipeline, "expose_detail", False)
    fake.extract_error = ValueError("secret-ish internal message")
    body = post(client, "metin").json()
    assert "secret-ish" not in str(body)


def test_missing_config_is_503_config_error(client, monkeypatch):
    from app import main

    monkeypatch.setitem(main.state, "init_error", "Eksik ortam değişkenleri: GROQ_API_KEY")
    for path in ("/verify", "/verify/stream"):
        r = client.post(path, json={"text": "metin"})
        assert r.status_code == 503 and r.json()["error"] == "CONFIG_ERROR", path
        assert validate_error_body(r.json()) == []


@pytest.mark.known_gap
@pytest.mark.xfail(reason="Fatih / item 3: CONFIG_ERROR always includes `detail`, even with EXPOSE_ERROR_DETAIL=0")
def test_config_error_detail_respects_expose_detail(client, monkeypatch):
    from app import main

    monkeypatch.setattr(main.settings.pipeline, "expose_detail", False)
    monkeypatch.setitem(main.state, "init_error", "Eksik ortam değişkenleri: GROQ_API_KEY")
    assert "GROQ_API_KEY" not in str(post(client, "metin").json())


def test_every_error_code_in_main_is_known_to_the_frontend():
    import re

    from app import main

    src = open(main.__file__, encoding="utf-8").read()
    codes = set(re.findall(r'"error":\s*"([A-Z_]+)"', src))
    assert codes and codes <= KNOWN_ERROR_CODES, f"unknown to frontend: {codes - KNOWN_ERROR_CODES}"


# ---- health ----------------------------------------------------------------------

def test_health_is_cheap_and_reports_readiness(client, fake):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert fake.calls == {"extract": 0, "retrieve": 0, "verify": 0}


def test_health_never_contains_api_keys(client, monkeypatch):
    from app import main

    text = client.get("/health").text
    for key in (main.settings.groq_api_key, main.settings.tavily_api_key):
        if key:
            assert key not in text


# ---- cache keeps the contract -----------------------------------------------------

def test_cached_answer_has_the_same_shape(client, fake, monkeypatch):
    from app import main
    from app.pipeline import TTLCache

    monkeypatch.setitem(main.state, "cache", TTLCache())
    first = post(client, "metin").json()
    second = post(client, "metin").json()
    assert validate_verify_response(second) == []
    assert fake.calls["retrieve"] == 2  # second request fully cached
    assert [c.get("cached", False) for c in second["results"] if c["is_verifiable"]] == [True, True]
    strip = lambda b: [{k: v for k, v in c.items() if k not in ("cached", "timings_ms")} for c in b["results"]]  # noqa: E731
    assert strip(first) == strip(second)


def test_concurrent_requests_do_not_mix_results(client, fake):
    import concurrent.futures as cf

    fake.retrieve_delay = 0.05
    with cf.ThreadPoolExecutor(4) as ex:
        bodies = list(ex.map(lambda _: post(client, "metin").json(), range(4)))
    for b in bodies:
        assert validate_verify_response(b) == []
        assert [c["claim_id"] for c in b["results"]] == ["c1", "c2", "c3"]


def test_asyncio_is_not_left_with_pending_tasks(fake):
    """run_pipeline on its own leaves nothing behind after a normal run."""
    from app.pipeline import run_pipeline

    async def go():
        await run_pipeline("x", extract=fake.extract, retrieve=fake.retrieve, verify=fake.verify)
        return [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    assert asyncio.run(go()) == []
