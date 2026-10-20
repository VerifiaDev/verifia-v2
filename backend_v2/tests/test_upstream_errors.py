"""Real SDK + mock HTTP transport; no provider requests or credentials."""
import json
from types import SimpleNamespace as NS

import groq
import httpx
import pytest

from app import llm, main
from app.upstream_errors import InvalidModelResponse, UpstreamError, UpstreamRateLimited, UpstreamTimeout
from contract import validate_error_body, validate_verify_response, validate_stream


SENSITIVE = "private-provider-marker reasoning"


def mock_llm(monkeypatch, outcome):
    calls = []

    def respond(request):
        calls.append(request)
        if outcome == "timeout":
            raise httpx.ReadTimeout(SENSITIVE, request=request)
        if isinstance(outcome, dict):
            return httpx.Response(200, json=outcome)
        return httpx.Response(outcome, json={"error": {"message": SENSITIVE}})

    client = groq.Groq(
        api_key="offline-placeholder",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    ae = llm._import_ai_engine()
    monkeypatch.setattr(ae, "Groq", lambda **kwargs: client)
    instance = llm.LLM(NS(
        groq_api_key="offline-placeholder", model_name="openai/gpt-oss-20b",
        reasoning_effort="low", llm_timeout=1,
    ))
    return instance, calls, client


@pytest.mark.parametrize("outcome,kind", [
    (429, UpstreamRateLimited), ("timeout", UpstreamTimeout),
    (400, UpstreamError), (401, UpstreamError), (500, UpstreamError),
])
def test_sdk_classification_and_no_retry(monkeypatch, outcome, kind):
    instance, calls, client = mock_llm(monkeypatch, outcome)
    try:
        assert instance.engine.client.max_retries == 0
        assert instance.engine.client.timeout == 1
        with pytest.raises(kind) as caught:
            instance.engine.extract_claims("offline input")
        assert type(caught.value) is kind
        assert SENSITIVE not in str(caught.value)
        assert caught.value.__suppress_context__
        assert len(calls) == 1
        assert json.loads(calls[0].content)["reasoning_effort"] == "low"
    finally:
        client.close()


def test_client_options_failure_does_not_use_defaults(monkeypatch):
    class BrokenClient:
        def with_options(self, **kwargs):
            raise ValueError(SENSITIVE)

    class Base:
        def __init__(self, **kwargs):
            self.client = BrokenClient()

    monkeypatch.setattr(llm, "_import_ai_engine", lambda: NS(FactCheckEngine=Base))
    with pytest.raises(RuntimeError) as caught:
        llm.make_engine(NS(reasoning_effort="low", groq_api_key="offline-placeholder",
                           model_name="offline-model", llm_timeout=1))
    assert SENSITIVE not in str(caught.value)


def events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


@pytest.mark.parametrize("path", ["/verify", "/verify/stream"])
@pytest.mark.parametrize("expose", [False, True])
@pytest.mark.parametrize("outcome,status,code", [
    (429, 503, "UPSTREAM_RATE_LIMITED"),
    ("timeout", 504, "EXTRACTION_TIMEOUT"),
    (500, 502, "EXTRACTION_FAILED"),
])
def test_extraction_sdk_errors(client, monkeypatch, path, expose, outcome, status, code):
    instance, calls, sdk = mock_llm(monkeypatch, outcome)
    monkeypatch.setitem(main.state, "llm", instance)
    monkeypatch.setattr(main.settings.pipeline, "expose_detail", expose)
    try:
        response = client.post(path, json={"text": "offline input"})
        assert response.status_code == (200 if path.endswith("stream") else status)
        if path.endswith("stream"):
            data = events(response)
            assert validate_stream([(e["type"], e) for e in data]) == []
            assert [e["type"] for e in data] == ["started", "stage", "error"]
            body = data[-1]
        else:
            body = response.json()
            assert validate_error_body(body) == []
            assert body["status"] == "error"
        assert body["error"] == code
        assert body["message"]
        if outcome != 500:
            assert "detail" not in body
        assert SENSITIVE not in response.text
        assert "offline-placeholder" not in response.text
        assert len(calls) == 1
    finally:
        sdk.close()


def broken_completion(kind):
    content = {
        "json": "{broken-json " + SENSITIVE,
        "schema": json.dumps({"claims": SENSITIVE, "verdict": SENSITIVE}),
        "missing_content": None,
        "verdict": json.dumps({"claim_id": "c2", "verdict": SENSITIVE,
                               "explanation": SENSITIVE, "used_sources": []}),
    }[kind]
    return {"id": "offline-completion", "object": "chat.completion", "created": 0,
            "model": "offline-model",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": content}}]}


@pytest.mark.parametrize("kind", ["json", "schema", "missing_content", "verdict"])
def test_model_response_error_is_safe(monkeypatch, kind):
    instance, calls, sdk = mock_llm(monkeypatch, broken_completion(kind))
    try:
        with pytest.raises(InvalidModelResponse) as caught:
            if kind == "verdict":
                instance.engine.verify_claim("offline input", [])
            else:
                instance.engine.extract_claims("offline input")
        assert str(caught.value) == "Yapay zekâ servisinin yanıtı işlenemedi."
        assert len(calls) == 1
    finally:
        sdk.close()


@pytest.mark.parametrize("path", ["/verify", "/verify/stream"])
@pytest.mark.parametrize("expose", [False, True])
@pytest.mark.parametrize("stage", ["extract", "verdict"])
@pytest.mark.parametrize("kind", ["json", "schema", "missing_content", "verdict"])
def test_invalid_model_response_never_exposes_details(client, fake, monkeypatch,
                                                     path, expose, stage, kind):
    if stage == "extract" and kind == "verdict":
        pytest.skip("Verdict label validation only applies to the verdict stage")
    instance, calls, sdk = mock_llm(monkeypatch, broken_completion(kind))
    if stage == "extract":
        monkeypatch.setitem(main.state, "llm", instance)
    else:
        fake.set_claims(("successful claim", True), ("failing claim", True))

        async def verify(text, sources):
            if text == "failing claim":
                return await instance.verify(text, sources)
            return await fake.verify(text, sources)

        monkeypatch.setitem(main.state, "llm", NS(extract=fake.extract, verify=verify))
    monkeypatch.setattr(main.settings.pipeline, "expose_detail", expose)
    try:
        response = client.post(path, json={"text": "offline input"})
        assert response.status_code == (502 if stage == "extract" and path == "/verify" else 200)
        assert SENSITIVE not in response.text
        assert "broken-json" not in response.text
        assert "ValidationError" not in response.text
        assert "JSONDecodeError" not in response.text
        assert "offline-placeholder" not in response.text
        if path.endswith("stream"):
            data = events(response)
            assert validate_stream([(e["type"], e) for e in data]) == []
            if stage == "extract":
                assert [e["type"] for e in data] == ["started", "stage", "error"]
                assert data[-1]["error"] == "EXTRACTION_FAILED"
                assert "detail" not in data[-1]
            else:
                assert data[-1]["type"] == "done" and data[-1]["partial"] is True
                results = [e["result"] for e in data if e["type"] == "result"]
        elif stage == "extract":
            body = response.json()
            assert validate_error_body(body) == []
            assert body["error"] == "EXTRACTION_FAILED" and "detail" not in body
        else:
            body = response.json()
            assert validate_verify_response(body) == []
            assert body["partial"] is True
            results = body["results"]
        if stage == "verdict":
            by_id = {r["claim_id"]: r for r in results}
            assert by_id["c1"]["status"] == "ok"
            bad = by_id["c2"]
            assert bad["status"] == "error" and bad["error_code"] == "VERDICT_FAILED"
            assert bad["failed_stage"] == "verdict" and bad["detail"] is None
        assert len(calls) == 1
    finally:
        sdk.close()


@pytest.mark.parametrize("path", ["/verify", "/verify/stream"])
@pytest.mark.parametrize("expose", [False, True])
@pytest.mark.parametrize("outcome,code,status", [
    (429, "UPSTREAM_RATE_LIMITED", "error"),
    ("timeout", "UPSTREAM_TIMEOUT", "timeout"),
])
def test_verdict_sdk_errors_preserve_partial_results(client, fake, monkeypatch, path, expose,
                                                    outcome, code, status):
    instance, calls, sdk = mock_llm(monkeypatch, outcome)
    fake.set_claims(("successful claim", True), ("failing claim", True))

    async def verify(text, sources):
        if text == "failing claim":
            return await instance.verify(text, sources)
        return await fake.verify(text, sources)

    monkeypatch.setitem(main.state, "llm", NS(extract=fake.extract, verify=verify))
    monkeypatch.setattr(main.settings.pipeline, "expose_detail", expose)
    try:
        response = client.post(path, json={"text": "offline input"})
        assert response.status_code == 200
        if path.endswith("stream"):
            data = events(response)
            assert validate_stream([(e["type"], e) for e in data]) == []
            assert data[-1]["type"] == "done" and data[-1]["partial"] is True
            assert not any(e["type"] == "error" for e in data)
            results = sorted([e["result"] for e in data if e["type"] == "result"],
                             key=lambda r: r["claim_id"])
        else:
            body = response.json()
            assert validate_verify_response(body) == []
            assert body["status"] == "ok" and body["partial"] is True
            results = body["results"]
        assert results[0]["status"] == "ok"
        assert results[1]["status"] == status
        assert results[1]["error_code"] == code
        assert results[1]["failed_stage"] == "verdict"
        assert results[1]["verdict"] is None
        assert "detail" not in results[1]
        assert SENSITIVE not in response.text
        assert "offline-placeholder" not in response.text
        assert len(calls) == 1
    finally:
        sdk.close()


def test_valid_verdict_with_missing_assessments_repairs_once_without_raw_details(monkeypatch):
    payload = broken_completion('verdict')
    payload['choices'][0]['message']['content'] = json.dumps({
        'claim_id': 'c', 'verdict': 'SUPPORTED', 'explanation': SENSITIVE,
        'used_sources': ['source_1'],
    })
    instance, calls, sdk = mock_llm(monkeypatch, payload)
    ae = llm._import_ai_engine()
    try:
        with pytest.raises(ae.AssessmentCoverageError) as caught:
            instance.engine.verify_claim('offline input', [ae.Source(id='source_1', text='Synthetic evidence')])
        assert len(calls) == 2
        assert SENSITIVE not in str(caught.value)
        assert caught.value.__suppress_context__
        assert instance.engine.client.max_retries == 0
    finally:
        sdk.close()
