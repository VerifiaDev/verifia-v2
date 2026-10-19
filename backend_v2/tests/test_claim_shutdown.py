"""Offline shutdown and cancellation boundary checks. Failures are not xfailed."""
import asyncio
import threading
from types import SimpleNamespace as NS

import pytest

from app.limits import UpstreamGate
from app.resources import ClaimLease, Lease, TrackingExecutor, current_claim_lease, current_lease
from test_executor_diagnosis import wait_until


@pytest.mark.parametrize("shutdown", ["closed_before_completion", "queued_callback_then_close", "graceful_drain"])
def test_worker_completion_at_loop_shutdown(shutdown):
    loop = asyncio.new_event_loop()
    executor = TrackingExecutor(max_workers=8)
    release = threading.Event()
    callback_finished = threading.Event()
    started = threading.Event()

    def worker():
        started.set()
        if not release.wait(5):
            raise AssertionError("Worker barrier was not released")
        return "done"

    async def setup():
        semaphore = asyncio.BoundedSemaphore(1)
        await semaphore.acquire()
        claim = ClaimLease(semaphore, loop)
        request = Lease(NS(active=1))
        a = current_claim_lease.set(claim)
        b = current_lease.set(request)
        try:
            future = executor.submit(worker)
        finally:
            current_claim_lease.reset(a)
            current_lease.reset(b)
        future.add_done_callback(lambda _: callback_finished.set())
        claim.finished = request.finished = True
        claim.release_if_done()
        request.release_if_done()
        return semaphore, claim, request, future

    try:
        semaphore, claim, request, future = loop.run_until_complete(setup())
        assert started.wait(2)
        assert claim.pending == request.pending == 1
        assert not claim.released and request.guard.active == 1
        if shutdown == "closed_before_completion":
            loop.close()
            release.set()
            assert callback_finished.wait(2)
        elif shutdown == "queued_callback_then_close":
            # A real completion callback is accepted by a stopped, still-open loop.
            # Closing now discards its ready queue; no monkeypatch changes production logic.
            release.set()
            assert callback_finished.wait(2)
            assert not loop.is_closed()
            assert claim.pending == request.pending == 0
            loop.close()
        else:
            # Run queued completion callbacks using a live loop before closing it.
            release.set()
            assert callback_finished.wait(2)
            async def flush():
                pass
            loop.run_until_complete(flush())
            assert semaphore._value == 1
            loop.close()
        assert future.result(timeout=1) == "done"
        assert claim.pending == request.pending == 0, "Completion bookkeeping was lost during loop shutdown"
        assert claim.released and request.released and request.guard.active == 0
        claim.release_if_done()
        request.release_if_done()
        assert request.guard.active == 0
    finally:
        release.set()
        executor.shutdown(wait=True)
        if not loop.is_closed():
            loop.close()


@pytest.mark.parametrize("order", ["cancel_before_completion", "completion_races_cancel"])
def test_cancel_and_real_future_completion_release_exactly_once(order):
    async def run():
        loop = asyncio.get_running_loop()
        executor = TrackingExecutor(max_workers=8)
        loop.set_default_executor(executor)
        errors = []
        loop.set_exception_handler(lambda _, context: errors.append(context))
        for _ in range(12):
            semaphore = asyncio.BoundedSemaphore(1)
            await semaphore.acquire()
            claim = ClaimLease(semaphore, loop)
            request = Lease(NS(active=1))
            release = threading.Event()
            started = asyncio.Event()

            def worker():
                loop.call_soon_threadsafe(started.set)
                if not release.wait(5):
                    raise AssertionError("Worker barrier was not released")
                return "done"

            async def operation():
                a = current_claim_lease.set(claim)
                b = current_lease.set(request)
                try:
                    return await asyncio.to_thread(worker)
                finally:
                    claim.finished = request.finished = True
                    claim.release_if_done()
                    request.release_if_done()
                    current_claim_lease.reset(a)
                    current_lease.reset(b)

            task = asyncio.create_task(operation())
            try:
                await asyncio.wait_for(started.wait(), 2)
                if order == "cancel_before_completion":
                    task.cancel()
                    release.set()
                else:
                    # Both events are triggered in one loop turn. Either task outcome
                    # is valid; ownership counts and exactly-once release are invariant.
                    release.set()
                    loop.call_soon(task.cancel)
                result = (await asyncio.gather(task, return_exceptions=True))[0]
                assert result == "done" or isinstance(result, asyncio.CancelledError)
                await wait_until(lambda: claim.released and request.released)
                assert claim.pending == request.pending == 0
                assert request.guard.active == 0 and semaphore._value == 1
                for _ in range(3):
                    claim.release_if_done()
                    request.release_if_done()
                assert semaphore._value == 1 and request.guard.active == 0
                await asyncio.wait_for(semaphore.acquire(), 1)
                assert semaphore.locked()
            finally:
                release.set()
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        await loop.shutdown_default_executor()
        assert errors == [], "Unexpected event-loop callback exception"

    asyncio.run(run())


