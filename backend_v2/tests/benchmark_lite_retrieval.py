"""Standalone offline Lite benchmark; never imported by production or pytest.

Run: python3 -B backend_v2/tests/benchmark_lite_retrieval.py
Each sample uses a fresh child. Main RSS runs and tracemalloc runs are separate.
MiB (1024**2) is used for every field ending in _mb.
"""
from __future__ import annotations

import argparse
import asyncio
import gc
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).with_name("benchmark_results_lite.json")
MIB = 1024 * 1024
CONFIG = {
    "repeats": 3, "source_count": 8, "max_sources": 5,
    "small_payload_bytes": 128 * 1024, "large_payload_bytes": int(1.85 * MIB),
    "chunk_bytes": 16 * 1024, "header_delay_seconds": 0.05,
    "chunk_delay_seconds": 0.01, "sample_interval_seconds": 0.05,
    "memory_guard_mb": 405.0, "stress_headroom_mb": 320.0,
    "child_wall_guard_seconds": 100, "late_deadline_seconds": 0.30,
    "late_hold_after_new_claim_seconds": 0.20,
}
CLAIM = "Annual production increased by 20 percent in 2024 according to published reports."
# Same content for every URL, worker setting and claim. No full-page fixture copies.
PARAGRAPH = ("<p>" + (
    "Annual production increased by 20 percent in 2024. Published reports describe "
    "capacity, deliveries, investment and measured output across the reporting period. "
) * 5 + "</p>").encode("ascii")


def lifetime_peak_mb():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / MIB if sys.platform == "darwin" else peak / 1024


def current_rss_mb(pid):
    if sys.platform.startswith("linux"):
        try:
            for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
        except (OSError, ValueError):
            return None
    try:
        value = subprocess.check_output(
            ["/bin/ps", "-o", "rss=", "-p", str(pid)], text=True,
            stderr=subprocess.DEVNULL, timeout=2,
        ).strip()
        return int(value) / 1024 if value else None
    except (subprocess.SubprocessError, ValueError):
        return None


def emit(event, **data):
    print(json.dumps({"event": event, **data}), flush=True)


