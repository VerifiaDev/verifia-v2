"""Offline admission/executor diagnosis; all blocking work is local and event-controlled."""
import asyncio
import json
import threading
import time
from types import SimpleNamespace as NS

import httpx
import pytest

from app import main, pipeline
from app.resources import TrackingExecutor, ClaimLease


class ControlledBackend:
    def __init__(self, loop, blocked_claims, occupied_at):
        self.loop = loop
        self.blocked_claims = blocked_claims
        self.occupied_at = occupied_at
        self.release = threading.Event()
        self.occupied = asyncio.Event()
        self.records = []
        self.lock = threading.Lock()
        self.running_blocked = 0

    async def call(self, request, stage, function, block=False):
        record = {"request": request, "stage": stage, "submitted": time.perf_counter(),
                  "started": None, "finished": None}
        self.records.append(record)

        def worker():
            record["started"] = time.perf_counter()
            if block:
                with self.lock:
                    self.running_blocked += 1
                    if self.running_blocked == self.occupied_at:
                        self.loop.call_soon_threadsafe(self.occupied.set)
                try:
                    if not self.release.wait(5):
                        raise AssertionError("Test barrier was not released")
                finally:
                    with self.lock:
                        self.running_blocked -= 1
            try:
                return function()
            finally:
                record["finished"] = time.perf_counter()

        return await asyncio.to_thread(worker)

    async def extract(self, text):
        count = self.blocked_claims if text == "first" else 1
        return await self.call(text, "extract", lambda: NS(claims=[
            NS(id=f"c{i}", text=f"{text}:{i}", is_verifiable=True) for i in range(count)
        ]))

    async def retrieve(self, text):
        request = text.split(":")[0]
        return await self.call(request, "retrieval", lambda: [
            {"id": "source_1", "url": "https://offline.invalid", "text": "synthetic evidence"}
        ], block=request == "first")

    async def verify(self, text, sources):
        return await self.call(text.split(":")[0], "verdict", lambda: NS(
            verdict="SUPPORTED", explanation="synthetic result", used_sources=["source_1"]))

    def stage_metrics(self, request, at):
        out = []
        for record in self.records:
            if record["request"] != request:
                continue
            start, finish, submitted = record["started"], record["finished"], record["submitted"]
            out.append({
                "stage": record["stage"], "started": start is not None,
                "queue_ms": round(((start or at) - submitted) * 1000, 2),
                "execution_ms": round(((finish or at) - start) * 1000, 2) if start else None,
                "finished": finish is not None,
            })
        return out


async def post(client, text):
    started = time.perf_counter()
    response = await client.post("/verify", json={"text": text})
    ended = time.perf_counter()
    body = response.json()
    return response, {
        "request": text, "http_status": response.status_code,
        "error": body.get("error"), "total_ms": round((ended - started) * 1000, 2),
        "request_id": response.headers.get("x-request-id"),
        "partial": body.get("partial"), "pipeline_timings": body.get("timings"),
        "results": [{k: r[k] for k in ("status", "error_code", "failed_stage", "timings_ms") if k in r}
                    for r in body.get("results", [])],
    }, ended


class LegacyClaimLease(ClaimLease):
    """Test-only negative control: reproduce the original early slot release."""
    def release_if_done(self):
        if self.finished and not self.released:
            self.released = True
            self.semaphore.release()


async def wait_until(predicate):
    loop = asyncio.get_running_loop()
    ready = loop.create_future()

    def check():
        if ready.done():
            return
        if predicate():
            ready.set_result(None)
        else:
            loop.call_later(0.001, check)

    check()
    await asyncio.wait_for(ready, 2)


