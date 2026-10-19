"""
contract.py - the JSON contract the frontend (efeeyildiz91/verify-test, lib/api/adapter.ts,
docs/API_CONTRACT.md) depends on, written as plain checks.

Used by the offline tests AND by check_all.py's live checks, so a deployed server
is held to exactly the same rules as the fakes.

Every validate_* function returns a list of human-readable problems ([] = OK).
"""

from __future__ import annotations

import json
import re
from typing import Iterable, Optional

VERDICTS = {"SUPPORTED", "REFUTED", "NOT ENOUGH EVIDENCE", "CONFLICTING"}
CLAIM_STATUSES = {"ok", "error", "timeout", "skipped"}

# Request-level API codes; clients may use HTTP status fallback for newer codes.
KNOWN_ERROR_CODES = {
    "EMPTY_TEXT", "VALIDATION_ERROR", "TEXT_TOO_LONG", "BUSY", "RATE_LIMITED",
    "DAILY_QUOTA_EXCEEDED", "UPSTREAM_UNAVAILABLE", "TIMEOUT", "CONFIG_ERROR",
    "EXTRACTION_TIMEOUT", "EXTRACTION_FAILED", "VERIFY_FAILED", "UPSTREAM_RATE_LIMITED",
}
# per-claim codes (results[i].error_code when status != "ok")
CLAIM_ERROR_CODES = {"CLAIM_TIMEOUT", "DEADLINE_EXCEEDED", "RETRIEVAL_FAILED", "VERDICT_FAILED", "INTERNAL_ERROR",
                     "UPSTREAM_RATE_LIMITED", "UPSTREAM_TIMEOUT"}

CLAIM_KEYS = {"claim_id", "claim", "is_verifiable", "verdict", "explanation", "used_sources", "sources", "status"}
SOURCE_KEYS = {"id", "title", "domain", "url", "published_date", "text"}

