# backend_v2

A from-scratch rewrite of `backend/`, built to be **fast, observable, and impossible to hang**.
The old `backend/` is untouched, so the two can be compared side by side.

## What is different

| Old backend | backend_v2 |
|---|---|
| Claims processed one after another | Claims run concurrently (`CLAIM_CONCURRENCY`) |
| Up to 5 searches + 12 page downloads + a Chromium launch per page, per claim | Arda's new `retrieval_demo_lite` (3 searches, 8 plain page downloads, no browser, no ML models), with the downloads run **in parallel** |
| torch + sentence-transformers + Chromium in the image (~2 GB+) | Only `fastapi`, `groq`, `tavily-python` |
| No time limit: a slow request just dies at the frontend's timeout | Hard deadline (`TOTAL_TIMEOUT`): always answers, with partial results if needed |
| Any error becomes the same generic 500 | Each claim reports its own `status`, `error_code`, `failed_stage`, and (optionally) `detail` |
| Missing API key crashes the server at startup | Server starts, `/health` and `/verify` say exactly which variable is missing |
| gpt-oss "thinks" at default effort | `reasoning_effort=low` (auto-disabled if Groq rejects it) |
| Same claim re-researched every time | In-memory cache (6 h), Turkish-aware key |
| No way to see what is slow | `timings` in every response + `/health/deep` |

`ai-engine/ai_engine.py` and `retrieval_demo_lite/search_retrieval_lite.py` are reused as-is (imported, never copied
or edited), so there is one copy of the prompts and one copy of the retrieval logic, and `git pull` never conflicts.

The lite module downloads its pages one after another; `LiteRetriever` (in `app/retrieval.py`) wraps two of its
internal functions so they run in parallel (4.1 s -> 0.5 s in a simulated test, same sources chosen). If Arda later
parallelises the module himself, that wrapper can simply be deleted.

## Run locally (Windows)

```powershell
cd C:\Users\Mert\Desktop\verify
python -m venv .venv
.venv\Scripts\activate
pip install -r backend_v2\requirements.txt
copy backend_v2\.env.example backend_v2\.env     # then fill in the two keys
cd backend_v2
uvicorn app.main:app --reload
```

Then open <http://localhost:8000/health/deep>. It makes one tiny real call to Groq and to Tavily and
tells you how long each took, or the exact error. **If something is wrong, start there.**

Tests (no network, no keys needed):

```powershell
pip install -r requirements-dev.txt
python -m pytest              # contract, stream, partial results, errors, logging, pipeline
python check_all.py --skip-live   # what CI runs (also works without pytest: then only the 2 script tests)
```

`tests/contract.py` is the frontend JSON contract written as checks; `check_all.py --url ...` applies the same
checks to a running server. Tests marked `known_gap` are `xfail(strict)`: they describe open items owned by a
teammate and turn CI red once the item is fixed, so the marker gets removed. CI: `.github/workflows/backend.yml`.

### Load, memory and performance

`tests/test_load.py` (marker `perf`, runs in CI with everything else, about 8 s) checks with fakes:
25 requests at once overlap and never mix answers; `CLAIM_CONCURRENCY` holds per request and
`MAX_UPSTREAM_CONCURRENCY` over all requests; identical claims in flight are searched once and one user
leaving does not cancel the other's shared call; a request stuck
on a hanging claim does not slow down the others and still answers within `TOTAL_TIMEOUT`; `/health` stays
under 250 ms while 30 verifications run; memory does not grow over 400 requests; the cache stays at
`max_items`; 20 disconnected streams leave no task behind; the backend's own overhead per request is small.

`loadtest.py` measures a real uvicorn process (latency percentiles, status / error codes, contract
problems, unique request ids, server RAM):

```bash
python loadtest.py --spawn-fake --requests 300 --concurrency 30        # offline, fake LLM/search
python loadtest.py --spawn-fake --requests 300 --concurrency 30 --stream
python loadtest.py --url https://<backend> --requests 6 --concurrency 3  # REAL: spends Groq/Tavily quota
```

Measured on 16 Oct 2026 (CI container, one uvicorn worker, fake search 0.3 s per claim, cache off,
every text has its own claims, 2 verifiable claims per request):

| Scenario | `MAX_UPSTREAM_CONCURRENCY` | p50 | p95 | Errors | Server RAM (before → peak) |
|---|---|---|---|---|---|
| `/verify`, 200 requests, 20 at once | 8 (default) | 1519 ms | 1536 ms | 0 | 51.8 → 53.0 MB |
| `/verify`, 300 requests, 30 at once | 8 (default) | 2123 ms | 4227 ms | 0 | 51.8 → 53.6 MB |
| `/verify`, 200 requests, 20 at once | 64 | 304 ms | 317 ms | 0 | 51.8 → 53.2 MB |
| `/verify`, 300 requests, 30 at once | 64 | 306 ms | 328 ms | 0 | 51.8 → 53.8 MB |

