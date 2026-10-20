"""
pipeline.py
-----------
The orchestration core. Deliberately free of FastAPI / Groq / Tavily imports:
the three steps (extract, retrieve, verify) are injected as async callables,
which makes the whole flow testable with fakes (see tests/test_pipeline.py).

What it guarantees:
  * claims are processed CONCURRENTLY (bounded by a semaphore)
  * every claim has its own timeout; the whole request has a hard deadline
  * one claim failing / timing out never kills the others
  * a response ALWAYS comes back within `total_timeout` (possibly partial)
  * errors say which stage failed and why (no more mystery 500s)
  * per-stage timings are reported, so "what is slow?" has an answer
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import hashlib
from copy import deepcopy
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from .resources import ClaimLease, current_claim_lease
from .upstream_errors import InvalidModelResponse, UpstreamRateLimited, UpstreamTimeout
from .evidence import evidence_fingerprint, current_claim_frame, claim_frame_fingerprint, current_research, verifier_budget

log = logging.getLogger("verify.pipeline")

NO_EVIDENCE = "NOT ENOUGH EVIDENCE"


class PipelineError(Exception):
    """A failure of the whole request (not just one claim)."""

    def __init__(self, code: str, message: str, detail: Optional[str] = None, http_status: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail
        self.http_status = http_status


@dataclass
class PipelineConfig:
    max_claims: int = 8            # verifiable claims beyond this are skipped
    claim_concurrency: int = 4     # claims processed at the same time
    extract_timeout: float = 20.0  # seconds for the claim-extraction LLM call
    claim_timeout: float = 30.0    # seconds per claim (retrieval + verdict)
    total_timeout: float = 45.0    # hard deadline for the whole request
    expose_detail: bool = False    # include "Type: message" of errors; opt in only for private debugging


class TTLCache:
    """Tiny in-memory LRU+TTL cache (single process, event-loop only)."""

    def __init__(self, ttl: float = 6 * 3600, max_items: int = 500):
        self.ttl = ttl
        self.max_items = max_items
        self._d: "OrderedDict[str, tuple[float, dict]]" = OrderedDict()

    def get(self, key: str) -> Optional[dict]:
        item = self._d.get(key)
        if item is None:
            return None
        expires, value = item
        if expires < time.monotonic():
            self._d.pop(key, None)
            return None
        self._d.move_to_end(key)
        return deepcopy(value)

    def set(self, key: str, value: dict) -> None:
        self._d[key] = (time.monotonic() + self.ttl, deepcopy(value))
        self._d.move_to_end(key)
        while len(self._d) > self.max_items:
            self._d.popitem(last=False)

    def __len__(self) -> int:
        return len(self._d)


Extract = Callable[[str], Awaitable[Any]]                 # -> obj with .claims
Retrieve = Callable[[str], Awaitable[list]]               # -> list[source dict]
Verify = Callable[[str, list], Awaitable[Any]]            # -> obj with verdict/explanation/used_sources
Emit = Callable[[dict], Awaitable[None]]


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def cache_key(text: str) -> str:
    # Turkish-aware lowercase: plain .lower() turns "İ" into "i" + a combining
    # dot, so "İddia" and "iddia" would get different keys.
    folded = text.strip().replace("İ", "i").replace("I", "ı").lower()
    return re.sub(r"\s+", " ", folded)


def _detail(exc: BaseException, cfg: PipelineConfig) -> Optional[str]:
    if isinstance(exc, InvalidModelResponse):
        return None
    if not cfg.expose_detail:
        return None
    msg = str(exc) or "(no message)"
    return f"{type(exc).__name__}: {msg}"[:300]


def _base(claim: Any, **overrides: Any) -> dict:
    result = {
        "claim_id": claim.id,
        "claim": claim.text,
        "is_verifiable": bool(claim.is_verifiable),
        "verdict": None,
        "explanation": None,
        "used_sources": [],
        "sources": [],
        "status": "ok",
    }
    result.update(overrides)
    return result


async def _process_claim(
    claim: Any, *, retrieve: Retrieve, verify: Verify, cfg: PipelineConfig, cache: Optional[TTLCache]
) -> dict:
    frame = getattr(claim, "claim_frame", None)
    if hasattr(frame, "model_dump"):
        frame = frame.model_dump()
    frame_token = current_claim_frame.set(frame if isinstance(frame, dict) else None)
    research = {}
    research_token = current_research.set(research)
    budget_token = verifier_budget.set({"repairs": 0, "attempts": 0})
    stage = {"name": "retrieval"}
    timings: dict = {}

    def can_research():
        return research.get("round") == 1 and bool(research.get("fallbacks")) and not research.get("stopped")

    def grounded(v, sources):
        if getattr(v, "source_assessments", None) is None:
            return v
        from .llm import _import_ai_engine
        ae = _import_ai_engine()
        return ae.normalize_assessments(ae.VerdictResult(
            claim_id=getattr(v, "claim_id", claim.id), verdict=v.verdict,
            explanation=v.explanation, used_sources=v.used_sources,
            source_assessments=v.source_assessments), [s["id"] for s in sources], frame)

    async def body() -> dict:
        t = time.perf_counter()
        sources = await retrieve(claim.text)
        if research.get("quality_weak") and can_research():
            research["trigger"] = "passage_quality"
            sources = await retrieve(claim.text)
        timings["retrieval_ms"] = _ms(t)
        outcome = getattr(sources, "outcome", None)
        outcome_fields = {"retrieval_outcome": outcome} if outcome else {}
        key = hashlib.sha256((cache_key(claim.text) + ":" + claim_frame_fingerprint() + ":" + evidence_fingerprint(sources)).encode()).hexdigest()
        if cache is not None and sources and not research.get("stopped"):
            hit = cache.get(key)
            if hit is not None:
                return _base(claim, **hit, **outcome_fields, cached=True, timings_ms=dict(timings))

        if not sources:
            if research.get("stopped"):
                raise RuntimeError("Research interrupted without evidence")
            return _base(
                claim,
                verdict=NO_EVIDENCE,
                explanation="Bu iddia için kaynak bulunamadı.",
                no_sources=True,
                **outcome_fields,
                timings_ms=dict(timings),
            )

        stage["name"] = "verdict"
        t = time.perf_counter()
        v = await verify(claim.text, sources)
        v = grounded(v, sources)
        if getattr(v, "source_assessments", None) is not None and not v.used_sources and can_research():
            stage["name"] = "retrieval"
            research["trigger"] = "no_strong_evidence"
            sources = await retrieve(claim.text)
            outcome = getattr(sources, "outcome", None)
            outcome_fields = {"retrieval_outcome": outcome} if outcome else {}
            key = hashlib.sha256((cache_key(claim.text) + ":" + claim_frame_fingerprint() + ":" + evidence_fingerprint(sources)).encode()).hexdigest()
            stage["name"] = "verdict"
            v = grounded(await verify(claim.text, sources), sources)
        if research.get("stopped") and not v.used_sources:
            stage["name"] = "retrieval"
            raise RuntimeError("Research interrupted before useful evidence was established")
        timings["verify_ms"] = _ms(t)

        ids = {s["id"] for s in sources}
        used = [s for s in (v.used_sources or []) if s in ids]  # drop hallucinated ids
        assessments = getattr(v, "source_assessments", None)
        if assessments is not None:
            # Revalidate at the adapter boundary too; injected/alternative verifiers cannot
            # bypass grounding merely by returning a structured-looking response.
            from .llm import _import_ai_engine
            ae = _import_ai_engine()
            v = ae.normalize_assessments(ae.VerdictResult(
                claim_id=getattr(v, "claim_id", claim.id), verdict=v.verdict,
                explanation=v.explanation, used_sources=v.used_sources,
                source_assessments=assessments), [s["id"] for s in sources], frame)
            used = v.used_sources
            by_id = {a.source_id: a for a in v.source_assessments}
            sources = [{**s, **({"relation": by_id[s["id"]].relation.lower(),
                                "strength": by_id[s["id"]].strength,
                                "assessment_reason": by_id[s["id"]].reason}
                               if s["id"] in by_id else {})} for s in sources]
        payload = {
            **({"source_assessments": [a.model_dump() for a in v.source_assessments],
                "compatibility_materiality": ae.compatibility_materiality(frame)}
               if assessments is not None else {}),
            "verdict": v.verdict,
            "explanation": v.explanation,
            "used_sources": used,
            "sources": sources,
        }
        if cache is not None:
            cache.set(key, payload)
        return _base(claim, **payload, **outcome_fields, timings_ms=dict(timings))

    try:
        return await asyncio.wait_for(body(), cfg.claim_timeout)
    except asyncio.TimeoutError:
        return _base(
            claim,
            status="timeout",
            error_code="CLAIM_TIMEOUT",
            failed_stage=stage["name"],
            explanation="Bu iddia zamanında incelenemedi.",
            timings_ms=dict(timings),
        )
    except (UpstreamRateLimited, UpstreamTimeout) as exc:
        return _base(
            claim,
            status="timeout" if isinstance(exc, UpstreamTimeout) else "error",
            error_code="UPSTREAM_TIMEOUT" if isinstance(exc, UpstreamTimeout) else "UPSTREAM_RATE_LIMITED",
            failed_stage=stage["name"],
            explanation=str(exc),
            timings_ms=dict(timings),
        )
    except Exception as exc:  # one claim failing must not kill the others
        log.exception("claim %s failed in stage %s", claim.id, stage["name"])
        return _base(
            claim,
            status="error",
            error_code="RETRIEVAL_FAILED" if stage["name"] == "retrieval" else "VERDICT_FAILED",
            failed_stage=stage["name"],
            explanation="Bu iddia incelenirken bir hata oluştu.",
            detail=_detail(exc, cfg),
            timings_ms=dict(timings),
        )
    finally:
        current_claim_frame.reset(frame_token)
        current_research.reset(research_token)
        verifier_budget.reset(budget_token)


async def run_pipeline(
    text: str,
    *,
    extract: Extract,
    retrieve: Retrieve,
    verify: Verify,
    cfg: Optional[PipelineConfig] = None,
    cache: Optional[TTLCache] = None,
    emit: Optional[Emit] = None,
) -> dict:
    cfg = cfg or PipelineConfig()
    t_start = time.perf_counter()

    async def _emit(event: dict) -> None:
        if emit is None:
            return
        try:
            await emit(event)
        except Exception:
            log.exception("emit callback failed")

    # ---- 1. claim extraction ------------------------------------------------
    t = time.perf_counter()
    try:
        extraction = await asyncio.wait_for(extract(text), cfg.extract_timeout)
    except (asyncio.TimeoutError, UpstreamTimeout):
        raise PipelineError(
            "EXTRACTION_TIMEOUT", "İddialar ayrıştırılırken zaman aşımı oluştu.", http_status=504
        )
    except UpstreamRateLimited as exc:
        raise PipelineError("UPSTREAM_RATE_LIMITED", str(exc), http_status=503) from None
    except Exception as exc:
        log.exception("claim extraction failed")
        raise PipelineError(
            "EXTRACTION_FAILED", "İddialar ayrıştırılamadı.", detail=_detail(exc, cfg)
        ) from exc
    extract_ms = _ms(t)

    claims = list(extraction.claims)
    slots: list[Optional[dict]] = [None] * len(claims)

    await _emit(
        {
            "type": "claims",
            "claims": [
                {"claim_id": c.id, "claim": c.text, "is_verifiable": bool(c.is_verifiable)}
                for c in claims
            ],
            "extract_ms": extract_ms,
        }
    )

    # ---- 2. decide what to run ---------------------------------------------
    to_run: list[tuple[int, Any]] = []
    verifiable_seen = 0
    for i, c in enumerate(claims):
        if not c.is_verifiable:
            slots[i] = _base(c)
        else:
            verifiable_seen += 1
            if verifiable_seen > cfg.max_claims:
                slots[i] = _base(
                    c,
                    status="skipped",
                    explanation="Metinde çok sayıda iddia olduğu için bu iddia incelenmedi.",
                )
            else:
                to_run.append((i, c))
        if slots[i] is not None:
            await _emit({"type": "result", "result": slots[i]})

    # ---- 3. run claims concurrently, under a hard deadline -----------------
    sem = asyncio.Semaphore(max(1, cfg.claim_concurrency))

    async def run_one(i: int, c: Any) -> None:
        await sem.acquire()
        lease = ClaimLease(sem, asyncio.get_running_loop())
        token = current_claim_lease.set(lease)
        try:
            res = await _process_claim(c, retrieve=retrieve, verify=verify, cfg=cfg, cache=cache)
        finally:
            lease.finished = True
            lease.release_if_done()
            current_claim_lease.reset(token)
        slots[i] = res
        await _emit({"type": "result", "result": res})

    tasks = {asyncio.create_task(run_one(i, c)): (i, c) for i, c in to_run}
    if tasks:
        remaining = max(0.1, cfg.total_timeout - (time.perf_counter() - t_start))
        try:
            done, pending = await asyncio.wait(tasks.keys(), timeout=remaining)
        except asyncio.CancelledError:
            # The caller gave up (e.g. the SSE client disconnected). asyncio.wait does not
            # cancel its tasks, so without this the claims (and claims still waiting on the
            # semaphore) would keep running and spending Groq/Tavily quota.
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        for task in list(done) + list(pending):
            i, c = tasks[task]
            if slots[i] is not None:
                continue
            if task in pending:
                res = _base(
                    c,
                    status="timeout",
                    error_code="DEADLINE_EXCEEDED",
                    explanation="Bu iddia süre sınırı içinde incelenemedi.",
                )
            else:
                res = _base(
                    c,
                    status="error",
                    error_code="INTERNAL_ERROR",
                    explanation="Bu iddia incelenirken bir hata oluştu.",
                    detail=_detail(task.exception(), cfg) if task.exception() else None,
                )
            slots[i] = res
            await _emit({"type": "result", "result": res})

    results = [s for s in slots if s is not None]
    total_ms = _ms(t_start)
    partial = any(r["status"] in ("timeout", "error", "skipped") or
                  r.get("retrieval_outcome", {}).get("partial", False) for r in results)
    log.info(
        "pipeline done: claims=%d ran=%d extract=%dms total=%dms partial=%s",
        len(claims), len(to_run), extract_ms, total_ms, partial,
    )
    return {
        "status": "ok",
        "results": results,
        "partial": partial,
        "timings": {"extract_ms": extract_ms, "total_ms": total_ms},
    }
