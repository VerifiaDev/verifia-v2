# Temporary IP diagnostics

Disabled by default. Only authenticated GET / requests receive diagnostics.
Keep Uvicorn --no-proxy-headers --no-access-log. Quotas, verification and the
existing client-IP selection algorithm are unchanged.

## Create a session

From the repository root run:

    python backend_v2/tools/create_ip_diagnostics_session.py

This silently creates backend_v2/.env.ip-diagnostics (git ignored) using two
independent secrets.token_hex(32) calls and an absolute Unix expiry 900 seconds
ahead. It refuses overwrites. POSIX mode is 0600; Windows inherits the directory
ACL, so use a private workspace. No Render settings are changed.
The file is not automatically loaded and does not activate diagnostics.
Do not print or share its contents. Generate fresh secrets for each new session.

Securely load these variables into the backend environment and restart before
expiry:

    IP_DIAGNOSTICS_ENABLED=1
    IP_DIAGNOSTICS_TOKEN=<generated 64-character hex token>
    IP_DIAGNOSTICS_HMAC_KEY=<independent generated 64-character hex key>
    IP_DIAGNOSTICS_EXPIRES_AT=<generated absolute Unix timestamp>

For local use, launch Uvicorn from backend_v2 with --env-file .env.ip-diagnostics
--workers 1 --no-proxy-headers --no-access-log. The ordinary .env loader does not
load the session file. Old IP_DIAGNOSTICS_TTL_SECONDS configuration is ignored.

Expiry must be in the future and at most one hour away at startup. Wall-clock
and monotonic deadlines are checked for every diagnostic request. On detected
expiry the object disables itself and releases its secret references. Restart
or redeploy with the same configuration cannot renew an expired timestamp.
Correct system time is required, especially across restarts. Environment changes
alone do not reconfigure an already running process.

Validation checks 256-bit hex representation and unequal secrets; it cannot prove
randomness of manually supplied values. Use the generator. HMAC input includes
absolute expiry to separate sessions with different expiries. Share the same
session configuration across instances for comparison.

## Request and interpret

Send GET / directly to the HTTPS backend with X-Verifia-IP-Diagnostics containing
the token. Use a client with header logging and persistent history disabled.
Never put secrets in URLs. Diagnostic requests receive a server-generated request
ID; incoming X-Request-ID is ignored to prevent reflection of copied secrets.
Other requests retain existing request-ID behavior. Responses have no-store and
contain no raw IP/XFF or secrets.

peer and selected contain address families and 128-bit HMAC tags. Ordered
xff_hops contain tags or family: invalid. XFF is bounded to 4096 bytes and 16
entries across all occurrences before calling the existing IP selector. If either
limit is exceeded, xff_truncated is true, xff_hops is empty and selected is null.
The selector is not invoked with oversized input. Within bounds, its existing
handling of duplicate XFF fields is retained.

Compare repeated requests from home internet and mobile data, without XFF and
then with synthetic X-Forwarded-For: 192.0.2.123. Equal peer tags mean equal
connection IPs within the session. Different peer tags may be different proxies.
XFF values changing by network are candidates, not verified client identities.
Retained synthetic entries demonstrate client-controlled content. With an empty
trust list, bounded requests must have equal selected and peer tags.
Never derive a CIDR from one IP or set TRUSTED_PROXY_CIDRS without confirmation
of platform ingress ranges and header sanitation behavior.

## Disable and remove

Set IP_DIAGNOSTICS_ENABLED=0, remove secrets and restart all instances. Delete
the local session file when finished. Expiry independently stops responses.
Python does not guarantee secure memory erasure. External proxy, APM and HTTP
client logging policies require separate review. Existing request-ID reflection
outside diagnostic requests is unchanged; never copy secrets into that field.

For full removal delete app/ip_diagnostics.py, its import/instance/root branch
in app/main.py, the diagnostic-request block in app/observability.py (restore
rid = accept_request_id(incoming)), the generator, tests, env entries and this
document. Restore the root handler's original signature if desired.
