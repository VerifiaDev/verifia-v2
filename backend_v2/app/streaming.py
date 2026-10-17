"""
streaming.py
------------
Server-Sent Events for POST /verify/stream.

Event order (each event is `event: <type>` + `data: <json>`; data.type == event name):

    started   {"type":"started","request_id":"..."}
    stage     {"type":"stage","stage":"extract","status":"started"}
    stage     {"type":"stage","stage":"extract","status":"finished","ms":812}
    claims    {"type":"claims","claims":[{claim_id, claim, is_verifiable}], "extract_ms":812}
    stage     {"type":"stage","stage":"verify","status":"started","total":3}
    result    {"type":"result","result":{...same shape as one item of /verify results...}}   x total
    stage     {"type":"stage","stage":"verify","status":"finished","ms":2310}
    done      {"type":"done","partial":false,"timings":{...},"request_id":"..."}

  or, if the whole request fails (e.g. claim extraction):
    error     {"type":"error","error":"EXTRACTION_FAILED","message":"...","request_id":"..."}
              (+ "detail" only when EXPOSE_ERROR_DETAIL is on)

`started`, `stage` and the `request_id` fields are additions; `claims`, `result`,
`done` and `error` keep their earlier shape. Clients must ignore unknown events.
`total` in the verify stage = number of `result` events that will follow.
A `: keep-alive` comment line is sent when nothing happened for KEEPALIVE seconds.

Client disconnect: the response watches the ASGI `receive` channel itself, so a
closed connection is noticed immediately (not only at the next failed write),
and the pipeline task is cancelled.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from starlette.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

from .pipeline import PipelineError

log = logging.getLogger("verify.stream")

KEEPALIVE_SECONDS = 15.0
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

Emit = Callable[[dict], Awaitable[None]]
RunFn = Callable[[Emit], Awaitable[dict]]


def format_sse(event: dict) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


class VerificationStream:
    """Runs the pipeline in a background task and turns its callbacks into SSE text."""

    def __init__(
        self,
        run: RunFn,
        *,
        request_id: str,
        expose_detail: bool,
        keepalive: float = KEEPALIVE_SECONDS,
    ) -> None:
        self._run = run
        self.request_id = request_id
        self.expose_detail = expose_detail
        self.keepalive = keepalive
        self._queue: "asyncio.Queue[Optional[dict]]" = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self._t0 = time.perf_counter()
        self.finished = False      # pipeline ended (done or error)
        self.cancelled = False     # stopped because the client went away
        self.results_sent = 0

    # -- producer ------------------------------------------------------------

    def _put(self, event: dict) -> None:
        self._queue.put_nowait(event)  # unbounded queue: never blocks, safe in finally/cancel

    def _error_event(self, code: str, message: str, detail: Optional[str]) -> dict:
        ev: dict[str, Any] = {"type": "error", "error": code, "message": message, "request_id": self.request_id}
        if self.expose_detail and detail:
            ev["detail"] = detail
        return ev

    async def _runner(self) -> None:
        verify_t0: list = []

        async def emit(event: dict) -> None:
            if event.get("type") == "claims":
                self._put({"type": "stage", "stage": "extract", "status": "finished",
                           "ms": event.get("extract_ms")})
                self._put(event)
                verify_t0.append(time.perf_counter())
                self._put({"type": "stage", "stage": "verify", "status": "started",
                           "total": len(event.get("claims") or [])})
            else:
                if event.get("type") == "result":
                    self.results_sent += 1
                self._put(event)

        self._put({"type": "started", "request_id": self.request_id})
        self._put({"type": "stage", "stage": "extract", "status": "started"})
        try:
            res = await self._run(emit)
            if verify_t0:
                self._put({"type": "stage", "stage": "verify", "status": "finished", "ms": _ms(verify_t0[0])})
            self._put({"type": "done", "partial": res.get("partial", False), "timings": res.get("timings", {}),
                       "request_id": self.request_id})
        except asyncio.CancelledError:
            raise
        except PipelineError as e:
            self._put(self._error_event(e.code, e.message, e.detail))
        except Exception as exc:
            log.exception("unexpected failure in /verify/stream")
            self._put(self._error_event("VERIFY_FAILED", "Doğrulama işlemi sırasında bir hata oluştu.",
                                        f"{type(exc).__name__}: {exc}"[:300]))
        finally:
            self.finished = True
            self._put(None)

    # -- consumer ------------------------------------------------------------

    async def events(self) -> AsyncIterator[str]:
        if self._task is None:
            self._task = asyncio.create_task(self._runner())
        while True:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=self.keepalive)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"  # stops proxies from closing an idle connection
                continue
            if event is None:
                return
            yield format_sse(event)

    async def aclose(self, *, disconnected: bool = False) -> None:
        """Stop the pipeline if it is still running. Safe to call more than once."""
        task = self._task
        if task is not None and not task.done():
            self.cancelled = True
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if self.cancelled:
            log.info("stream cancelled%s after %d ms, %d results sent",
                     " (client disconnected)" if disconnected else "", _ms(self._t0), self.results_sent)


class SSEResponse(StreamingResponse):
    """StreamingResponse that (1) notices a client disconnect right away and
    (2) always cancels the pipeline when the response ends for any reason."""

    def __init__(self, stream: VerificationStream) -> None:
        super().__init__(stream.events(), media_type="text/event-stream", headers=SSE_HEADERS)
        self.stream = stream

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def wait_disconnect() -> None:
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return

        sender = asyncio.create_task(self.stream_response(send))
        watcher = asyncio.create_task(wait_disconnect())
        disconnected = False
        try:
            done, _ = await asyncio.wait({sender, watcher}, return_when=asyncio.FIRST_COMPLETED)
            if sender in done:
                exc = sender.exception()
                if isinstance(exc, OSError):  # write failed: the client is gone
                    disconnected = True
                elif exc is not None:
                    raise exc
            else:
                disconnected = True
        finally:
            for t in (sender, watcher):
                t.cancel()
            await asyncio.gather(sender, watcher, return_exceptions=True)
            with contextlib.suppress(Exception):
                await self.body_iterator.aclose()  # type: ignore[attr-defined]
            await self.stream.aclose(disconnected=disconnected)