def child(spec):
    # Imports are outside the measurement window, but lifetime high-water is kept.
    import socket
    from unittest.mock import patch
    import requests
    from urllib3.response import HTTPResponse
    sys.path.insert(0, str(ROOT / "backend_v2"))
    sys.path.insert(0, str(ROOT / "retrieval_demo_lite"))
    import search_retrieval_lite as mod
    from app.retrieval import LiteRetriever

    mod.FETCH_SOURCE_LIMIT = CONFIG["source_count"]
    # Use documented production defaults, independent of the shell/.env file.
    mod.CONNECT_TIMEOUT, mod.READ_TIMEOUT = 3.0, 5.0
    mod.PAGE_BUDGET, mod.TAVILY_TIMEOUT, mod.TOTAL_DEADLINE = 10.0, 5.0, 20.0
    mod.SEARCH_RESULTS_PER_QUERY, mod.MAX_QUERY_COUNT = 5, 3
    mod.PREFILTER_SOURCE_LIMIT, mod.MAX_CHUNKS_PER_SOURCE = 10, 10
    mod.MIN_FETCHED_TEXT_CHARS, mod.MIN_SNIPPET_CHARS = 350, 60
    mod.CHUNK_TARGET_WORDS, mod.CHUNK_MAX_WORDS = 90, 135
    retriever = LiteRetriever(max_sources=CONFIG["max_sources"], workers=spec["workers_per_claim"])
    assert retriever.parallel_fetch
    lock = threading.Lock()
    stats = {"active": 0, "peak_active": 0, "peak_threads": 0,
             "after_new_peak_active": 0, "after_new_peak_threads": 0}
    late_started = threading.Event()
    late_release = threading.Event()
    late_done = threading.Event()
    late_active = [0]
    new_started = [False]
    late_released_at = [None]
    trace = spec.get("tracemalloc", False)

    def observe():
        count = threading.active_count()
        stats["peak_threads"] = max(stats["peak_threads"], count)
        stats["peak_active"] = max(stats["peak_active"], stats["active"])
        if new_started[0]:
            stats["after_new_peak_threads"] = max(stats["after_new_peak_threads"], count)
            stats["after_new_peak_active"] = max(stats["after_new_peak_active"], stats["active"])

    class GeneratedBody(io.RawIOBase):
        def __init__(self):
            self.offset = 0
            self.size = spec["payload_bytes_per_page"]
            self.prefix, self.suffix = b"<html><body><article>", b"</article></body></html>"
            self.finished = False

        def readable(self):
            return True

        def read(self, size=-1):
            if self.closed or self.offset >= self.size:
                return b""
            time.sleep(CONFIG["chunk_delay_seconds"])
            size = min(size if size >= 0 else CONFIG["chunk_bytes"], self.size - self.offset)
            out = bytearray()
            end = self.offset + size
            while self.offset < end:
                if self.offset < len(self.prefix):
                    piece = self.prefix[self.offset:min(end, len(self.prefix))]
                elif self.offset >= self.size - len(self.suffix):
                    i = self.offset - (self.size - len(self.suffix))
                    piece = self.suffix[i:i + end - self.offset]
                else:
                    i = (self.offset - len(self.prefix)) % len(PARAGRAPH)
                    n = min(end - self.offset, len(PARAGRAPH) - i,
                            self.size - len(self.suffix) - self.offset)
                    piece = PARAGRAPH[i:i + n]
                out.extend(piece)
                self.offset += len(piece)
            return bytes(out)

    class FetchResponse(requests.Response):
        def __init__(self, late):
            super().__init__()
            self.late = late
            self.closed_once = False

        def close(self):
            super().close()
            if not self.closed_once:
                self.closed_once = True
                with lock:
                    stats["active"] -= 1
                    if self.late:
                        late_active[0] -= 1
                        if late_active[0] == 0:
                            late_released_at[0] = time.monotonic()
                            late_done.set()
                    observe()

    class Tavily:
        def search(self, query, timeout=5, **kwargs):
            marker = "late" if "latewave" in query.casefold() else "normal"
            return {"results": [
                {"url": f"https://source{i}.example/{marker}/report", "title": "Annual production report",
                 "content": CLAIM * 3, "score": 0.9 - i * 0.01}
                for i in range(CONFIG["source_count"])
            ]}

    def dns(host, port, **kwargs):
        if host not in {f"source{i}.example" for i in range(CONFIG["source_count"])}:
            raise socket.gaierror("unexpected offline hostname")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    def transport(adapter, request, **kwargs):
        assert kwargs.get("stream") is True
        assert not kwargs.get("proxies")
        late = "/late/" in request.url
        with lock:
            stats["active"] += 1
            if late:
                late_active[0] += 1
                if late_active[0] == CONFIG["source_count"]:
                    late_started.set()
            observe()
        if late:
            if not late_release.wait(10):
                raise RuntimeError("late fixture release timed out")
        else:
            time.sleep(CONFIG["header_delay_seconds"])
        result = FetchResponse(late)
        result.status_code = 200
        result.url, result.request = request.url, request
        result.encoding = "utf-8"
        result.headers.update({"Content-Type": "text/html; charset=utf-8",
                               "Content-Length": str(spec["payload_bytes_per_page"])})
        result.raw = HTTPResponse(body=GeneratedBody(), preload_content=False)
        return result

    async def detailed(claim):
        # Installed real Lite adapter owns mod._build_candidates; retain diagnostics.
        return await asyncio.to_thread(mod.search_detailed, claim, CONFIG["max_sources"])

    async def workload():
        if spec["scenario"] != "G":
            started = time.monotonic()
            results = await asyncio.gather(*(detailed(CLAIM) for _ in range(spec["claim_count"])))
            return results, {"retrieval_latency_seconds": time.monotonic() - started}
        mod.TOTAL_DEADLINE = CONFIG["late_deadline_seconds"]
        first_start = time.monotonic()
        expired = await detailed("latewave " + CLAIM)
        timeout_at = time.monotonic()
        assert expired["diagnostics"]["timed_out"]
        assert late_started.is_set(), "all first-wave workers must be running"
        with lock:
            timeout_counts = {"timeout_active_fetches": stats["active"],
                              "timeout_python_threads": threading.active_count()}
            new_started[0] = True
        emit("late_timeout", timeout_response_seconds=timeout_at - first_start, **timeout_counts)
        mod.TOTAL_DEADLINE = 20.0
        async def release_later():
            await asyncio.sleep(CONFIG["late_hold_after_new_claim_seconds"])
            late_release.set()
        releaser = asyncio.create_task(release_later())
        second_start = time.monotonic()
        normal = await detailed(CLAIM)
        second_latency = time.monotonic() - second_start
        await releaser
        while not late_done.is_set():
            await asyncio.sleep(0.005)
        return [expired, normal], {
            "retrieval_latency_seconds": time.monotonic() - first_start,
            "timeout_response_seconds": timeout_at - first_start,
            "new_claim_latency_seconds": second_latency,
            "late_worker_cleanup_seconds": late_released_at[0] - timeout_at,
            **timeout_counts,
        }

    with patch.object(mod, "_tavily_client", Tavily()), \
         patch.object(mod.socket, "getaddrinfo", side_effect=dns), \
         patch.object(requests.adapters.HTTPAdapter, "send", new=transport):
        gc.collect()
        baseline_threads = threading.active_count()
        emit("ready", baseline_python_threads=baseline_threads,
             import_ru_maxrss_mb=lifetime_peak_mb())
        if sys.stdin.readline().strip() != "go":
            raise RuntimeError("parent handshake missing")
        if trace:
            import tracemalloc
            tracemalloc.start()
        wall_start = time.monotonic()
        try:
            results, timings = asyncio.run(workload())
        finally:
            late_release.set()
        traced = None
        if trace:
            current, peak = tracemalloc.get_traced_memory()
            traced = {"python_current_mb": current / MIB, "python_peak_mb": peak / MIB}
            tracemalloc.stop()
        emit("result", **timings,
             total_child_workload_seconds=time.monotonic() - wall_start,
             ru_maxrss_mb=lifetime_peak_mb(), baseline_python_threads=baseline_threads,
             peak_python_threads=stats["peak_threads"], peak_active_fetches=stats["peak_active"],
             after_new_peak_active_fetches=stats["after_new_peak_active"],
             after_new_peak_python_threads=stats["after_new_peak_threads"],
             returned_source_count=[len(r["sources"]) for r in results],
             timed_out=[r["diagnostics"]["timed_out"] for r in results],
             partial_result=[r["diagnostics"]["partial_result"] for r in results],
             timeout_stage=[r["diagnostics"]["timeout_stage"] for r in results],
             result_status="timed_out" if any(r["diagnostics"]["timed_out"] for r in results) else "completed",
             tracemalloc=traced)


