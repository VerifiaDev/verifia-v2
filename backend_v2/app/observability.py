"""
observability.py
----------------
Request ids, request logs and per-stage timing logs.

* Every response carries an `X-Request-ID` header. A valid incoming
  `X-Request-ID` (8-64 chars of [A-Za-z0-9._-]) is reused, so a request can be
  followed from the frontend through the logs; anything else is replaced.
* Every log line has `rid=<request id>` (or `rid=-` outside a request).
* One line per request (method, path, status, duration) and, per /verify run,
  one line per claim (status, retrieval_ms, verify_ms, cached) plus a summary.
* User text, claim text and API keys are never logged here.
"""

from __future__ import annotations

import contextvars
import logging
import re
import time
import uuid
from typing import Optional

from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
_HEADER_BYTES = REQUEST_ID_HEADER.lower().encode("latin-1")
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

log = logging.getLogger("verify.request")
perf_log = logging.getLogger("verify.perf")

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s rid=%(request_id)s: %(message)s"


def current_request_id() -> str:
    return request_id_var.get()


def new_request_id() -> str:
    return uuid.uuid4().hex


def accept_request_id(raw: Optional[str]) -> str:
    """Reuse a well-formed incoming id, otherwise make a new one (never trust free text in logs)."""
    if raw and _VALID_ID.match(raw):
        return raw
    return new_request_id()


_factory_installed = False


def setup_logging(level: str = "INFO") -> None:
    """basicConfig + a record factory that stamps every record with the current request id."""
    global _factory_installed
    if not _factory_installed:
        old_factory = logging.getLogRecordFactory()

        def factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            if not hasattr(record, "request_id"):
                record.request_id = request_id_var.get()
            return record

        logging.setLogRecordFactory(factory)
        _factory_installed = True
    logging.basicConfig(level=level, format=LOG_FORMAT)


class RequestContextMiddleware:
    """Pure ASGI middleware (safe for streaming responses, unlike BaseHTTPMiddleware)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = None
        for name, value in scope.get("headers") or []:
            if name == _HEADER_BYTES:
                incoming = value.decode("latin-1")
                break
        rid = accept_request_id(incoming)
        token = request_id_var.set(rid)
        scope.setdefault("state", {})["request_id"] = rid

        t0 = time.perf_counter()
        status = {"code": 0}

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != _HEADER_BYTES]
                headers.append((_HEADER_BYTES, rid.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            ms = int((time.perf_counter() - t0) * 1000)
            log.info("%s %s -> %s in %d ms", scope.get("method"), scope.get("path"), status["code"] or "aborted", ms)
            request_id_var.reset(token)


def log_pipeline_result(res: dict) -> None:
    """Per-claim stage timings + one summary line. No claim text."""
    results = res.get("results") or []
    retrieval, verify, counts = [], [], {}
    for r in results:
        st = r.get("status", "?")
        counts[st] = counts.get(st, 0) + 1
        tm = r.get("timings_ms") or {}
        if "retrieval_ms" in tm:
            retrieval.append(tm["retrieval_ms"])
        if "verify_ms" in tm:
            verify.append(tm["verify_ms"])
        if r.get("is_verifiable"):
            perf_log.info(
                "claim %s status=%s retrieval_ms=%s verify_ms=%s sources=%d cached=%s%s",
                r.get("claim_id"), st, tm.get("retrieval_ms", "-"), tm.get("verify_ms", "-"),
                len(r.get("sources") or []), bool(r.get("cached")),
                f" error={r.get('error_code')}@{r.get('failed_stage', '-')}" if r.get("error_code") else "",
            )

    def agg(xs: list) -> str:
        return f"avg={sum(xs) // len(xs)} max={max(xs)}" if xs else "-"

    t = res.get("timings") or {}
    perf_log.info(
        "verify summary claims=%d statuses=%s partial=%s extract_ms=%s total_ms=%s retrieval[%s] verify[%s]",
        len(results), counts, res.get("partial"), t.get("extract_ms"), t.get("total_ms"), agg(retrieval), agg(verify),
    )