@pytest.mark.parametrize("retention", ["legacy", "fixed"])
@pytest.mark.parametrize("blocked_claims,total_timeout", [(4, 1.5), (8, 1.5), (8, 0.45)])
def test_two_requests_with_abandoned_sync_work(fake, monkeypatch, blocked_claims, total_timeout, retention):
    """Eight real executor threads; compare baseline, spare capacity, and orphan saturation.

    Short diagnostic budgets reproduce ordering, not production wall-clock latency.
    The legacy negative control changes only claim-slot release, not work or budgets.
    """
    if retention == "legacy":
        monkeypatch.setattr(pipeline, "ClaimLease", LegacyClaimLease)
    assert main.guard.maximum == 2, "Diagnosis expects the deployment-default admission limit"
    for key, value in dict(extract_timeout=0.15, claim_timeout=0.30,
                           total_timeout=total_timeout, claim_concurrency=4,
                           max_claims=8, expose_detail=False).items():
        monkeypatch.setattr(main.settings.pipeline, key, value)

    async def run():
        loop = asyncio.get_running_loop()
        executor = TrackingExecutor(max_workers=8)
        loop.set_default_executor(executor)
        occupied_at = blocked_claims if retention == "legacy" else min(4, blocked_claims)
        backend = ControlledBackend(loop, blocked_claims, occupied_at)
        first_timeout = asyncio.Event()
        original_process = pipeline._process_claim

        async def process(claim, **kwargs):
            result = await original_process(claim, **kwargs)
            if claim.text.startswith("first:") and result.get("error_code") == "CLAIM_TIMEOUT":
                first_timeout.set()
            return result

        monkeypatch.setattr(pipeline, "_process_claim", process)
        monkeypatch.setitem(main.state, "llm", NS(extract=backend.extract, verify=backend.verify))
        monkeypatch.setitem(main.state, "retriever", backend.retrieve)
        tasks = []
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                         base_url="http://offline") as client:
                baseline, baseline_metrics, ended = await post(client, "second")
                baseline_metrics["stages"] = backend.stage_metrics("second", ended)
                assert baseline.status_code == 200 and baseline.json()["partial"] is False
                backend.records.clear()

                first = asyncio.create_task(post(client, "first"))
                tasks.append(first)
                # Trigger only when real synchronous workers occupy the intended slots.
                occupied = asyncio.create_task(backend.occupied.wait())
                tasks.append(occupied)
                done, _ = await asyncio.wait({first, occupied}, timeout=2,
                                             return_when=asyncio.FIRST_COMPLETED)
                assert occupied in done, "First request never reached the expected occupancy"
                if retention == "fixed" and blocked_claims == 8:
                    await asyncio.wait_for(first_timeout.wait(), 2)
                assert backend.running_blocked == occupied_at
                assert not first.done(), "Requests would not overlap"
                second = asyncio.create_task(post(client, "second"))
                tasks.append(second)
                second_response, second_metrics, second_ended = await asyncio.wait_for(second, 2)
                second_metrics["stages"] = backend.stage_metrics("second", second_ended)
                first_response, first_metrics, first_ended = await asyncio.wait_for(first, 2)
                first_metrics["stages"] = backend.stage_metrics("first", first_ended)
                active_before_release = main.guard.active

                assert first_response.status_code == 200
                assert first_response.json()["partial"] is True
                codes = {r.get("error_code") for r in first_response.json()["results"]}
                assert "CLAIM_TIMEOUT" in codes
                if total_timeout < 0.60 or (retention == "fixed" and blocked_claims == 8):
                    assert "DEADLINE_EXCEEDED" in codes
                else:
                    assert codes == {"CLAIM_TIMEOUT"}
                extraction = [r for r in backend.records
                              if r["request"] == "second" and r["stage"] == "extract"]
                assert len(extraction) == 1
                if blocked_claims == 4 or retention == "fixed":
                    assert second_response.status_code == 200
                    assert second_response.json()["partial"] is False
                    assert extraction[0]["started"] is not None
                else:
                    assert second_response.status_code == 504
                    assert second_response.json()["error"] == "EXTRACTION_TIMEOUT"
                    assert extraction[0]["started"] is None
                assert backend.running_blocked == occupied_at
                first_retrievals = [r for r in backend.records
                                    if r["request"] == "first" and r["stage"] == "retrieval"]
                assert len(first_retrievals) == occupied_at
                assert active_before_release == 1, "Only the abandoned first request should retain admission"
                print("\nEXECUTOR_DIAG " + json.dumps({
                    "retention": retention, "executor_workers": 8, "blocked_claims": blocked_claims,
                    "actually_running": occupied_at,
                    "diagnostic_budgets": {"extract": 0.15, "claim": 0.30, "total": total_timeout},
                    "baseline": baseline_metrics, "concurrent": [first_metrics, second_metrics],
                    "active_before_release": active_before_release,
                }, sort_keys=True))
                backend.release.set()
                await wait_until(lambda: main.guard.active == 0)
                recovered, recovered_metrics, _ = await post(client, "second")
                assert recovered.status_code == 200 and recovered.json()["partial"] is False
                print("RECOVERED " + json.dumps(recovered_metrics, sort_keys=True))
        finally:
            backend.release.set()
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            # Join without blocking the event loop; queued completion callbacks release leases.
            await loop.shutdown_default_executor()
        assert main.guard.active == 0
        if blocked_claims == 8 and retention == "legacy":
            assert extraction[0]["started"] is None, "Cancelled queued extraction must never execute"

    asyncio.run(run())
