#!/usr/bin/env python3
"""
check_all.py - ONE command that tests everything in backend_v2.

    python check_all.py                      offline tests + start the server + live checks
    python check_all.py --skip-live          offline tests only (no keys, no internet needed; what CI runs)
    python check_all.py --url http://localhost:8000     test a server that is ALREADY running
    python check_all.py --url https://your-app.onrender.com   ...or a deployed one
    python check_all.py --stress             also send a 10-claim text (uses more API credits)

What it does
  [0] environment : packages installed? API keys present and plausible?
  [1] offline     : the whole tests/ folder with pytest (fakes, no network); without pytest,
                    tests/test_pipeline.py + tests/test_lite_adapter.py as plain scripts
  [2] server      : starts uvicorn for you (unless --url is given)
  [3] live        : /health, /health/deep, /verify (verdicts, sources, timings), cache,
                    error handling, CORS, X-Request-ID, /verify/stream, and the frontend
                    JSON contract (tests/contract.py) on every live response
  [4] summary     : PASS / WARN / FAIL table + a report file (check_all_report.txt)

PASS = works.  WARN = works but worth a look (e.g. the AI judged a claim differently).
FAIL = broken. The exit code is 1 if anything FAILed.
API keys are never printed or written to the report.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:  # Turkish characters in a Windows console
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tests"))
import contract  # noqa: E402  (tests/contract.py: the frontend JSON contract, no dependencies)

LINES: list = []
RESULTS: list = []  # (status, name, detail)
VALID_VERDICTS = {"SUPPORTED", "REFUTED", "NOT ENOUGH EVIDENCE", "CONFLICTING"}


def out(msg: str = "") -> None:
    print(msg, flush=True)
    LINES.append(msg)


def record(status: str, name: str, detail: str = "") -> None:
    RESULTS.append((status, name, detail))
    out(f"  {status:<5} {name}" + (f"  -  {detail}" if detail else ""))


# --------------------------------------------------------------------------
# [0] environment
# --------------------------------------------------------------------------

REQUIRED = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "pydantic": "pydantic",
    "dotenv": "python-dotenv",
    "groq": "groq",
    "tavily": "tavily-python",
    "requests": "requests",
    "bs4": "beautifulsoup4",
}


def read_env_file() -> dict:
    vals: dict = {}
    p = HERE / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k.strip()] = v.split(" #")[0].strip().strip('"').strip("'")
    return vals


def step_environment(check_keys: bool = True) -> bool:
    out("\n[0] Environment")
    ok = True
    missing = [pip for mod, pip in REQUIRED.items() if importlib.util.find_spec(mod) is None]
    if missing:
        ok = False
        record("FAIL", "packages installed", "missing: " + ", ".join(missing)
               + "  ->  python -m pip install -r requirements.txt")
    else:
        record("PASS", "packages installed")

    if not (HERE.parent / "retrieval_demo_lite" / "search_retrieval_lite.py").exists():
        ok = False
        record("FAIL", "retrieval_demo_lite folder", "must sit next to backend_v2 (Arda's module)")
    else:
        record("PASS", "retrieval_demo_lite folder found")
    if not (HERE.parent / "ai-engine" / "ai_engine.py").exists():
        ok = False
        record("FAIL", "ai-engine folder", "must sit next to backend_v2 (your ai_engine.py)")
    else:
        record("PASS", "ai-engine folder found")

    if not check_keys:
        record("SKIP", "API keys", "not needed for --skip-live or --url")
        return ok
    env_file = read_env_file()
    for key, prefix in (("GROQ_API_KEY", "gsk_"), ("TAVILY_API_KEY", "tvly-")):
        val = os.environ.get(key) or env_file.get(key) or ""
        if not val:
            ok = False
            record("FAIL", f"{key} is set", "empty or missing in backend_v2\\.env")
        elif not val.startswith(prefix):
            record("WARN", f"{key} is set", f"does not start with '{prefix}' - was it copied completely?")
        else:
            record("PASS", f"{key} is set")
    return ok


# --------------------------------------------------------------------------
# [1] offline tests
# --------------------------------------------------------------------------

def step_unit_tests() -> None:
    out("\n[1] Offline tests (fake search + fake AI, no network)")
    if importlib.util.find_spec("pytest") is not None:
        t = time.perf_counter()
        try:
            p = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=HERE, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=600, env={**os.environ, "PYTHONUTF8": "1"},
            )
        except subprocess.TimeoutExpired:
            record("FAIL", "pytest tests/", "timed out after 600 s")
            return
        lines = p.stdout.strip().splitlines()
        last = lines[-1].strip("= ") if lines else ""
        took = f"{time.perf_counter() - t:.1f}s"
        if p.returncode == 0:
            record("PASS", "pytest tests/", f"{last} ({took})")
            gaps = [l.split(" - ", 1)[-1] for l in lines if l.startswith("XFAIL")]
            for g in gaps:
                record("WARN", "known gap (xfail)", g)
        else:
            fails = [l for l in lines if l.startswith(("FAILED", "ERROR"))]
            record("FAIL", "pytest tests/", "; ".join(fails[:3]) or last or (p.stderr.strip().splitlines() or [""])[-1])
            for l in lines[-40:]:
                out("     " + l)
        return
    out("  (pytest not installed: running the two script tests only. pip install -r requirements-dev.txt)")
    for rel in ("tests/test_pipeline.py", "tests/test_lite_adapter.py"):
        t = time.perf_counter()
        try:
            p = subprocess.run(
                [sys.executable, str(HERE / rel)], cwd=HERE, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=300,
                env={**os.environ, "PYTHONUTF8": "1"},
            )
        except subprocess.TimeoutExpired:
            record("FAIL", rel, "timed out after 300 s")
            continue
        summary = [l for l in p.stdout.splitlines() if "passed" in l]
        took = f"{time.perf_counter() - t:.1f}s"
        if p.returncode == 0:
            record("PASS", rel, f"{summary[-1].strip() if summary else 'ok'} ({took})")
        else:
            fails = [l for l in p.stdout.splitlines() if l.startswith("FAIL")]
            tail = (p.stderr.strip().splitlines() or [""])[-1]
            record("FAIL", rel, "; ".join(fails[:3]) or tail or "see output")


# --------------------------------------------------------------------------
# [2] server
# --------------------------------------------------------------------------

def http(method, path, base, body=None, headers=None, timeout=120):
    data = None
    h = dict(headers or {})
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        h.setdefault("Content-Type", "application/json; charset=utf-8")
    req = urllib.request.Request(base + path, data=data, method=method, headers=h)
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw, status, hdrs = r.read(), r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        raw, status, hdrs = e.read(), e.code, dict(e.headers)
    elapsed = time.perf_counter() - t
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except Exception:
        parsed = raw.decode("utf-8", "replace")
    return status, {k.lower(): v for k, v in hdrs.items()}, parsed, elapsed


def start_server(app: str, port: int, app_dir: str):
    log_path = HERE / "check_all_server.log"
    log = open(log_path, "w", encoding="utf-8")
    cmd = [sys.executable, "-m", "uvicorn", app, "--port", str(port)]
    if app_dir:
        cmd += ["--app-dir", app_dir]
    proc = subprocess.Popen(cmd, cwd=HERE, stdout=log, stderr=subprocess.STDOUT,
                            env={**os.environ, "PYTHONUTF8": "1"})
    return proc, log_path


def wait_ready(base: str, proc, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            return False
        try:
            http("GET", "/health", base, timeout=3)
            return True
        except Exception:
            time.sleep(0.5)
    return False


# --------------------------------------------------------------------------
# [3] live checks
# --------------------------------------------------------------------------

TEXT = ("Ankara Türkiye'nin başkentidir. İstanbul Türkiye'nin başkentidir. "
        "Bence Türk kahvesi dünyanın en güzel kahvesidir.")

FACTS_10 = " ".join([
    "Paris Fransa'nın başkentidir.", "Berlin Almanya'nın başkentidir.", "Roma İtalya'nın başkentidir.",
    "Madrid İspanya'nın başkentidir.", "Tokyo Japonya'nın başkentidir.", "Lizbon Portekiz'in başkentidir.",
    "Atina Yunanistan'ın başkentidir.", "Viyana Avusturya'nın başkentidir.",
    "Varşova Polonya'nın başkentidir.", "Oslo Norveç'in başkentidir.",
])


def hint_for(err: str) -> str:
    e = (err or "").lower()
    if "401" in e or "invalid api key" in e or "unauthorized" in e:
        return "  (the API key was rejected - copy it again, no spaces or quotes)"
    if "429" in e or "rate" in e:
        return "  (rate limit - wait a minute and retry)"
    if "timeout" in e or "timed out" in e:
        return "  (a network call timed out)"
    return ""


def find_claim(results: list, needle: str):
    for r in results:
        if needle in (r.get("claim") or "").lower():
            return r
    return None


def live_checks(base: str, stress: bool) -> None:
    out(f"\n[3] Live checks against {base}")

    # ---- /health -----------------------------------------------------------
    try:
        st, _, h, _ = http("GET", "/health", base)
    except Exception as exc:
        record("FAIL", "GET /health", f"server not reachable: {exc}")
        return
    if st != 200 or not isinstance(h, dict):
        record("FAIL", "GET /health", f"HTTP {st}")
        return
    if h.get("init_error"):
        record("FAIL", "server started correctly", str(h["init_error"]))
        return
    cfg = h.get("config", {})
    record("PASS", "GET /health", f"retriever={cfg.get('retriever')} model={cfg.get('model')} "
           f"reasoning={cfg.get('reasoning_effort')} timeout={cfg.get('total_timeout_s')}s")
    total_timeout = float(cfg.get("total_timeout_s") or 45)

    # ---- /health/deep ------------------------------------------------------
    st, _, d, el = http("GET", "/health/deep", base)
    if st != 200 or not isinstance(d, dict):
        record("FAIL", "GET /health/deep", f"HTTP {st}: {str(d)[:200]}")
    else:
        for part, label in (("llm", "Groq (AI)"), ("search", "search provider")):
            r = d.get(part, {})
            if r.get("ok"):
                record("PASS", f"{label} reachable", f"{r.get('ms')} ms")
            else:
                record("FAIL", f"{label} reachable", f"{r.get('error')}{hint_for(r.get('error'))}")

    # ---- /verify: the main check --------------------------------------------
    first_ok = False
    try:
        st, _, r, el = http("POST", "/verify", base, {"text": TEXT})
    except Exception as exc:
        record("FAIL", "POST /verify", f"{type(exc).__name__}: {exc}")
        st, r, el = 0, None, 0.0
    if st == 200 and isinstance(r, dict) and r.get("status") == "ok":
        first_ok = True
        problems = contract.validate_verify_response(r, strict_dates=False)
        record("PASS" if not problems else "FAIL", "/verify matches the frontend JSON contract",
               "; ".join(problems[:3]))
        bad_dates = [s.get("published_date") for c in r.get("results", []) for s in c.get("sources") or []
                     if s.get("published_date") is not None
                     and not contract.ISO_DATE.match(str(s.get("published_date")))]
        record("PASS" if not bad_dates else "WARN", "published_date is YYYY-MM-DD or null",
               f"{len(bad_dates)} other formats, e.g. {bad_dates[:2]}" if bad_dates else "")
        bad_cites = [x for c in r.get("results", []) for x in contract.invalid_citations(c)]
        record("PASS" if not bad_cites else "WARN", "explanations cite only listed sources",
               f"unknown: {bad_cites[:3]}" if bad_cites else "")
        results = r.get("results", [])
        t = r.get("timings", {})
        record("PASS", "POST /verify answers", f"{el:.1f}s total ({len(results)} claims, "
               f"extract {t.get('extract_ms')} ms, partial={r.get('partial')})")
        if el <= total_timeout + 5:
            record("PASS", f"answered within the {total_timeout:.0f}s deadline")
        else:
            record("FAIL", f"answered within the {total_timeout:.0f}s deadline", f"took {el:.1f}s")

        out("\n     claim -> verdict   (status | sources used/found | retrieval ms / verdict ms)")
        for c in results:
            tm = c.get("timings_ms") or {}
            out(f"     - {(c.get('claim') or '')[:58]:<58} -> {c.get('verdict')}"
                f"   ({c.get('status')} | {len(c.get('used_sources') or [])}/{len(c.get('sources') or [])}"
                f" | {tm.get('retrieval_ms', '-')} / {tm.get('verify_ms', '-')})")
        out("")

        a = find_claim(results, "ankara")
        i = find_claim(results, "stanbul")
        o = find_claim(results, "kahve")
        if a is None or i is None:
            record("WARN", "claim extraction found both capital claims", f"got {len(results)} claims")
        else:
            record("PASS" if a.get("verdict") == "SUPPORTED" else "WARN",
                   "true claim (Ankara) judged SUPPORTED", f"got {a.get('verdict')}")
            record("PASS" if i.get("verdict") == "REFUTED" else "WARN",
                   "false claim (Istanbul) judged REFUTED", f"got {i.get('verdict')}")
        if o is None or o.get("is_verifiable") is False:
            record("PASS", "opinion is not fact-checked")
        else:
            record("WARN", "opinion is not fact-checked", f"got verdict {o.get('verdict')}")

        bad = [c for c in results if c.get("status") != "ok"]
        if bad:
            record("WARN", "every claim finished", "; ".join(
                f"{c.get('error_code')}@{c.get('failed_stage')}: {c.get('detail') or ''}{hint_for(c.get('detail'))}"
                for c in bad[:3]))
        else:
            record("PASS", "every claim finished")

        verifiable = [c for c in results if c.get("is_verifiable") and c.get("status") == "ok"]
        no_src = [c for c in verifiable if not c.get("sources")]
        bad_ids = [c for c in verifiable
                   if not set(c.get("used_sources") or []) <= {s["id"] for s in c.get("sources") or []}]
        invalid = [c for c in verifiable if c.get("verdict") not in VALID_VERDICTS]
        if invalid:
            record("FAIL", "verdict labels are valid", str([c.get("verdict") for c in invalid]))
        else:
            record("PASS", "verdict labels are valid")
        record("PASS" if not no_src else "WARN", "claims have sources",
               f"{len(no_src)} without sources" if no_src else "")
        record("PASS" if not bad_ids else "FAIL", "cited sources exist in the source list")

        rt = [c["timings_ms"]["retrieval_ms"] for c in verifiable if "retrieval_ms" in (c.get("timings_ms") or {})]
        vt = [c["timings_ms"]["verify_ms"] for c in verifiable if "verify_ms" in (c.get("timings_ms") or {})]
        if rt and vt:
            slow = "search" if sum(rt) / len(rt) > sum(vt) / len(vt) else "the AI judgement"
            out(f"     where the time goes: search avg {sum(rt)//len(rt)} ms, AI avg {sum(vt)//len(vt)} ms "
                f"-> slower part is {slow}")
    elif st != 0:
        err = r if isinstance(r, dict) else {}
        record("FAIL", "POST /verify answers", f"HTTP {st} {err.get('error')}: "
               f"{err.get('detail') or err.get('message') or str(r)[:150]}{hint_for(str(err.get('detail')))}")

    # ---- cache -------------------------------------------------------------
    if first_ok:
        st, _, r2, el2 = http("POST", "/verify", base, {"text": TEXT})
        if st == 200 and isinstance(r2, dict):
            ok_claims = [c for c in r2["results"] if c.get("is_verifiable") and c.get("status") == "ok"]
            cached = [c for c in ok_claims if c.get("cached")]
            if ok_claims and len(cached) == len(ok_claims):
                record("PASS", "repeat request served from cache", f"{el2:.1f}s (first was {el:.1f}s)")
            else:
                record("WARN", "repeat request served from cache", f"{len(cached)}/{len(ok_claims)} cached")
        else:
            record("FAIL", "repeat request", f"HTTP {st}")

    # ---- error handling ----------------------------------------------------
    st, _, r, _ = http("POST", "/verify", base, {})
    record("PASS" if st == 422 and isinstance(r, dict) and r.get("error") == "VALIDATION_ERROR" else "FAIL",
           "missing 'text' -> 422 VALIDATION_ERROR", f"got HTTP {st}")
    st, _, r, _ = http("POST", "/verify", base, {"text": "   "})
    record("PASS" if st == 400 and isinstance(r, dict) and r.get("error") == "EMPTY_TEXT" else "FAIL",
           "blank text -> 400 EMPTY_TEXT", f"got HTTP {st}")
    problems = contract.validate_error_body(r)
    record("PASS" if not problems else "FAIL", "error body matches the frontend contract", "; ".join(problems))
    st, _, r, _ = http("POST", "/verify/stream", base, {"text": "   "})
    record("PASS" if st == 400 and isinstance(r, dict) and r.get("error") == "EMPTY_TEXT" else "FAIL",
           "blank text on /verify/stream -> 400 EMPTY_TEXT (no LLM call)", f"got HTTP {st}")

    # ---- request id --------------------------------------------------------
    rid = "check-all-" + str(int(time.time()))
    st, hd, _, _ = http("GET", "/health", base, headers={"X-Request-ID": rid})
    if hd.get("x-request-id") == rid:
        record("PASS", "X-Request-ID is echoed")
    elif hd.get("x-request-id"):
        record("FAIL", "X-Request-ID is echoed", f"sent {rid}, got {hd.get('x-request-id')}")
    else:
        record("FAIL", "X-Request-ID is echoed", "no X-Request-ID header (older backend?)")

    # ---- CORS --------------------------------------------------------------
    origin = "https://verify-test-swart.vercel.app"
    st, hd, _, _ = http("OPTIONS", "/verify", base, headers={
        "Origin": origin, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"})
    record("PASS" if hd.get("access-control-allow-origin") == origin else "FAIL",
           "CORS allows the frontend (vercel) origin", f"HTTP {st}")

    # ---- streaming ---------------------------------------------------------
    check_stream(base)

    # ---- stress (optional) -------------------------------------------------
    if stress:
        out("\n     stress test: 10 claims at once ...")
        st, _, r, el = http("POST", "/verify", base, {"text": FACTS_10}, timeout=total_timeout + 30)
        if st == 200 and isinstance(r, dict):
            counts: dict = {}
            for c in r["results"]:
                counts[c["status"]] = counts.get(c["status"], 0) + 1
            record("PASS" if el <= total_timeout + 5 else "FAIL", "10 claims answered within the deadline",
                   f"{el:.1f}s, {counts}")
            if counts.get("timeout"):
                record("WARN", "no claim timed out under load",
                       "try LITE_QUERY_COUNT=2 or a higher CLAIM_CONCURRENCY in .env")
            if counts.get("skipped"):
                record("PASS", "claim cap works", f"{counts['skipped']} extra claims skipped (not dropped silently)")
        else:
            record("FAIL", "stress test", f"HTTP {st}")


def check_stream(base: str) -> None:
    text = "Madrid İspanya'nın başkentidir. Kahire Mısır'ın başkentidir."
    data = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base + "/verify/stream", data=data, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    t0 = time.perf_counter()
    events: list = []
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            cur = None
            for raw in r:
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if line.startswith("event:"):
                    cur = line[6:].strip()
                elif line.startswith("data:"):
                    try:
                        events.append((cur, time.perf_counter() - t0, json.loads(line[5:].strip())))
                    except ValueError:
                        pass
    except Exception as exc:
        record("FAIL", "POST /verify/stream", f"{type(exc).__name__}: {exc}")
        return
    kinds = [e[0] for e in events]
    at = {k: next((e[1] for e in events if e[0] == k), None) for k in ("claims", "done")}
    if not events:
        record("FAIL", "POST /verify/stream", "no events received")
    elif kinds[-1] == "error":
        record("FAIL", "stream finished", str(events[-1][2].get("detail") or events[-1][2].get("message")))
    elif "done" not in kinds or "result" not in kinds:
        record("FAIL", "stream delivers results and 'done'", f"events: {kinds}")
    else:
        results_at = [f"{e[1]:.1f}s" for e in events if e[0] == "result"]
        record("PASS", "POST /verify/stream", f"claims at {at['claims']:.1f}s, results at "
               f"{', '.join(results_at)}, done at {at['done']:.1f}s")
    if events:
        problems = contract.validate_stream([(e[0], e[2]) for e in events], strict_dates=False)
        record("PASS" if not problems else "FAIL", "stream matches the SSE contract", "; ".join(problems[:3]))
        if "started" not in kinds:
            record("WARN", "stream has started/stage events", "older backend: no request_id / stage events")
        stages = [e for e in events if e[0] == "stage"]
        if stages:
            out("     stages: " + ", ".join(f"{e[2].get('stage')} {e[2].get('status')} at {e[1]:.1f}s"
                                         + (f" ({e[2]['ms']} ms)" if e[2].get("ms") is not None else "")
                                         for e in stages))


# --------------------------------------------------------------------------
# [4] summary
# --------------------------------------------------------------------------

def summary() -> int:
    n = {s: sum(1 for r in RESULTS if r[0] == s) for s in ("PASS", "WARN", "FAIL", "SKIP")}
    out("\n" + "=" * 64)
    out(f"  PASS {n['PASS']}   WARN {n['WARN']}   FAIL {n['FAIL']}   SKIP {n['SKIP']}")
    out("=" * 64)
    for status in ("FAIL", "WARN"):
        for s, name, detail in RESULTS:
            if s == status:
                out(f"  {status}: {name}" + (f"  -  {detail}" if detail else ""))
    verdict = "ALL GOOD" if n["FAIL"] == 0 and n["WARN"] == 0 else (
        "WORKS, but check the WARN lines" if n["FAIL"] == 0 else "SOMETHING IS BROKEN - see the FAIL lines")
    out(f"\n  {verdict}")
    report = HERE / "check_all_report.txt"
    try:
        report.write_text("\n".join(LINES) + "\n", encoding="utf-8")
        out(f"  Report saved: {report}")
    except OSError:
        pass
    return 1 if n["FAIL"] else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Test all of backend_v2 with one command.")
    ap.add_argument("--url", help="test an already-running server instead of starting one")
    ap.add_argument("--app", default="app.main:app", help="uvicorn app path (default app.main:app)")
    ap.add_argument("--app-dir", default="", help="passed to uvicorn --app-dir (testing only)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--skip-live", action="store_true", help="offline tests only")
    ap.add_argument("--skip-unit", action="store_true", help="skip the offline tests")
    ap.add_argument("--stress", action="store_true", help="also send a 10-claim text (more API credits)")
    args = ap.parse_args()

    out("backend_v2 - full check   " + time.strftime("%Y-%m-%d %H:%M:%S"))
    # keys are only needed when this script starts the server and talks to Groq/Tavily
    env_ok = step_environment(check_keys=not args.url and not args.skip_live)
    if not args.skip_unit:
        step_unit_tests()

    if args.skip_live:
        record("SKIP", "live checks", "--skip-live")
        return summary()

    proc = None
    base = (args.url or "").rstrip("/")
    if not base:
        if not env_ok:
            out("\n[2] Server")
            record("SKIP", "live checks", "fix the FAIL lines in [0] first (packages / API keys)")
            return summary()
        out("\n[2] Starting the server ...")
        base = f"http://127.0.0.1:{args.port}"
        proc, log_path = start_server(args.app, args.port, args.app_dir)
        if not wait_ready(base, proc):
            tail = ""
            try:
                tail = "\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-12:])
            except OSError:
                pass
            record("FAIL", "server starts", "did not come up; last log lines below")
            out(tail)
            if proc.poll() is None:
                proc.terminate()
            return summary()
        record("PASS", "server starts", f"on {base} (log: {log_path.name})")

    try:
        live_checks(base, args.stress)
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
    return summary()


if __name__ == "__main__":
    sys.exit(main())
