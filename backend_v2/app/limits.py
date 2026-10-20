"""
limits.py
---------
One gate in front of the paid per-claim calls (search = Tavily, verdict = Groq), shared by
ALL requests of this process:

  * at most MAX_UPSTREAM_CONCURRENCY of these calls run at the same time
    (CLAIM_CONCURRENCY only limits claims inside one request; without this gate R requests
    could start R x CLAIM_CONCURRENCY paid calls at once)
  * identical calls that are in flight at the same moment are made once and the result is
    shared (two users checking the same claim together: one search, one verdict). The
    TTL cache in pipeline.py only helps AFTER the first call has finished.

Cancellation: a shared call is cancelled only when every request waiting for it has gone
(e.g. all their streams disconnected); one user leaving does not break the other's result.

The pipeline itself is unchanged: main.py passes wrapped `retrieve` / `verify` functions.
Single process only (like the cache): with several workers each has its own gate.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Hashable, Optional

from .pipeline import cache_key
from .resources import retain_task_resources
from .evidence import evidence_fingerprint, claim_frame_fingerprint, current_research, current_claim_frame

log = logging.getLogger("verify.limits")


class _Shared:
    __slots__ = ("task", "waiters")

    def __init__(self, task: asyncio.Task) -> None:
        self.task = task
        self.waiters = 0


class UpstreamGate:
    def __init__(self, max_concurrency: int) -> None:
        self.max_concurrency = max(1, int(max_concurrency))
        self._sem: Optional[asyncio.Semaphore] = None
        self._sem_loop: Optional[asyncio.AbstractEventLoop] = None
        self._sem_size = self.max_concurrency
        self._inflight: dict = {}
        # counters for /health and tests
        self.active = 0
        self.peak = 0
        self.shared_hits = 0

    def _semaphore(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        if self._sem is None or self._sem_loop is not loop or self._sem_size != self.max_concurrency:
            self._sem = asyncio.Semaphore(max(1, int(self.max_concurrency)))
            self._sem_loop = loop
            self._sem_size = self.max_concurrency
            self._inflight = {k: v for k, v in self._inflight.items() if v.task.get_loop() is loop}
        return self._sem

    async def _limited(self, factory: Callable[[], Awaitable[Any]]) -> Any:
        async with self._semaphore():
            self.active += 1
            self.peak = max(self.peak, self.active)
            try:
                return await factory()
            finally:
                self.active -= 1

    async def call(self, key: Hashable, factory: Callable[[], Awaitable[Any]]) -> Any:
        self._semaphore()  # binds to the running loop (and drops entries of an old loop)
        entry = self._inflight.get(key)
        if entry is None or entry.task.done():
            entry = _Shared(asyncio.ensure_future(self._limited(factory)))
            # The task inherits the creator's context; retain that ownership until
            # it ends, including queue waits and gaps between synchronous calls.
            retain_task_resources(entry.task)
            self._inflight[key] = entry

            def _forget(task: asyncio.Task, key=key, entry=entry) -> None:
                if self._inflight.get(key) is entry:
                    del self._inflight[key]

            entry.task.add_done_callback(_forget)
        else:
            self.shared_hits += 1
        entry.waiters += 1
        try:
            return await asyncio.shield(entry.task)
        finally:
            entry.waiters -= 1
            if entry.waiters == 0 and not entry.task.done():
                # nobody wants the answer any more: stop spending quota on it
                if self._inflight.get(key) is entry:
                    del self._inflight[key]
                entry.task.cancel()

    # ---- wrappers with the right keys for the two pipeline steps -----------------------

    def _research_key(self):
        frame = current_claim_frame.get()
        return id(current_research.get()) if isinstance(frame, dict) and frame.get("fallback_queries") else None

    def retrieve(self, fn: Callable[[str], Awaitable[list]]) -> Callable[[str], Awaitable[list]]:
        async def wrapped(claim_text: str) -> list:
            return await self.call(("retrieve", cache_key(claim_text), claim_frame_fingerprint(), self._research_key()), lambda: fn(claim_text))

        return wrapped

    def verify(self, fn: Callable[[str, list], Awaitable[Any]]) -> Callable[[str, list], Awaitable[Any]]:
        async def wrapped(claim_text: str, sources: list) -> Any:
            ids = evidence_fingerprint(sources)
            return await self.call(("verify", cache_key(claim_text), ids, claim_frame_fingerprint(), self._research_key()), lambda: fn(claim_text, sources))

        return wrapped

    def stats(self) -> dict:
        return {"max": self.max_concurrency, "active": self.active, "peak": self.peak,
                "shared_hits": self.shared_hits}
