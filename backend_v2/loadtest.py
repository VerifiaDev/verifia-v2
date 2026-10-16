"""
Load test: many /verify (or /verify/stream) requests at the same time against a running
server; reports latency percentiles, status / error codes, request ids and server RAM.

    cd backend_v2
    # offline, no keys: starts tests/fake_server.py itself and samples its RAM
    python loadtest.py --spawn-fake --requests 200 --concurrency 20

    # against a deployed server: SPENDS GROQ/TAVILY QUOTA, keep the numbers small
    python loadtest.py --url https://<backend> --requests 6 --concurrency 3

Exit code 1 if any request failed in a way the API contract does not allow
(network error, 5xx without a JSON error body, missing X-Request-ID, bad SSE order)
or if --max-p95 / --max-rss-mb is exceeded.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tests"))
from contract import parse_sse, validate_error_body, validate_stream, validate_verify_response  # noqa: E402

TEXT = "Ankara Türkiye'nin başkentidir. İstanbul'un nüfusu 15 milyonu geçer."


def rss_mb(pid: int):
    """Resident memory of a process in MB (Linux /proc; None elsewhere)."""
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        return None
    return None


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def one(c: httpx.AsyncClient, url: str, text: str, stream: bool) -> dict:
    t = time.perf_counter()
    path = "/verify/stream" if stream else "/verify"
    try:
        r = await c.post(url + path, json={"text": text})
    except httpx.HTTPError as exc:
        return {"ok": False, "status": None, "error": type(exc).__name__, "s": time.perf_counter() - t, "problems": [str(exc)]}
    took = time.perf_counter() - t
    problems = []
    rid = r.headers.get("x-request-id")
    if not rid:
        problems.append("X-Request-ID missing")
    code = None
    partial = None
    if r.status_code == 200 and stream:
        events = parse_sse(r.text)
        problems += validate_stream(events, strict_dates=False)
        last = events[-1][1] if events else {}
        code = last.get("error") if last.get("type") == "error" else None
        partial = last.get("partial")
    elif r.status_code == 200:
        body = r.json()
        problems += validate_verify_response(body, strict_dates=False)
        partial = body.get("partial")
    else:
        try:
            body = r.json()
            problems += validate_error_body(body, status_code=r.status_code)
            code = body.get("error")
        except ValueError:
            problems.append(f"HTTP {r.status_code} without JSON body")
    return {"ok": not problems, "status": r.status_code, "error": code, "partial": partial,
            "s": took, "rid": rid, "problems": problems}


async def run(url: str, n: int, conc: int, stream: bool, text: str, pid=None) -> tuple:
    sem = asyncio.Semaphore(conc)
    rss = []
    stop = asyncio.Event()

    async def sampler():
        while not stop.is_set():
            v = rss_mb(pid) if pid else None
            if v:
                rss.append(v)
            await asyncio.sleep(0.05)

    async def guarded(c, i):
        async with sem:
            # distinct texts so the server cache does not answer for free
            return await one(c, url, f"{text} (#{i})", stream)

    limits = httpx.Limits(max_connections=conc, max_keepalive_connections=conc)
    async with httpx.AsyncClient(timeout=120, limits=limits) as c:
        await c.get(url + "/health")  # wake up / warm up, not measured
        rss_before = rss_mb(pid) if pid else None
        samp = asyncio.create_task(sampler())
        t = time.perf_counter()
        results = await asyncio.gather(*[guarded(c, i) for i in range(n)])
        wall = time.perf_counter() - t
        stop.set()
        await samp
        h0 = time.perf_counter()
        await c.get(url + "/health")
        health_after = time.perf_counter() - h0
    return results, wall, rss_before, rss, health_after


def report(results, wall, rss_before, rss, health_after, conc) -> dict:
    lat = sorted(r["s"] for r in results)
    q = statistics.quantiles(lat, n=100) if len(lat) >= 2 else lat * 99
    rids = [r.get("rid") for r in results if r.get("rid")]
    out = {
        "requests": len(results),
        "concurrency": conc,
        "wall_s": round(wall, 2),
        "throughput_rps": round(len(results) / wall, 1) if wall else None,
        "p50_ms": round(q[49] * 1000), "p95_ms": round(q[94] * 1000), "max_ms": round(lat[-1] * 1000),
        "http_status": dict(Counter(str(r["status"]) for r in results)),
        "error_codes": dict(Counter(r["error"] for r in results if r["error"])),
        "partial": sum(1 for r in results if r.get("partial")),
        "contract_problems": sum(1 for r in results if not r["ok"]),
        "request_ids_unique": len(set(rids)) == len(rids) == len(results),
        "health_after_ms": round(health_after * 1000),
    }
    if rss:
        out.update(rss_before_mb=round(rss_before, 1), rss_peak_mb=round(max(rss), 1), rss_end_mb=round(rss[-1], 1))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", help="server base URL (no trailing slash)")
    ap.add_argument("--spawn-fake", action="store_true", help="start tests/fake_server.py (offline) and test it")
    ap.add_argument("--fake-delay", type=float, default=0.3, help="fake search delay per claim, seconds")
    ap.add_argument("--fake-cache", action="store_true",
                    help="keep the fake server's result cache on (off by default: its claims never change)")
    ap.add_argument("--requests", type=int, default=100)
    ap.add_argument("--concurrency", type=int, default=10)
    ap.add_argument("--stream", action="store_true", help="use /verify/stream instead of /verify")
    ap.add_argument("--text", default=TEXT)
    ap.add_argument("--max-p95", type=float, help="fail if p95 latency (seconds) is higher")
    ap.add_argument("--max-rss-mb", type=float, help="fail if server peak RSS (MB) is higher (--spawn-fake only)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON only")
    a = ap.parse_args()
    if bool(a.url) == a.spawn_fake:
        ap.error("give exactly one of --url or --spawn-fake")

    proc = None
    url = (a.url or "").rstrip("/")
    if a.spawn_fake:
        port = free_port()
        env = {**os.environ, "PORT": str(port), "FAKE_DELAY": str(a.fake_delay),
               "FAKE_CACHE": "1" if a.fake_cache else "0"}
        # the server log goes to a file: an unread pipe fills up and blocks the server
        log_file = tempfile.NamedTemporaryFile("w+", prefix="fake_server_", suffix=".log", delete=False)
        proc = subprocess.Popen([sys.executable, str(HERE / "tests" / "fake_server.py")], env=env,
                                stdout=log_file, stderr=subprocess.STDOUT, text=True)
        url = f"http://127.0.0.1:{port}"
        for _ in range(100):
            try:
                if httpx.get(url + "/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        else:
            proc.kill()
            print(Path(log_file.name).read_text(), file=sys.stderr)
            print("fake server did not start", file=sys.stderr)
            return 2
    try:
        res = asyncio.run(run(url, a.requests, a.concurrency, a.stream, a.text, proc.pid if proc else None))
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            log_file.close()
            os.unlink(log_file.name)

    results = res[0]
    rep = report(*res, a.concurrency)
    rep["endpoint"] = "/verify/stream" if a.stream else "/verify"
    rep["target"] = "fake (tests/fake_server.py)" if a.spawn_fake else url
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        for k, v in rep.items():
            print(f"{k:>20}: {v}")
        for r in results:
            if not r["ok"]:
                print(f"  problem (HTTP {r['status']}): {r['problems'][:3]}")
    failed = rep["contract_problems"] > 0 or not rep["request_ids_unique"]
    if a.max_p95 is not None and rep["p95_ms"] > a.max_p95 * 1000:
        print(f"FAIL: p95 {rep['p95_ms']} ms > {a.max_p95 * 1000:.0f} ms", file=sys.stderr)
        failed = True
    if a.max_rss_mb is not None and rep.get("rss_peak_mb", 0) > a.max_rss_mb:
        print(f"FAIL: peak RSS {rep['rss_peak_mb']} MB > {a.max_rss_mb} MB", file=sys.stderr)
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