def run_sample(spec, repeat):
    import queue
    messages = queue.Queue()
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--child", json.dumps(spec)]
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, bufsize=1)
    def read_output():
        for line in proc.stdout:
            try:
                messages.put(json.loads(line))
            except json.JSONDecodeError:
                messages.put({"event": "log", "text": line})
    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    result = {**spec, "repeat": repeat, "fetch_url_count_per_claim": CONFIG["source_count"],
              "baseline_rss_mb": None, "peak_sampled_rss_mb": None, "delta_rss_mb": None,
              "ru_maxrss_mb": None, "baseline_python_threads": None, "peak_python_threads": None,
              "peak_active_fetches": None, "retrieval_latency_seconds": None,
              "late_worker_cleanup_seconds": None, "returned_source_count": [],
              "timed_out": [], "partial_result": [], "result_status": "skipped"}
    start = time.monotonic()
    sampling = False
    while proc.poll() is None or not messages.empty():
        rss = current_rss_mb(proc.pid) if proc.poll() is None else None
        if sampling and rss is not None:
            result["peak_sampled_rss_mb"] = max(result["peak_sampled_rss_mb"], rss)
        if rss is not None and rss >= CONFIG["memory_guard_mb"]:
            result["result_status"] = "aborted_by_memory_guard"
            result["guard_observed_rss_mb"] = rss
            proc.terminate()
            break
        if time.monotonic() - start > CONFIG["child_wall_guard_seconds"]:
            result["result_status"] = "skipped"
            result["reason"] = "child_wall_guard"
            proc.terminate()
            break
        try:
            event = messages.get(timeout=CONFIG["sample_interval_seconds"])
        except queue.Empty:
            continue
        kind = event.pop("event")
        if kind == "ready":
            rss = current_rss_mb(proc.pid)
            if rss is None:
                proc.terminate()
                raise RuntimeError("RSS sampling unavailable; cannot run guarded benchmark")
            result.update(event)
            result["baseline_rss_mb"] = result["peak_sampled_rss_mb"] = rss
            sampling = True
            proc.stdin.write("go\n")
            proc.stdin.flush()
        elif kind in ("result", "late_timeout"):
            result.update(event)
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    reader.join(timeout=1)
    # Drain final result if process exited between poll and reader delivery.
    while not messages.empty():
        event = messages.get()
        if event.pop("event", None) == "result" and result["result_status"] != "aborted_by_memory_guard":
            result.update(event)
    errors = proc.stderr.read()
    if errors:
        result["stderr"] = errors[-4000:]
    if proc.returncode and result["result_status"] != "aborted_by_memory_guard":
        result["reason"] = f"child_exit_{proc.returncode}"
    if result["baseline_rss_mb"] is not None:
        result["delta_rss_mb"] = result["peak_sampled_rss_mb"] - result["baseline_rss_mb"]
    return result


