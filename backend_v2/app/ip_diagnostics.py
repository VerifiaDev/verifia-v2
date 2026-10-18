"""Temporary, opt-in IP diagnostics. Never logs request data or secrets."""
import hashlib
import hmac
import ipaddress
import os
import re
import time

from fastapi.responses import JSONResponse


class IPDiagnostics:
    def __init__(self):
        self.token = os.getenv("IP_DIAGNOSTICS_TOKEN", "").encode("utf-8")
        self.key = os.getenv("IP_DIAGNOSTICS_HMAC_KEY", "").encode("utf-8")
        try:
            expires_at = int(os.getenv("IP_DIAGNOSTICS_EXPIRES_AT", "0"))
        except ValueError:
            expires_at = 0
        now = time.time()
        self.enabled = (
            os.getenv("IP_DIAGNOSTICS_ENABLED") == "1"
            and all(re.fullmatch(rb"[0-9a-f]{64}", secret) for secret in (self.token, self.key))
            and not hmac.compare_digest(self.token, self.key)
            and now < expires_at <= now + 3600
        )
        self.expires_at = expires_at
        # Neither a restart nor a backward wall-clock adjustment extends a window.
        self.deadline = time.monotonic() + max(0, expires_at - now)

    def address(self, value):
        try:
            # Scope identifiers are not part of the address used for comparison.
            address = ipaddress.ip_address(value.split("%", 1)[0])
        except ValueError:
            return {"family": "invalid"}
        session = str(self.expires_at).encode("ascii") + b":"
        tag = hmac.new(self.key, session + address.packed, hashlib.sha256).hexdigest()[:32]
        return {"family": f"IPv{address.version}", "tag": tag}

    def response(self, scope, guard):
        if self.enabled and (time.time() >= self.expires_at or time.monotonic() >= self.deadline):
            self.enabled = False
            self.token = self.key = b""
        if not self.enabled:
            return None
        tokens = [v for k, v in scope["headers"] if k == b"x-verifia-ip-diagnostics"]
        if len(tokens) != 1 or not hmac.compare_digest(tokens[0], self.token):
            return None
        forwarded = [v for k, v in scope["headers"] if k == b"x-forwarded-for"]
        # Bound parsing and never return even fragments of malformed input.
        oversized = sum(map(len, forwarded)) > 4096
        too_many = not oversized and sum(value.count(b",") + 1 for value in forwarded) > 16
        bounded = not oversized and not too_many
        hops = [] if not bounded else [
            hop.strip() for value in forwarded
            for hop in value.decode("latin1").split(",")
        ]
        peer = (scope.get("client") or ("unknown", 0))[0]
        return JSONResponse({
            "peer": self.address(peer),
            # Do not pass oversized input to the existing, unbounded selector.
            # Report omission instead of pretending to reproduce its result.
            "selected": self.address(guard.client_ip(scope)) if bounded else None,
            "xff_header_count": len(forwarded),
            "xff_truncated": not bounded,
            "xff_hops": [self.address(hop) for hop in hops[:16]],
        }, headers={"Cache-Control": "no-store", "Vary": "X-Verifia-IP-Diagnostics"})
