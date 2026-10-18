"""
Cancelling run_pipeline (e.g. the SSE client disconnects) must stop the per-claim tasks.
Without the `except CancelledError` block around asyncio.wait in run_pipeline, every claim kept
running after the cancel and kept spending Groq/Tavily quota.
Run:   python tests/test_pipeline_cancel.py        (or: pytest tests)
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline import PipelineConfig, run_pipeline  # noqa: E402


def test_cancel_stops_running_and_queued_claims():
    stats = {"started": 0, "cancelled": 0, "finished": 0}

    async def extract(text):
        return NS(claims=[NS(id=f"c{i}", text=f"iddia {i}", is_verifiable=True) for i in range(6)])

    async def retrieve(text):
        stats["started"] += 1
        try:
            await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            stats["cancelled"] += 1
            raise
        stats["finished"] += 1
        return []

    async def verify(text, sources):
        return NS(verdict="NOT ENOUGH EVIDENCE", explanation="x", used_sources=[])

    async def scenario():
        cfg = PipelineConfig(claim_concurrency=2, total_timeout=30)
        task = asyncio.create_task(
            run_pipeline("metin", extract=extract, retrieve=retrieve, verify=verify, cfg=cfg)
        )
        await asyncio.sleep(0.2)          # 2 claims running, 4 queued behind the semaphore
        task.cancel()
        try:
            await task
            raised = False
        except asyncio.CancelledError:
            raised = True
        await asyncio.sleep(0.8)          # leaked claims would finish inside this window
        leaked = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        return raised, leaked

    raised, leaked = asyncio.run(scenario())

    assert raised, "the cancellation must propagate to the caller"
    assert stats["started"] == 2, "queued claims must never start after the cancel"
    assert stats["cancelled"] == 2, "running claims must be cancelled"
    assert stats["finished"] == 0, "no claim may finish (and spend quota) after the cancel"
    assert leaked == [], "no per-claim task may be left behind"


if __name__ == "__main__":
    test_cancel_stops_running_and_queued_claims()
    print("ok")
