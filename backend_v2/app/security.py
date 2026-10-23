"""Process-local quotas and HTTP security boundary; no request content logs.

Verification admission order after body checks: LOW_MEMORY, BUSY, RATE_LIMITED.
Unlike quota-first admission, memory/capacity rejections do not spend any quota.
Once admitted and charged, later validation/provider errors or cancellation do
not refund quota. The reservation remains owned until pending sync work finishes.
"""
import ipaddress
import logging
import math
import os
import time
import threading
from collections import OrderedDict

from fastapi.responses import JSONResponse

from .observability import current_request_id
from .resources import Lease, current_lease, memory_mb, positive_env

log = logging.getLogger("verify.security")


def error(code, status, retry=None):
    return JSONResponse(
        {"status": "error", "error": code, "message": "İstek şu anda işlenemiyor."},
        status_code=status,
        headers={"Retry-After": str(retry)} if retry else None,
    )


class Guard:
    def __init__(self):
        self._active_lock = threading.RLock()
        self._active = 0
        self._completed_releases = set()
        self.maximum = positive_env("MAX_ACTIVE_VERIFICATIONS", 2)
        self.memory_limit = positive_env("MAX_RSS_MB", 384)
        self.clients = OrderedDict()
        self.client_limit = positive_env("MAX_TRACKED_CLIENTS", 10000)
        self.limits = [
            (60, positive_env("RATE_LIMIT_PER_MINUTE", 10)),
            (3600, positive_env("HOURLY_QUOTA", 100)),
            (86400, positive_env("DAILY_QUOTA", 500)),
        ]
        self.global_daily = positive_env("GLOBAL_DAILY_QUOTA", 1000)
        self.global_count = (0, 0)
        try:
            self.trusted = [
                ipaddress.ip_network(value.strip())
                for value in os.getenv("TRUSTED_PROXY_CIDRS", "").split(",")
                if value.strip()
            ]
        except ValueError:
            raise ValueError("Invalid trusted proxy configuration") from None

    @property
    def active(self):
        with self._active_lock:
            return self._active - len(self._completed_releases)

    @active.setter
    def active(self, value):
        # Used by isolated test setup; runtime admission uses try_acquire.
        with self._active_lock:
            self._active = value
            self._completed_releases.clear()

    def try_acquire(self):
        with self._active_lock:
            # Drain receipts whose loop callbacks may have been discarded at shutdown.
            self._active -= len(self._completed_releases)
            self._completed_releases.clear()
            if self._active >= self.maximum:
                return False
            self._active += 1
            return True

    def queue_release(self, token):
        # Worker threads only record an idempotent completion receipt. Capacity
        # reads account for it even if the owner loop never runs its callback.
        with self._active_lock:
            if token not in self._completed_releases:
                if self._active <= len(self._completed_releases):
                    raise RuntimeError("Unbalanced admission release")
                self._completed_releases.add(token)

    def release(self, token):
        with self._active_lock:
            if token in self._completed_releases:
                self._completed_releases.remove(token)
                self._active -= 1

    def client_ip(self, scope):
        peer = (scope.get("client") or ("unknown", 0))[0]

        def trusted(value):
            try:
                return any(ipaddress.ip_address(value) in net for net in self.trusted)
            except ValueError:
                return False

        if not trusted(peer):
            return peer
        forwarded = dict(scope["headers"]).get(b"x-forwarded-for", b"")
        for hop in reversed(forwarded.decode("latin1").split(",")):
            hop = hop.strip()
            try:
                ipaddress.ip_address(hop)
            except ValueError:
                return peer
            if not trusted(hop):
                return hop
        return peer

    def quota(self, ip):
        now = time.time()
        while self.clients:
            key, (seen, _) = next(iter(self.clients.items()))
            if now - seen < 86400:
                break
            del self.clients[key]
        if ip not in self.clients and len(self.clients) >= self.client_limit:
            return 60  # fail closed without evicting an existing client's quota
        counters = self.clients.get(ip, (now, {}))[1]
        day = int(now // 86400)
        global_day, global_count = self.global_count
        if global_day != day:
            global_count = 0
        retries = []
        for seconds, limit in self.limits:
            bucket, count = counters.get(seconds, (-1, 0))
            if bucket == int(now // seconds) and count >= limit:
                retries.append(math.ceil(seconds - now % seconds))
        if global_count >= self.global_daily:
            retries.append(math.ceil(86400 - now % 86400))
        if retries:
            return max(retries)
        for seconds, _ in self.limits:
            bucket, count = counters.get(seconds, (-1, 0))
            current = int(now // seconds)
            counters[seconds] = (current, count + 1 if bucket == current else 1)
        self.clients[ip] = (now, counters)
        self.clients.move_to_end(ip)
        self.global_count = (day, global_count + 1)
        return 0


class SecurityMiddleware:
    def __init__(self, app, guard):
        self.app, self.guard = app, guard

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = current_request_id()
        status, started = 500, False

        async def output(message):
            nonlocal status, started
            if message["type"] == "http.response.start":
                started, status = True, message["status"]
            await send(message)

        lease, token = None, None
        rss = peak = 0
        try:
            if scope["method"] == "POST" and scope["path"] in ("/verify", "/verify/stream"):
                headers = dict(scope.get("headers", []))
                try:
                    declared = int(headers.get(b"content-length", b"0"))
                except ValueError:
                    return await error("INVALID_CONTENT_LENGTH", 400)(scope, receive, output)
                if declared < 0:
                    return await error("INVALID_CONTENT_LENGTH", 400)(scope, receive, output)
                if declared > 65536:
                    return await error("BODY_TOO_LARGE", 413)(scope, receive, output)
                body = bytearray()
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > 65536:
                        return await error("BODY_TOO_LARGE", 413)(scope, receive, output)
                    body.extend(chunk)
                    if not message.get("more_body"):
                        break
                original_receive, first = receive, True

                async def replay():
                    nonlocal first
                    if first:
                        first = False
                        return {"type": "http.request", "body": bytes(body), "more_body": False}
                    return await original_receive()

                receive = replay
                try:
                    rss, peak = memory_mb()
                except Exception:
                    return await error("LOW_MEMORY", 503, 30)(scope, receive, output)
                if rss >= self.guard.memory_limit:
                    return await error("LOW_MEMORY", 503, 30)(scope, receive, output)
                if not self.guard.try_acquire():
                    return await error("BUSY", 429, 1)(scope, receive, output)
                lease = Lease(self.guard)
                token = current_lease.set(lease)
                # Admission precedes quota charging: LOW_MEMORY/BUSY never spend
                # a user's budget. Install the lease first so quota rejection or
                # failure releases the reservation through the same finally path.
                retry = self.guard.quota(self.guard.client_ip(scope))
                if retry:
                    return await error("RATE_LIMITED", 429, retry)(scope, receive, output)
            await self.app(scope, receive, output)
        except Exception:
            if started:
                raise
            await error("INTERNAL_ERROR", 500)(scope, receive, output)
        finally:
            if lease:
                lease.finished = True
                lease.release_if_done()
                current_lease.reset(token)
            log.info(
                "request_id=%s status=%d rss_mb=%.1f peak_mb=%.1f active=%d",
                request_id, status, rss, peak, self.guard.active,
            )
