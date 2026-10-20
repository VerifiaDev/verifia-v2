"""Admission leases stay occupied until abandoned synchronous calls finish."""
import asyncio
import contextvars
import os
import threading
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

current_lease = contextvars.ContextVar("verification_lease", default=None)
current_claim_lease = contextvars.ContextVar("claim_lease", default=None)


def _retain_resources():
    """Return one idempotent completion receipt for the current resource owners."""
    leases = tuple(x for x in (current_lease.get(), current_claim_lease.get()) if x is not None)
    retained = []
    try:
        for lease in leases:
            lease.add_work()
            retained.append(lease)
    except BaseException:
        for lease in retained:
            lease.complete_work()
        raise
    completed = False
    lock = threading.Lock()

    def complete(_=None):
        nonlocal completed
        with lock:
            if completed:
                return
            completed = True
        for lease in leases:
            lease.complete_work()

    return complete


def retain_task_resources(task):
    """Keep shared-task ownership through queue waits and synchronous calls."""
    task.add_done_callback(_retain_resources())


class TrackingExecutor(ThreadPoolExecutor):
    """Account on actual future completion, even if its event loop never runs again."""

    def submit(self, function, /, *args, **kwargs):
        complete = _retain_resources()
        try:
            future = super().submit(function, *args, **kwargs)
        except BaseException:
            complete()
            raise
        future.add_done_callback(complete)
        return future


class _WorkOwner:
    def add_work(self):
        with self._lock:
            if self.released:
                raise RuntimeError("Resource owner already released")
            self.pending += 1

    def complete_work(self):
        with self._lock:
            if self.pending <= 0:
                raise RuntimeError("Unbalanced resource completion")
            self.pending -= 1
        self.release_if_done()


def positive_env(name, default):
    try:
        value = int(os.getenv(name, str(default)))
        return value if value > 0 else default
    except ValueError:
        return default


def memory_mb():
    """Return current RSS and reported peak in MiB (Windows or Linux).

    The peak includes the current sample: independently read Linux RSS counters
    can disagree, so the OS high-water mark alone can be below observed RSS.
    """
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (name, ctypes.c_size_t)
                for name in ("peak", "rss", "a", "b", "c", "d", "e", "f", "g")
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        get_info = ctypes.WinDLL("psapi").GetProcessMemoryInfo
        get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        get_info.restype = wintypes.BOOL
        if not get_info(
            kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            raise OSError("memory measurement unavailable")
        return counters.rss / 1048576, counters.peak / 1048576
    import resource
    from pathlib import Path

    pages = int(Path("/proc/self/statm").read_text().split()[1])
    rss = pages * os.sysconf("SC_PAGE_SIZE") / 1048576
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    return rss, max(rss, peak)


@dataclass
class Lease(_WorkOwner):
    guard: object
    pending: int = 0
    finished: bool = False
    released: bool = False
    loop: object = field(default_factory=asyncio.get_running_loop, init=False, repr=False, compare=False)
    _release_token: object = field(default_factory=object, init=False, repr=False, compare=False)
    _lock: object = field(default_factory=threading.RLock, init=False, repr=False, compare=False)

    def release_if_done(self):
        with self._lock:
            if not self.finished or self.pending or self.released:
                return
            self.guard.queue_release(self._release_token)
            self.released = True
        # Admission mutation belongs to the owner loop. The guarded receipt is
        # already visible to capacity checks, so losing this callback is safe.
        if self.loop.is_closed():
            return
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is self.loop:
            self.guard.release(self._release_token)
        else:
            try:
                self.loop.call_soon_threadsafe(self.guard.release, self._release_token)
            except RuntimeError:
                pass  # A later admission check can drain the completion receipt.


@dataclass
class ClaimLease(_WorkOwner):
    """Account immediately; wake waiters only on their owning event loop."""
    semaphore: asyncio.Semaphore
    loop: asyncio.AbstractEventLoop
    pending: int = 0
    finished: bool = False
    _released: bool = field(default=False, init=False, repr=False)
    _release_scheduled: bool = field(default=False, init=False, repr=False)
    _lock: object = field(default_factory=threading.RLock, init=False, repr=False, compare=False)

    @property
    def released(self):
        with self._lock:
            # A closed loop has no surviving waiters. Its discarded wakeup does
            # not keep an already-accounted owner alive.
            return self._released or (self._release_scheduled and self.loop.is_closed())

    @released.setter
    def released(self, value):
        with self._lock:
            self._released = value

    def _release_slot(self):
        with self._lock:
            if self._released or self.loop.is_closed():
                return
            self.semaphore.release()
            self._released = True

    def release_if_done(self):
        with self._lock:
            if not self.finished or self.pending or self._released or self._release_scheduled:
                return
            self._release_scheduled = True
        # Pending counters are already final and never depend on this wakeup.
        if self.loop.is_closed():
            return
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is self.loop:
            self._release_slot()
        else:
            try:
                self.loop.call_soon_threadsafe(self._release_slot)
            except RuntimeError:
                pass  # Loop closed between the check and scheduling the wakeup.
