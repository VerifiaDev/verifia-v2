"""
Run the REAL backend app (routes, CORS, middleware, pipeline, SSE) on a real port, with the
fake LLM and fake search from conftest.py instead of Groq/Tavily. No keys, no quota.

Used by:
  * the frontend-backend integration test (e2e/, .github/workflows/integration.yml)
  * loadtest.py --spawn-fake (RAM and latency of a real uvicorn process)

    cd backend_v2
    python tests/fake_server.py                 # http://127.0.0.1:8799

Environment:
  PORT                 default 8799
  FAKE_DELAY           seconds per fake search call (default 0.3)
  CLAIM_CONCURRENCY    claims per request at the same time (default 4)
  TOTAL_TIMEOUT        request deadline in seconds (default 45)
  FAKE_CACHE           "0" turns the result cache off (default on, like production);
                       the fake claims are the same for every text, so with the cache on
                       only the first request does any work
  FAKE_UNIQUE_CLAIMS   "1" makes every text produce its own claims (default off). Needed for
                       load tests: identical in-flight claims are otherwise searched once
                       (app/limits.py), so only the first request would do any work

The claims come from conftest.FakeBackend; keywords in the claim text pick a behaviour
(BOZUK, KARARSIZ, ASILI, KAYNAKSIZ). Special input texts, for the integration test:
  text contains "HATA-AYRISTIRMA"  -> claim extraction fails (502 EXTRACTION_FAILED)
  text contains "KISMI"            -> third claim's search fails (partial result)
"""

from __future__ import annotations

import os
import sys
import zlib
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace as NS

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

# never let a real key from a local .env switch on the real services
os.environ["GROQ_API_KEY"] = ""
os.environ["TAVILY_API_KEY"] = ""

from conftest import FakeBackend  # noqa: E402

from app import main  # noqa: E402
from app.pipeline import TTLCache  # noqa: E402


class ScenarioBackend(FakeBackend):
    async def extract(self, text):
        self.calls["extract"] += 1
        if "HATA-AYRISTIRMA" in text:
            raise RuntimeError("fake extraction failure")
        claims = list(self.claims)
        if "KISMI" in text:
            claims[2] = NS(id="c3", text="BOZUK kaynaklı iddia.", is_verifiable=True)
        if os.getenv("FAKE_UNIQUE_CLAIMS") == "1":
            tag = f" [{zlib.crc32(text.encode()):08x}]"
            claims = [NS(id=c.id, text=c.text + tag, is_verifiable=c.is_verifiable) for c in claims]
        return NS(claims=claims)


fb = ScenarioBackend()
fb.retrieve_delay = float(os.getenv("FAKE_DELAY", "0.3"))


@asynccontextmanager
async def lifespan(app):
    main.state.update(
        llm=NS(extract=fb.extract, verify=fb.verify),
        retriever=fb.retrieve,
        cache=None if os.getenv("FAKE_CACHE", "1") == "0" else TTLCache(),
        init_error=None,
    )
    cfg = main.settings.pipeline
    cfg.claim_concurrency = int(os.getenv("CLAIM_CONCURRENCY", "4"))
    cfg.total_timeout = float(os.getenv("TOTAL_TIMEOUT", "45"))
    print(f"fake backend ready (search delay {fb.retrieve_delay}s)", flush=True)
    yield
    print(f"FAKE-STATS calls={fb.calls} retrieve_cancelled={fb.retrieve_cancelled}", flush=True)


main.app.router.lifespan_context = lifespan

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(main.app, host="127.0.0.1", port=int(os.getenv("PORT", "8799")), log_level="warning")
