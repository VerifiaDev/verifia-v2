"""
Verify backend v2.

Endpoints
  GET  /              liveness
  GET  /health        config + which keys are set (never the keys themselves)
  GET  /health/deep   makes one tiny real call to Groq and to the search
                      provider and reports latency / errors for each.
                      -> run this first when "something is wrong"
  POST /verify        same request/response shape as the old backend, plus
                      per-claim `status`, `timings`, and `partial`.
                      Always answers within TOTAL_TIMEOUT seconds.
  POST /verify/stream Server-Sent Events: claims arrive first, then each
                      verdict as soon as it is ready, then `done`
                      (event list: app/streaming.py).

Every response has an X-Request-ID header (app/observability.py).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

load_dotenv()

from .config import Settings  # noqa: E402
from .observability import (  # noqa: E402
    RequestContextMiddleware,
    current_request_id,
    log_pipeline_result,
    setup_logging,
)
from .resources import TrackingExecutor
from .security import Guard, SecurityMiddleware
from .safe_logging import install_safe_logging
from .limits import UpstreamGate  # noqa: E402
from .pipeline import PipelineError, TTLCache, run_pipeline  # noqa: E402
from .streaming import SSEResponse, VerificationStream  # noqa: E402

setup_logging(os.getenv("LOG_LEVEL", "INFO"))
install_safe_logging()
log = logging.getLogger("verify.api")

settings = Settings.from_env()
state: dict = {"llm": None, "retriever": None, "cache": None, "init_error": None}
# shared by all requests: global cap on paid calls + one call for identical in-flight claims
upstream = UpstreamGate(settings.upstream_concurrency)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.get_running_loop().set_default_executor(TrackingExecutor(max_workers=8))
    # A missing key must NOT crash the server: it should start and say what is wrong.
    missing = settings.missing()
    if missing:
        state["init_error"] = "Eksik ortam değişkenleri: " + ", ".join(missing)
        log.error("startup: %s", state["init_error"])
    else:
        try:
            from .llm import LLM
            from .retrieval import build_retriever

            state["llm"] = LLM(settings)
            state["retriever"] = build_retriever(settings)
            state["cache"] = TTLCache(ttl=settings.cache_ttl)
            log.info(
                "ready: model=%s retriever=%s reasoning=%s",
                settings.model_name, settings.retriever, settings.reasoning_effort or "default",
            )
        except Exception as exc:
            state["init_error"] = f"{type(exc).__name__}: {exc}"
            log.exception("startup failed")
    yield


app = FastAPI(title="Verify Backend", version="2.0.0", lifespan=lifespan)

guard = Guard()
app.add_middleware(SecurityMiddleware, guard=guard)

allowed_origins = [
    "https://verify-test-swart.vercel.app",
    "http://localhost:3000",
    "http://localhost:5173",
]
# FRONTEND_ORIGIN may list several origins separated by commas (e.g. production + preview domain).
for origin in (settings.frontend_origin or "").split(","):
    origin = origin.strip().rstrip("/")
    if origin and origin != "*" and origin not in allowed_origins:
        allowed_origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    # The frontend sends no cookies or auth headers; keep the browser surface minimal.
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Request-ID"],
    # Lets the frontend's JavaScript read the id (e.g. to show it with an error message).
    expose_headers=["X-Request-ID"],
)
# Added last = outermost: every response, including CORS preflight, gets X-Request-ID.
app.add_middleware(RequestContextMiddleware)


class VerifyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "error": "VALIDATION_ERROR",
            "message": "Gönderilen veri geçersiz.",
        },
    )


def _not_ready():
    return JSONResponse(
        status_code=503,
        content={
            "status": "error",
            "error": "CONFIG_ERROR",
            "message": "Sunucu yapılandırması eksik.",
            "detail": state["init_error"] if settings.pipeline.expose_detail else None,
        },
    )


def _error_response(e: PipelineError):
    content = {"status": "error", "error": e.code, "message": e.message}
    if e.detail and settings.pipeline.expose_detail:
        content["detail"] = e.detail
    return JSONResponse(status_code=e.http_status, content=content)


async def _run(text: str, emit=None):
    res = await run_pipeline(
        text,
        extract=state["llm"].extract,
        retrieve=upstream.retrieve(state["retriever"]),
        verify=upstream.verify(state["llm"].verify),
        cfg=settings.pipeline,
        cache=state["cache"],
        emit=emit,
    )
    log_pipeline_result(res)
    return res


@app.get("/")
def root():
    return {"status": "ok", "message": "Backend çalışıyor!"}


@app.get("/health")
def health():
    return {
        "status": "ok" if state["init_error"] is None else "degraded",
        "service": "verify-backend",
        "version": "2.0.0",
        "init_error": state["init_error"] if settings.pipeline.expose_detail else None,
        "config": {
            "model": settings.model_name,
            "reasoning_effort": settings.reasoning_effort or None,
            "retriever": settings.retriever,
            "tavily_depth": settings.tavily_depth,
            "groq_key_set": bool(settings.groq_api_key),
            "tavily_key_set": bool(settings.tavily_api_key),
            "max_claims": settings.pipeline.max_claims,
            "claim_concurrency": settings.pipeline.claim_concurrency,
            "upstream_concurrency": upstream.max_concurrency,
            "total_timeout_s": settings.pipeline.total_timeout,
            "cache_entries": len(state["cache"]) if state["cache"] is not None else 0,
        },
    }


@app.get("/health/deep")
async def health_deep():
    # This diagnostic endpoint spends provider credits; it only exists while debugging is enabled.
    if not settings.pipeline.expose_detail:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    if state["init_error"]:
        return _not_ready()

    async def timed(coro):
        t = time.perf_counter()
        try:
            await coro
            return {"ok": True, "ms": int((time.perf_counter() - t) * 1000)}
        except Exception as exc:
            return {
                "ok": False,
                "ms": int((time.perf_counter() - t) * 1000),
                "error": f"{type(exc).__name__}: {exc}"[:300],
            }

    claim = "Ankara Türkiye'nin başkentidir."
    llm_check, search_check = await asyncio.gather(
        timed(state["llm"].extract(claim)),
        timed(state["retriever"](claim)),
    )
    return {"llm": llm_check, "search": search_check}


@app.post("/verify")
async def verify(request: VerifyRequest):
    if state["init_error"]:
        return _not_ready()

    text = request.text.strip()
    if not text:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error": "EMPTY_TEXT",
                "message": "Doğrulanacak metin boş olamaz.",
            },
        )

    try:
        return await _run(text)
    except PipelineError as e:
        return _error_response(e)
    except Exception as exc:
        log.exception("unexpected failure in /verify")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": "VERIFY_FAILED",
                "message": "Doğrulama işlemi sırasında bir hata oluştu.",
                "detail": f"{type(exc).__name__}: {exc}"[:300] if settings.pipeline.expose_detail else None,
            },
        )


@app.post("/verify/stream")
async def verify_stream(request: VerifyRequest):
    if state["init_error"]:
        return _not_ready()

    text = request.text.strip()
    if not text:  # same answer as /verify; do not spend an LLM call on whitespace
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error": "EMPTY_TEXT",
                "message": "Doğrulanacak metin boş olamaz.",
            },
        )

    stream = VerificationStream(
        lambda emit: _run(text, emit=emit),
        request_id=current_request_id(),
        expose_detail=settings.pipeline.expose_detail,
    )
    return SSEResponse(stream)
