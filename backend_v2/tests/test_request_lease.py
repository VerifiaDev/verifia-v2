"""Offline request admission ownership and simultaneous completion regressions."""
import asyncio
import threading

import pytest

from app.resources import ClaimLease, Lease, TrackingExecutor, current_claim_lease, current_lease
from app.security import Guard
from test_executor_diagnosis import wait_until


def active_guard(count=1):
    guard = Guard()
    guard.active = count
    return guard


class ThreadCheckedGuard(Guard):
    def __init__(self):
        self.writes = []
        super().__init__()

    def __setattr__(self, name, value):
        if name in ("active", "_active") and "writes" in self.__dict__:
            self.writes.append((name, value, threading.get_ident()))
        super().__setattr__(name, value)


def test_simultaneous_cancelled_workers_release_admission_on_owner_loop():
    async def run():
        loop = asyncio.get_running_loop()
        owner_thread = threading.get_ident()
        loop.set_default_executor(TrackingExecutor(max_workers=8))
        guard = ThreadCheckedGuard()
        guard.active = 2
        release = threading.Event()
        finish_together = threading.Barrier(2)
        started = [asyncio.Event(), asyncio.Event()]
        leases, claims, tasks = [], [], []

        def worker(index):
            loop.call_soon_threadsafe(started[index].set)
            if not release.wait(5):
                raise AssertionError("Worker barrier was not released")
            finish_together.wait(timeout=5)
            return "done"

        try:
            for index in range(2):
                semaphore = asyncio.BoundedSemaphore(1)
                await semaphore.acquire()
                request = Lease(guard)
                claim = ClaimLease(semaphore, loop)
                leases.append(request)
                claims.append(claim)
                a = current_lease.set(request)
                b = current_claim_lease.set(claim)
                tasks.append(asyncio.create_task(asyncio.to_thread(worker, index)))
                current_claim_lease.reset(b)
                current_lease.reset(a)
            await asyncio.wait_for(asyncio.gather(*(event.wait() for event in started)), 2)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for lease in leases + claims:
                lease.finished = True
                lease.release_if_done()
            assert guard.active == 2
            assert all(not lease.released and lease.pending == 1 for lease in leases + claims)
            release.set()
            await wait_until(lambda: guard.active == 0 and all(claim.released for claim in claims))
            assert all(lease.pending == 0 and lease.released for lease in leases + claims)
            for lease in leases + claims:
                lease.release_if_done()
            assert guard.active == 0
            assert all(claim.semaphore._value == 1 for claim in claims)
            assert all(thread == owner_thread for _, _, thread in guard.writes), guard.writes
        finally:
            release.set()
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await loop.shutdown_default_executor()

    asyncio.run(run())


def test_deferred_release_and_new_admission_share_one_capacity_account():
    async def run():
        guard = ThreadCheckedGuard()
        owner = threading.get_ident()
        assert guard.try_acquire() and guard.try_acquire()
        assert not guard.try_acquire()
        token = object()
        # A completed request makes capacity visible before its callback runs.
        guard.queue_release(token)
        assert guard.active == 1
        assert guard.try_acquire()
        assert guard.active == 2
        # The late or repeated callback must not consume a new request's slot.
        guard.release(token)
        guard.release(token)
        assert guard.active == 2 and not guard.try_acquire()
        for _ in range(2):
            lease = Lease(guard)
            lease.finished = True
            lease.release_if_done()
            lease.release_if_done()
        assert guard.active == 0
        assert all(thread == owner for _, _, thread in guard.writes)

    asyncio.run(run())


@pytest.mark.parametrize("close_before_completion", [False, True])
def test_shutdown_receipts_preserve_capacity_without_owner_callback(close_before_completion):
    loop = asyncio.new_event_loop()
    executor = TrackingExecutor(max_workers=8)
    guard = ThreadCheckedGuard()
    release = threading.Event()
    done = threading.Barrier(3)
    leases = []

    def worker():
        if not release.wait(5):
            raise AssertionError("Worker barrier was not released")
        return "done"

    async def setup():
        futures = []
        for _ in range(2):
            assert guard.try_acquire()
            lease = Lease(guard)
            leases.append(lease)
            token = current_lease.set(lease)
            try:
                future = executor.submit(worker)
            finally:
                current_lease.reset(token)
            future.add_done_callback(lambda _: done.wait(timeout=5))
            lease.finished = True
            lease.release_if_done()
            futures.append(future)
        return futures

    try:
        futures = loop.run_until_complete(setup())
        assert guard.active == 2
        if close_before_completion:
            loop.close()
        release.set()
        done.wait(timeout=5)
        if not loop.is_closed():
            # Deliberately discard the accepted callbacks without executing them.
            loop.close()
        assert [future.result(timeout=1) for future in futures] == ["done", "done"]
        assert guard.active == 0
        assert all(lease.released and lease.pending == 0 for lease in leases)
        assert all(thread == threading.get_ident() for _, _, thread in guard.writes)

        async def recover():
            # The same guard may be reused by a later test/server loop. Old
            # receipts cannot reduce its newly acquired reservations twice.
            assert guard.try_acquire() and guard.try_acquire()
            assert guard.active == 2 and not guard.try_acquire()
            for old in leases:
                old.release_if_done()
                guard.release(old._release_token)
            assert guard.active == 2
            for _ in range(2):
                lease = Lease(guard)
                lease.finished = True
                lease.release_if_done()
            assert guard.active == 0

        asyncio.run(recover())
    finally:
        release.set()
        executor.shutdown(wait=True)
        if not loop.is_closed():
            loop.close()