SOURCE_ID = re.compile(r"^source_\d+$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CITATION = re.compile(r"\[(source_\d+)\]")

# SSE
STREAM_EVENT_TYPES = {"started", "stage", "claims", "result", "done", "error"}


def validate_source(src: dict, where: str, *, strict_dates: bool = True) -> list:
    p = []
    if not isinstance(src, dict):
        return [f"{where}: source is not an object"]
    missing = SOURCE_KEYS - set(src)
    if missing:
        p.append(f"{where}: source missing {sorted(missing)}")
    if not SOURCE_ID.match(str(src.get("id", ""))):
        p.append(f"{where}: source id {src.get('id')!r} is not source_N")
    url = src.get("url")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        p.append(f"{where}: source url {url!r} is not http(s)")
    if strict_dates:
        d = src.get("published_date")
        if d is not None and not (isinstance(d, str) and ISO_DATE.match(d)):
            p.append(f"{where}: published_date {d!r} is not YYYY-MM-DD or null")
    return p


def validate_claim(r: dict, where: str, *, strict_dates: bool = True) -> list:
    p = []
    if not isinstance(r, dict):
        return [f"{where}: result is not an object"]
    missing = CLAIM_KEYS - set(r)
    if missing:
        p.append(f"{where}: missing {sorted(missing)}")
    st = r.get("status")
    if st not in CLAIM_STATUSES:
        p.append(f"{where}: status {st!r} not in {sorted(CLAIM_STATUSES)}")
    if not isinstance(r.get("is_verifiable"), bool):
        p.append(f"{where}: is_verifiable is not a bool")
    v = r.get("verdict")
    if st == "ok" and r.get("is_verifiable"):
        if v not in VERDICTS:
            p.append(f"{where}: verdict {v!r} not in {sorted(VERDICTS)}")
    elif v is not None:
        # a claim that was not judged must never look like a real verdict
        p.append(f"{where}: verdict must be null when status={st!r} / is_verifiable={r.get('is_verifiable')}")
    if st in ("error", "timeout") and r.get("error_code") not in CLAIM_ERROR_CODES:
        p.append(f"{where}: error_code {r.get('error_code')!r} not in {sorted(CLAIM_ERROR_CODES)}")

    sources = r.get("sources")
    if not isinstance(sources, list):
        p.append(f"{where}: sources is not a list")
        sources = []
    for j, s in enumerate(sources):
        p += validate_source(s, f"{where}.sources[{j}]", strict_dates=strict_dates)
    ids = {s.get("id") for s in sources if isinstance(s, dict)}
    used = r.get("used_sources")
    if not isinstance(used, list):
        p.append(f"{where}: used_sources is not a list")
    else:
        extra = [u for u in used if u not in ids]
        if extra:
            p.append(f"{where}: used_sources {extra} are not in sources")
    return p


def validate_verify_response(body, *, strict_dates: bool = True) -> list:
    if not isinstance(body, dict):
        return ["body is not a JSON object"]
    p = []
    if body.get("status") != "ok":
        p.append(f"status is {body.get('status')!r}, expected 'ok'")
    results = body.get("results")
    if not isinstance(results, list):
        return p + ["results is not a list"]
    for i, r in enumerate(results):
        p += validate_claim(r, f"results[{i}]", strict_dates=strict_dates)
    ids = [r.get("claim_id") for r in results if isinstance(r, dict)]
    if len(ids) != len(set(ids)):
        p.append("claim_id values are not unique")
    if not isinstance(body.get("partial"), bool):
        p.append("partial is not a bool")
    elif body["partial"] != any(isinstance(r, dict) and r.get("status") != "ok" for r in results):
        p.append("partial does not match the claim statuses")
    t = body.get("timings")
    if not isinstance(t, dict) or not all(isinstance(t.get(k), int) for k in ("extract_ms", "total_ms")):
        p.append("timings must contain integer extract_ms and total_ms")
    return p


def validate_error_body(body, *, status_code: Optional[int] = None) -> list:
    if not isinstance(body, dict):
        return ["error body is not a JSON object"]
    p = []
    if body.get("status") != "error":
        p.append(f"status is {body.get('status')!r}, expected 'error'")
    if body.get("error") not in KNOWN_ERROR_CODES:
        p.append(f"error code {body.get('error')!r} is unknown to the frontend")
    if not isinstance(body.get("message"), str) or not body["message"]:
        p.append("message is missing")
    return p


def invalid_citations(r: dict) -> list:
    """[source_N] markers in the explanation that point at no source of this claim."""
    ids = {s.get("id") for s in r.get("sources") or []}
    return [c for c in CITATION.findall(r.get("explanation") or "") if c not in ids]


# ---- SSE -------------------------------------------------------------------

def parse_sse(raw: str) -> list:
    """'event: x\\ndata: {...}\\n\\n' blocks -> [(event_name, data_dict)]. Comment lines (': ...') are skipped."""
    events = []
    for block in raw.replace("\r\n", "\n").split("\n\n"):
        name, data = None, []
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
        if name is not None or data:
            events.append((name, json.loads("\n".join(data)) if data else None))
    return events


def validate_stream(events: Iterable, *, strict_dates: bool = True) -> list:
    events = list(events)
    p = []
    if not events:
        return ["no events"]
    for i, (name, data) in enumerate(events):
        if name not in STREAM_EVENT_TYPES:
            p.append(f"event[{i}] has unknown type {name!r}")
        if not isinstance(data, dict) or data.get("type") != name:
            p.append(f"event[{i}] data.type does not match the event name {name!r}")
    names = [n for n, _ in events]
    last = names[-1]
    if last not in ("done", "error"):
        p.append(f"stream must end with done or error, ended with {last!r}")
    if names.count("done") + names.count("error") != 1:
        p.append("exactly one done/error event expected")
    if last == "error":
        p += [f"error event: {x}" for x in validate_error_body({**events[-1][1], "status": "error"})]
        return p

    if "claims" not in names:
        return p + ["no claims event"]
    if any(n == "result" for n in names[: names.index("claims")]):
        p.append("a result arrived before the claims list")
    claims = events[names.index("claims")][1].get("claims") or []
    results = [d["result"] for n, d in events if n == "result"]
    for i, r in enumerate(results):
        p += validate_claim(r, f"result#{i}", strict_dates=strict_dates)
    claim_ids = [c.get("claim_id") for c in claims]
    result_ids = [r.get("claim_id") for r in results]
    if sorted(claim_ids) != sorted(result_ids):
        p.append(f"result claim_ids {result_ids} do not match the claims list {claim_ids}")
    stages = [d for n, d in events if n == "stage"]
    verify_start = [s for s in stages if s.get("stage") == "verify" and s.get("status") == "started"]
    if verify_start and verify_start[0].get("total") != len(results):
        p.append(f"verify stage announced total={verify_start[0].get('total')} but {len(results)} results came")
    done = events[-1][1]
    if not isinstance(done.get("partial"), bool):
        p.append("done.partial is not a bool")
    elif done["partial"] != any(r.get("status") != "ok" for r in results):
        p.append("done.partial does not match the result statuses")
    return p
