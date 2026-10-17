"""Admission leases stay occupied until abandoned synchronous calls finish."""
import asyncio
import contextvars
import os
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

current_lease = contextvars.ContextVar("verification_lease", default=None)


class TrackingExecutor(ThreadPoolExecutor):
    """Track existing asyncio.to_thread adapters without changing their files."""

    def submit(self, function, /, *args, **kwargs):
        lease = current_lease.get()
        loop = asyncio.get_running_loop()
        if lease:
            lease.pending += 1
        try:
            future = super().submit(function, *args, **kwargs)
        except BaseException:
            if lease:
                lease.pending -= 1
            raise

        def complete(_):
            if lease:
                def release():
                    lease.pending -= 1
                    lease.release_if_done()
                try:
                    loop.call_soon_threadsafe(release)
                except RuntimeError:
                    release()  # loop closed during process shutdown

        future.add_done_callback(complete)
        return future


def positive_env(name, default):
    try:
        value = int(os.getenv(name, str(default)))
        return value if value > 0 else default
    except ValueError:
        return default


def memory_mb():
    """Return current RSS and OS process peak in MiB (Windows or Linux)."""
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
    return (
        pages * os.sysconf("SC_PAGE_SIZE") / 1048576,
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    )


@dataclass
class Lease:
    guard: object
    pending: int = 0
    finished: bool = False
    released: bool = False

    def release_if_done(self):
        if self.finished and not self.pending and not self.released:
            self.released = True
            self.guard.active -= 1
