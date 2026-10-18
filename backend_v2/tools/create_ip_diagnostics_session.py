"""Create a short diagnostic session in a git-ignored file; never print secrets."""
import os
from pathlib import Path
import secrets
import time


def create_session(path, duration=900):
    if not 0 < duration <= 3600:
        raise ValueError("Invalid diagnostic duration")
    token = secrets.token_hex(32)
    key = secrets.token_hex(32)
    while secrets.compare_digest(token, key):
        key = secrets.token_hex(32)
    content = (
        "IP_DIAGNOSTICS_ENABLED=1\n"
        f"IP_DIAGNOSTICS_TOKEN={token}\n"
        f"IP_DIAGNOSTICS_HMAC_KEY={key}\n"
        f"IP_DIAGNOSTICS_EXPIRES_AT={int(time.time()) + duration}\n"
    )
    # Refuse overwrites. On POSIX restrict permissions at creation; Windows
    # inherits the parent directory's ACL (use a private user workspace).
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as output:
        output.write(content)


if __name__ == "__main__":
    destination = Path(__file__).resolve().parents[1] / ".env.ip-diagnostics"
    create_session(destination)
