"""Claim ownership tests with real executor futures and local event barriers."""
import asyncio
import threading
from types import SimpleNamespace as NS

import pytest

from app.limits import UpstreamGate
from app.resources import ClaimLease, Lease, TrackingExecutor, current_claim_lease, current_lease
from test_executor_diagnosis import wait_until


@pytest.mark.parametrize("outcome", ["success", "exception", "cancel"])
def test_claim_slot_waits_for_real_future_and_releases_once(outcome):
    async def run():
        loop = asyncio.get_running_loop()
        loop.set_default_executor(TrackingExecutor(max_workers=8))
        semaphore = asyncio.BoundedSemaphore(1)
        await semaphore.acquire()
        claim = ClaimLease(semaphore, loop)
        guard = NS(active=1)
        request = Lease(guard)
        started = asyncio.Event()
        release = threading.Event()
        claim_token = current_claim_lease.set(claim)
        request_token = current_lease.set(request)

        def work():
            loop.call_soon_threadsafe(started.set)
            if not release.wait(5):
                raise AssertionError("Unreleased test barrier")
            if outcome == "exception":
                raise ValueError("synthetic worker error")
            return "ok"

        task = asyncio.create_task(asyncio.to_thread(work))
        current_claim_lease.reset(claim_token)
        current_lease.reset(request_token)
        try:
            await asyncio.wait_for(started.wait(), 2)
            assert claim.pending == request.pending == 1
            if outcome == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                claim.finished = request.finished = True
                claim.release_if_done()
                request.release_if_done()
                assert not claim.released and semaphore.locked() and guard.active == 1
            else:
                # The future may finish before the coroutine finalizer: do not release early.
                release.set()
                if outcome == "exception":
                    with pytest.raises(ValueError, match="synthetic worker error"):
                        await task
                else:
                    assert await task == "ok"
                await wait_until(lambda: claim.pending == request.pending == 0)
                assert not claim.released and semaphore.locked()
                claim.finished = request.finished = True
                claim.release_if_done()
                request.release_if_done()
            release.set()
            await wait_until(lambda: claim.released and guard.active == 0)
            assert claim.pending == request.pending == 0
            # BoundedSemaphore would raise on a duplicate release.
            claim.release_if_done()
            claim.release_if_done()
            request.release_if_done()
            await asyncio.wait_for(semaphore.acquire(), 1)
            assert semaphore.locked()
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
            await loop.shutdown_default_executor()
        assert current_claim_lease.get() is None and current_lease.get() is None

    asyncio.run(run())


def test_executor_submit_failure_rolls_back_both_owners():
    async def run():
        loop = asyncio.get_running_loop()
        executor = TrackingExecutor(max_workers=8)
        executor.shutdown(wait=False)
        semaphore = asyncio.BoundedSemaphore(1)
        await semaphore.acquire()
        claim = ClaimLease(semaphore, loop)
        request = Lease(NS(active=1))
        a = current_claim_lease.set(claim)
        b = current_lease.set(request)
        try:
            with pytest.raises(RuntimeError, match="shutdown"):
                executor.submit(lambda: None)
            assert claim.pending == request.pending == 0
            claim.finished = request.finished = True
            claim.release_if_done()
            request.release_if_done()
            assert claim.released and request.guard.active == 0
        finally:
            current_claim_lease.reset(a)
            current_lease.reset(b)

    asyncio.run(run())


def test_shared_queued_task_retains_creator_after_creator_cancels():
    async def run():
        loop = asyncio.get_running_loop()
        loop.set_default_executor(TrackingExecutor(max_workers=8))
        semaphore = asyncio.BoundedSemaphore(1)
        await semaphore.acquire()
        owner = ClaimLease(semaphore, loop)
        guard = NS(active=1)
        request = Lease(guard)
        gate = UpstreamGate(1)
        gate_sem = gate._semaphore()
        await gate_sem.acquire()  # Shared call is queued before submitting any synchronous work.
        worker_started = asyncio.Event()
        release = threading.Event()
        calls = []

        def worker():
            assert current_claim_lease.get() is owner
            assert current_lease.get() is request
            calls.append(1)
            loop.call_soon_threadsafe(worker_started.set)
            if not release.wait(5):
                raise AssertionError("Unreleased shared worker")
            return ["shared-result"]

        async def factory():
            return await asyncio.to_thread(worker)

        a = current_claim_lease.set(owner)
        b = current_lease.set(request)
        creator = asyncio.create_task(gate.call("same", factory))
        current_claim_lease.reset(a)
        current_lease.reset(b)
        waiter = None
        try:
            await wait_until(lambda: bool(gate._inflight))
            waiter = asyncio.create_task(gate.call("same", factory))
            await wait_until(lambda: gate.shared_hits == 1)
            creator.cancel()
            with pytest.raises(asyncio.CancelledError):
                await creator
            owner.finished = request.finished = True
            owner.release_if_done()
            request.release_if_done()
            assert owner.pending == request.pending == 1
            assert semaphore.locked() and guard.active == 1
            assert not worker_started.is_set()
            gate_sem.release()
            await asyncio.wait_for(worker_started.wait(), 2)
            assert owner.pending == request.pending == 2  # shared task + synchronous future
            release.set()
            assert await asyncio.wait_for(waiter, 2) == ["shared-result"]
            await wait_until(lambda: owner.released and guard.active == 0)
            assert calls == [1] and owner.pending == request.pending == 0
            owner.release_if_done()
            assert not semaphore.locked()
        finally:
            release.set()
            for task in (creator, waiter):
                if task is not None and not task.done():
                    task.cancel()
            await asyncio.gather(*(t for t in (creator, waiter) if t is not None), return_exceptions=True)
            await loop.shutdown_default_executor()

    asyncio.run(run())