def summarize(runs):
    groups = {}
    for run in runs:
        key = run["scenario"] + ("_trace" if run.get("tracemalloc") is not None and isinstance(run.get("tracemalloc"), dict) else "")
        groups.setdefault(key, []).append(run)
    summary = {}
    for key, values in groups.items():
        measured = [r for r in values if r.get("retrieval_latency_seconds") is not None]
        def median(field):
            vals = [r[field] for r in measured if r.get(field) is not None]
            return statistics.median(vals) if vals else None
        def maximum(field):
            vals = [r[field] for r in values if r.get(field) is not None]
            return max(vals) if vals else None
        summary[key] = {
            "runs": len(values), "statuses": [r["result_status"] for r in values],
            "median_latency_seconds": median("retrieval_latency_seconds"),
            "median_delta_rss_mb": median("delta_rss_mb"),
            "maximum_observed_rss_mb": maximum("peak_sampled_rss_mb"),
            "maximum_lifetime_rss_mb": maximum("ru_maxrss_mb"),
            "maximum_active_fetches": maximum("peak_active_fetches"),
            "maximum_python_threads": maximum("peak_python_threads"),
        }
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", help=argparse.SUPPRESS)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.child:
        child(json.loads(args.child))
        return
    CONFIG["repeats"] = max(1, args.repeats)
    if current_rss_mb(os.getpid()) is None:
        raise SystemExit("RSS unavailable: run with permission to inspect child processes")
    targets = ["backend_v2/app/retrieval.py", "retrieval_demo_lite/search_retrieval_lite.py",
               "backend_v2/tests/test_lite_adapter.py", "retrieval_demo_lite/tests/test_source_fetch_security.py"]
    def hashes():
        return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in targets}
    report = {"platform": {"os": platform.platform(), "python": platform.python_version(),
                           "machine": platform.machine()}, "config": dict(CONFIG),
              "rss_units": "MiB", "source_hashes_before": hashes(), "raw_runs": [],
              "notes": ["Local macOS/Linux process RSS is not Render container memory.",
                        "Main run latencies exclude imports and tracemalloc.",
                        "Active fetch spans transport entry through response close (including extraction).",
                        "Python thread peaks observed at fetch entry/exit; may miss unrelated brief threads.",
                        "HTML repeats prose paragraphs; DOM shape is fixed, not worst-case arbitrary HTML.",
                        "tracemalloc results must not be pooled with primary performance measurements."]}
    def save():
        report["scenario_summary"] = summarize(report["raw_runs"])
        report["source_hashes_after"] = hashes()
        OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    def scenario(name, claims, workers, large=False, trace=False):
        return {"scenario": name, "claim_count": claims, "workers_per_claim": workers,
                "payload_bytes_per_page": CONFIG["large_payload_bytes" if large else "small_payload_bytes"],
                "tracemalloc": trace}
    small = [scenario(name, claims, workers) for name, claims, workers in
             [("A", 1, 1), ("B", 1, 2), ("C", 1, 4), ("D", 1, 8),
              ("E", 2, 8), ("F", 3, 8), ("H", 4, 8), ("G", 2, 8)]]
    stress = [scenario(f"S{workers}", 1, workers, large=True) for workers in (1, 2, 4, 8)]
    stress += [scenario(f"S8x{claims}", claims, 8, large=True) for claims in (2, 3, 4)]
    trace = [scenario(name, 1, workers, trace=True) for name, workers in [("A", 1), ("C", 4), ("D", 8)]]
    stop_stress = False
    try:
        for spec in small + stress + trace:
            if spec in stress and stop_stress:
                report["raw_runs"].append({**spec, "result_status": "skipped",
                                          "reason": "previous_stress_exceeded_headroom_or_guard"})
                save()
                print(spec["scenario"], "SKIPPED: stress headroom", flush=True)
                continue
            for repeat in range(1, CONFIG["repeats"] + 1):
                run = run_sample(spec, repeat)
                report["raw_runs"].append(run)
                save()
                print(spec["scenario"], "trace" if spec["tracemalloc"] else "rss", repeat,
                      run["result_status"], "latency", run.get("retrieval_latency_seconds"),
                      "RSS", run.get("peak_sampled_rss_mb"), "fetch", run.get("peak_active_fetches"), flush=True)
                if spec in stress and (run["result_status"] == "aborted_by_memory_guard" or
                        max(run.get("peak_sampled_rss_mb") or 0, run.get("ru_maxrss_mb") or 0)
                        >= CONFIG["stress_headroom_mb"]):
                    stop_stress = True
                    if run["result_status"] == "aborted_by_memory_guard":
                        break
    finally:
        save()
    print(json.dumps(report["scenario_summary"], indent=2), flush=True)
    print("Results:", OUTPUT, flush=True)


if __name__ == "__main__":
    main()
