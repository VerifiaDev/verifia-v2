"""
llm.py
------
Async adapter around Mert's `ai_engine.FactCheckEngine`.

ai_engine.py stays the single source of truth (no copy in backend_v2):
  * in Docker it is copied next to the app (see Dockerfile)
  * locally it is imported from ../ai-engine

Two things are added on top, both without editing ai_engine.py:
  1. `reasoning_effort="low"` for gpt-oss models. These are reasoning
     models; by default they "think" for several seconds before answering,
     which is the biggest single latency cost of each LLM call.
  2. A short HTTP timeout with no automatic retries, avoiding duplicate
     paid calls after quota errors or ambiguous timeouts.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from groq import APIError, APITimeoutError, RateLimitError

from .upstream_errors import InvalidModelResponse, UpstreamError, UpstreamRateLimited, UpstreamTimeout

def _import_ai_engine():
    try:
        import ai_engine

        return ai_engine
    except ImportError:
        repo = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(repo / "ai-engine"))
        import ai_engine

        return ai_engine


def make_engine(settings):
    ae = _import_ai_engine()

    class FastEngine(ae.FactCheckEngine):
        reasoning_effort = settings.reasoning_effort

        def _generate(self, system_prompt, user_prompt, schema_model, schema_name):
            kwargs = dict(
                model=self.model_name,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=ae._strict_response_format(schema_model, schema_name),
            )
            use_effort = bool(
                self.reasoning_effort
                and self.model_name.startswith("openai/gpt-oss")
            )
            if use_effort:
                kwargs["reasoning_effort"] = self.reasoning_effort

            try:
                completion = self.client.chat.completions.create(**kwargs)
            except RateLimitError:
                raise UpstreamRateLimited() from None
            except APITimeoutError:
                raise UpstreamTimeout() from None
            except APIError:
                raise UpstreamError() from None
            try:
                result = schema_model.model_validate(json.loads(completion.choices[0].message.content))
            except (ValueError, TypeError, AttributeError, IndexError):
                # ValidationError is a ValueError and may include raw input values.
                raise InvalidModelResponse() from None
            # The base engine's verdict check embeds the untrusted label in ValueError.
            if schema_name == "verdict_result" and result.verdict not in ae.VALID_VERDICTS:
                raise InvalidModelResponse()
            return result

    engine = FastEngine(api_key=settings.groq_api_key, model_name=settings.model_name)
    try:
        engine.client = engine.client.with_options(timeout=settings.llm_timeout, max_retries=0)
    except Exception:
        raise RuntimeError("LLM istemci seçenekleri uygulanamadı.") from None
    return engine


class LLM:
    """Async wrapper: the Groq SDK is synchronous, so calls run in threads."""

    def __init__(self, settings):
        self._ae = _import_ai_engine()
        self.engine = make_engine(settings)

    async def extract(self, text: str):
        return await asyncio.to_thread(self.engine.extract_claims, text)

    async def verify(self, claim_text: str, sources: list):
        srcs = [
            self._ae.Source(id=s["id"], url=s.get("url"), text=s["text"]) for s in sources
        ]
        return await asyncio.to_thread(self.engine.verify_claim, claim_text, srcs)