def test_shared_task_retains_slot_between_two_sync_calls():
    async def run():
        loop = asyncio.get_running_loop()
        loop.set_default_executor(TrackingExecutor(max_workers=8))
        semaphore = asyncio.BoundedSemaphore(1)
        await semaphore.acquire()
        owner = ClaimLease(semaphore, loop)
        gate = UpstreamGate(1)
        between = asyncio.Event()
        resume = asyncio.Event()

        async def factory():
            await asyncio.to_thread(lambda: None)
            between.set()
            await resume.wait()
            return await asyncio.to_thread(lambda: "done")

        token = current_claim_lease.set(owner)
        creator = asyncio.create_task(gate.call("same", factory))
        current_claim_lease.reset(token)
        waiter = None
        try:
            await asyncio.wait_for(between.wait(), 2)
            waiter = asyncio.create_task(gate.call("same", factory))
            await wait_until(lambda: gate.shared_hits == 1)
            creator.cancel()
            with pytest.raises(asyncio.CancelledError):
                await creator
            owner.finished = True
            owner.release_if_done()
            await wait_until(lambda: owner.pending == 1)
            assert semaphore.locked() and not owner.released
            resume.set()
            assert await asyncio.wait_for(waiter, 2) == "done"
            await wait_until(lambda: owner.released)
            owner.release_if_done()
            assert not semaphore.locked()
        finally:
            resume.set()
            for task in (creator, waiter):
                if task is not None and not task.done():
                    task.cancel()
            await asyncio.gather(*(t for t in (creator, waiter) if t is not None), return_exceptions=True)
            await loop.shutdown_default_executor()

    asyncio.run(run())


def test_pipeline_reuses_slot_when_timed_out_worker_really_finishes(fake, monkeypatch):
    from app import pipeline
    from app.pipeline import PipelineConfig, run_pipeline

    async def run():
        loop = asyncio.get_running_loop()
        loop.set_default_executor(TrackingExecutor(max_workers=8))
        semaphore_instances = []
        original_lease = pipeline.ClaimLease

        def lease_factory(semaphore, owner_loop):
            lease = original_lease(semaphore, owner_loop)
            semaphore_instances.append(lease)
            return lease

        monkeypatch.setattr(pipeline, "ClaimLease", lease_factory)
        timed_out = asyncio.Event()
        original_process = pipeline._process_claim

        async def process(claim, **kwargs):
            result = await original_process(claim, **kwargs)
            if result.get("error_code") == "CLAIM_TIMEOUT":
                timed_out.set()
            return result

        monkeypatch.setattr(pipeline, "_process_claim", process)
        release = threading.Event()
        started = []

        async def extract(text):
            return NS(claims=[NS(id=f"c{i}", text=str(i), is_verifiable=True) for i in range(2)])

        def work(text):
            started.append(text)
            if text == "0" and not release.wait(5):
                raise AssertionError("Unreleased pipeline worker")
            return []

        async def retrieve(text):
            return await asyncio.to_thread(work, text)

        task = asyncio.create_task(run_pipeline(
            "synthetic", extract=extract, retrieve=retrieve, verify=None,
            cfg=PipelineConfig(claim_concurrency=1, claim_timeout=0.1, total_timeout=2)))
        try:
            await asyncio.wait_for(timed_out.wait(), 1)
            assert started == ["0"] and len(semaphore_instances) == 1
            assert semaphore_instances[0].finished and not semaphore_instances[0].released
            release.set()
            result = await asyncio.wait_for(task, 1)
            assert [r["status"] for r in result["results"]] == ["timeout", "ok"]
            assert started == ["0", "1"]
            await wait_until(lambda: all(lease.released for lease in semaphore_instances))
            assert len(semaphore_instances) == 2
            semaphore = semaphore_instances[0].semaphore
            assert semaphore._value == 1
            for lease in semaphore_instances:
                lease.release_if_done()
            assert semaphore._value == 1
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await loop.shutdown_default_executor()

    asyncio.run(run())
