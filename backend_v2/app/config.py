"""All configuration comes from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .pipeline import PipelineConfig


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    tavily_api_key: str
    model_name: str
    reasoning_effort: str      # "low" | "medium" | "high" | "" (off) - gpt-oss models only
    llm_timeout: float         # seconds per Groq HTTP call
    retriever: str             # "lite" (default) | "tavily" (snippets only) | "arda" (old heavy pipeline)
    tavily_depth: str          # "basic" | "advanced"
    max_sources: int
    cache_ttl: int             # seconds
    frontend_origin: str
    pipeline: PipelineConfig

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
            tavily_api_key=os.getenv("TAVILY_API_KEY", "").strip(),
            model_name=os.getenv("FACTCHECK_MODEL_NAME", "openai/gpt-oss-20b").strip(),
            reasoning_effort=os.getenv("LLM_REASONING_EFFORT", "low").strip().lower(),
            llm_timeout=_float("LLM_TIMEOUT", 20.0),
            retriever=os.getenv("RETRIEVER", "lite").strip().lower(),
            tavily_depth=os.getenv("TAVILY_DEPTH", "basic").strip().lower() or "basic",
            max_sources=_int("MAX_SOURCES", 5),
            cache_ttl=_int("CACHE_TTL_SECONDS", 6 * 3600),
            frontend_origin=os.getenv("FRONTEND_ORIGIN", "").strip(),
            pipeline=PipelineConfig(
                max_claims=_int("MAX_VERIFIABLE_CLAIMS", 8),
                claim_concurrency=_int("CLAIM_CONCURRENCY", 4),
                extract_timeout=_float("EXTRACT_TIMEOUT", 20.0),
                claim_timeout=_float("CLAIM_TIMEOUT", 30.0),
                total_timeout=_float("TOTAL_TIMEOUT", 45.0),
                expose_detail=_bool("EXPOSE_ERROR_DETAIL", True),
            ),
        )

    def missing(self) -> list:
        """Names of required env vars that are not set."""
        out = []
        if not self.groq_api_key:
            out.append("GROQ_API_KEY")
        if not self.tavily_api_key:  # every retriever searches through Tavily
            out.append("TAVILY_API_KEY")
        return out