With the default cap at most 8 search/verdict calls run at once, so throughput is about
8 / (seconds per claim) and extra requests wait in line instead of all hitting Groq/Tavily
together (and their rate limits). The wait counts against `CLAIM_TIMEOUT` / `TOTAL_TIMEOUT`,
so under a flood claims come back as `timeout` (partial result) instead of piling up.
With a high cap the backend itself adds almost nothing (p95 ≈ the fake search time).
RAM stays around 50-60 MB (the Render free instance has 512 MB); `/health` answered in 3 ms
throughout. Earlier run without the cap: 1000 requests, 100 at once, p95 4.7 s, 0 errors,
peak 56 MB (single worker CPU limit). These numbers say nothing about Groq and Tavily
themselves: with real services each claim takes seconds and their rate limits decide what
`MAX_UPSTREAM_CONCURRENCY` should be.

## API

- `GET /health` – config and which keys are set (never the keys)
- `GET /health/deep` – live latency / error check of Groq and Tavily
- `POST /verify` `{"text": "..."}` – same shape as before. New fields: `partial`, `timings`, and per claim
  `status` (`ok` | `error` | `timeout` | `skipped`), `error_code`, `failed_stage`, `detail`, `cached`, `timings_ms`.
  A claim with `status != "ok"` has `verdict: null`, so the frontend must not show it as a real verdict.
- `POST /verify/stream` – Server-Sent Events, in this order:
  `started` (`request_id`) → `stage` extract started → `stage` extract finished (`ms`) → `claims` →
  `stage` verify started (`total` = number of `result` events to expect) → `result` × total →
  `stage` verify finished (`ms`) → `done` (`partial`, `timings`, `request_id`).
  If the whole request fails: `error` (`error`, `message`, `request_id`, and `detail` only when
  `EXPOSE_ERROR_DETAIL=1`) instead. `data.type` always equals the event name; clients must ignore unknown events.
  Blank text is answered with `400 EMPTY_TEXT` JSON before any LLM call. When the client disconnects the
  pipeline and its claim tasks are cancelled at once (threads already inside a Groq/Tavily call still finish).
  Full description: `app/streaming.py`. (Use `fetch` + a stream reader on the frontend; `EventSource` cannot POST.)
- Every response has an `X-Request-ID` header. A valid incoming one (8-64 chars `[A-Za-z0-9._-]`) is reused;
  every log line carries `rid=...`. Per request one access line, per claim one timing line
  (`retrieval_ms`, `verify_ms`, status, error code) and a summary. User text is never logged.

## Choosing the retriever (`RETRIEVER` in `.env`)

| Value | What it is | Speed | Needs |
|---|---|---|---|
| `lite` (default) | Arda's `retrieval_demo_lite` | medium | `requests`, `beautifulsoup4` |
| `tavily` | one Tavily search, uses its snippets only | fastest, thinnest evidence | nothing extra |
| `arda` | Arda's old heavy pipeline (embeddings + cross-encoder + browser) | slowest | torch, sentence-transformers, ... |

Run the same texts with different values and compare `timings` and the sources. For `lite`, `LITE_QUERY_COUNT=2`
is the easiest extra speed-up (see `.env.example`).

## Deploying

Make sure `retrieval_demo_lite/` is committed (the image copies it). Build from the **repo root**: `docker build -f backend_v2/Dockerfile -t verify-backend .`
On Render/Railway: Dockerfile path `backend_v2/Dockerfile`, build context = repository root, and set
`GROQ_API_KEY` and `TAVILY_API_KEY` in the dashboard. Set `EXPOSE_ERROR_DETAIL=0` once things are stable.

## Known limits

- The cache and rate-limiting are per process (fine for one instance; use Redis if you scale out).
- `MAX_UPSTREAM_CONCURRENCY` (default 8) caps search + verdict calls over all requests and identical
  in-flight claims share one call (`app/limits.py`). Claim extraction (one Groq call per request) is
  not capped by it; a per-IP / global request limit is still needed (Fatih's item).
- Python threads that are already waiting on Groq/Tavily when a request times out cannot be killed; their
  result is simply discarded.
- With `RETRIEVER=tavily`, Tavily snippets are shorter than full pages, so evidence is thinner (speed/depth trade-off).
- The lite module still runs its 3 Tavily searches one after another (about 1-2 s each).