@pytest.mark.parametrize("state", ["queued", "running"])
def test_all_shared_waiters_cancel_without_losing_owner(state):
    async def run():
        loop = asyncio.get_running_loop()
        loop.set_default_executor(TrackingExecutor(max_workers=8))
        semaphore = asyncio.BoundedSemaphore(1)
        await semaphore.acquire()
        claim = ClaimLease(semaphore, loop)
        request = Lease(NS(active=1))
        gate = UpstreamGate(1)
        gate_sem = gate._semaphore()
        if state == "queued":
            await gate_sem.acquire()
        release = threading.Event()
        started = asyncio.Event()
        calls = []

        def worker():
            calls.append(1)
            loop.call_soon_threadsafe(started.set)
            if not release.wait(5):
                raise AssertionError("Shared barrier was not released")
            return "shared"

        async def factory():
            return await asyncio.to_thread(worker)

        a = current_claim_lease.set(claim)
        b = current_lease.set(request)
        creator = asyncio.create_task(gate.call("same", factory))
        current_claim_lease.reset(a)
        current_lease.reset(b)
        waiter = None
        try:
            await wait_until(lambda: bool(gate._inflight))
            shared = gate._inflight["same"].task
            waiter = asyncio.create_task(gate.call("same", factory))
            await wait_until(lambda: gate.shared_hits == 1)
            if state == "running":
                await asyncio.wait_for(started.wait(), 2)
            creator.cancel()
            waiter.cancel()
            results = await asyncio.gather(creator, waiter, return_exceptions=True)
            assert all(isinstance(r, asyncio.CancelledError) for r in results)
            await asyncio.gather(shared, return_exceptions=True)
            claim.finished = request.finished = True
            claim.release_if_done()
            request.release_if_done()
            assert not gate._inflight
            if state == "running":
                assert claim.pending == request.pending == 1
                assert semaphore.locked() and request.guard.active == 1
            else:
                assert not started.is_set() and calls == []
            release.set()
            await wait_until(lambda: claim.released and request.released)
            assert claim.pending == request.pending == 0
            assert request.guard.active == 0 and semaphore._value == 1
            claim.release_if_done()
            assert semaphore._value == 1
        finally:
            release.set()
            for task in (creator, waiter):
                if task is not None and not task.done():
                    task.cancel()
            await asyncio.gather(*(t for t in (creator, waiter) if t is not None), return_exceptions=True)
            if state == "queued":
                gate_sem.release()
            await loop.shutdown_default_executor()

    asyncio.run(run())


def test_parallel_future_completions_after_loop_close_balance_all_owners():
    loop = asyncio.new_event_loop()
    executor = TrackingExecutor(max_workers=8)
    release = threading.Event()
    started = threading.Barrier(9)
    callbacks_done = threading.Barrier(9)

    def worker():
        started.wait(timeout=5)
        if not release.wait(5):
            raise AssertionError("Worker barrier was not released")
        return "done"

    async def setup():
        semaphore = asyncio.BoundedSemaphore(1)
        await semaphore.acquire()
        claim = ClaimLease(semaphore, loop)
        request = Lease(NS(active=1))
        a = current_claim_lease.set(claim)
        b = current_lease.set(request)
        try:
            futures = [executor.submit(worker) for _ in range(8)]
        finally:
            current_claim_lease.reset(a)
            current_lease.reset(b)
        for future in futures:
            future.add_done_callback(lambda _: callbacks_done.wait(timeout=5))
        claim.finished = request.finished = True
        return claim, request, futures

    try:
        claim, request, futures = loop.run_until_complete(setup())
        started.wait(timeout=5)
        assert claim.pending == request.pending == 8
        loop.close()
        release.set()
        callbacks_done.wait(timeout=5)
        assert [future.result(timeout=1) for future in futures] == ["done"] * 8
        assert claim.pending == request.pending == 0
        assert claim.released and request.released and request.guard.active == 0
        for _ in range(3):
            claim.release_if_done()
            request.release_if_done()
        assert request.guard.active == 0
    finally:
        release.set()
        executor.shutdown(wait=True)
        if not loop.is_closed():
            loop.close()


def test_duplicate_completion_receipt_is_idempotent_across_threads():
    from concurrent.futures import ThreadPoolExecutor
    from app.resources import _retain_resources

    async def run():
        loop = asyncio.get_running_loop()
        semaphore = asyncio.BoundedSemaphore(1)
        await semaphore.acquire()
        claim = ClaimLease(semaphore, loop)
        request = Lease(NS(active=1))
        a = current_claim_lease.set(claim)
        b = current_lease.set(request)
        try:
            complete = _retain_resources()
        finally:
            current_claim_lease.reset(a)
            current_lease.reset(b)
        claim.finished = request.finished = True
        barrier = threading.Barrier(3)
        pool = ThreadPoolExecutor(max_workers=2)

        def invoke():
            barrier.wait(timeout=5)
            complete()

        try:
            futures = [pool.submit(invoke) for _ in range(2)]
            barrier.wait(timeout=5)
            await asyncio.gather(*(asyncio.wrap_future(future) for future in futures))
            complete()
            assert claim.pending == request.pending == 0
            assert claim.released and request.released and request.guard.active == 0
            await asyncio.wait_for(semaphore.acquire(), 1)
            assert semaphore.locked()
        finally:
            pool.shutdown(wait=False)

    asyncio.run(run())
