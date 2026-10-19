"""
VERIFY Search/Retrieval Lite
512 MB Render için hafif sürüm.

Kullanım:
    from search_retrieval import search
    raw_sources = search(claim.text, max_sources=5)

Ağır bağımlılıklar YOK:
- sentence-transformers / torch
- CrossEncoder
- Playwright / Chromium
"""

from __future__ import annotations

import json
import threading
import inspect
import math
import time
from contextvars import ContextVar
from copy import deepcopy

import os
import ipaddress
import re
import socket
import unicodedata
from collections import Counter, OrderedDict
from urllib.parse import unquote, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

SURUM = "5.2-lite-512mb"
RETRIEVAL_API_VERSION = "search-v1"

SEARCH_RESULTS_PER_QUERY = int(os.getenv("LITE_RESULTS_PER_QUERY", "5"))
MAX_QUERY_COUNT = int(os.getenv("LITE_QUERY_COUNT", "3"))
PREFILTER_SOURCE_LIMIT = int(os.getenv("LITE_PREFILTER_SOURCE_LIMIT", "10"))
FETCH_SOURCE_LIMIT = int(os.getenv("LITE_FETCH_SOURCE_LIMIT", "8"))
MAX_CHUNKS_PER_SOURCE = int(os.getenv("LITE_MAX_CHUNKS_PER_SOURCE", "10"))


def _positive_env(name, default):
    try:
        value = float(os.getenv(name, str(default)))
        return value if math.isfinite(value) and value > 0 else default
    except (ValueError, TypeError):
        return default


def _cache_positive_int(name, default):
    value = os.getenv(name, str(default)).strip()
    if not value.isascii() or not value.isdecimal() or len(value) > 16:
        return default
    return int(value) or default


class _TavilyQueryCache:
    """Immutable payloads; byte limits exclude Python/key and decode overhead."""
    def __init__(self):
        enabled = os.getenv("LITE_TAVILY_CACHE_ENABLED", "true").strip().lower()
        self.enabled = enabled not in ("false", "0", "no", "off")
        self.ttl = _positive_env("LITE_TAVILY_CACHE_TTL_SECONDS", 60.0)
        self.max_entries = _cache_positive_int("LITE_TAVILY_CACHE_MAX_ENTRIES", 128)
        self.max_bytes = _cache_positive_int("LITE_TAVILY_CACHE_MAX_BYTES", 4 * 1024 * 1024)
        self.max_entry_bytes = _cache_positive_int("LITE_TAVILY_CACHE_MAX_ENTRY_BYTES", 128 * 1024)
        self._items = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()

    @staticmethod
    def key(params):
        params = dict(params)
        params["query"] = re.sub(r"\s+", " ", unicodedata.normalize("NFC", params["query"])).strip()
        return json.dumps(["tavily", 1, params], sort_keys=True, ensure_ascii=False)

    def get(self, key):
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            created, data = item
            age = time.monotonic() - created
            if age >= self.ttl:
                self._bytes -= len(data)
                del self._items[key]
                return None
            self._items.move_to_end(key)
        return json.loads(data), age

    def put(self, key, response):
        if not self.enabled or not _provider_rows(response):
            return
        try:
            data = json.dumps(response, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            return  # Optional caching must not invalidate a usable provider result.
        if len(data) > min(self.max_entry_bytes, self.max_bytes):
            return
        with self._lock:
            _remaining("tavily")
            now = time.monotonic()
            for old in list(self._items):
                if now - self._items[old][0] >= self.ttl:
                    self._bytes -= len(self._items.pop(old)[1])
            if key in self._items:
                self._bytes -= len(self._items.pop(key)[1])
            self._items[key] = (now, data)
            self._bytes += len(data)
            while len(self._items) > self.max_entries or self._bytes > self.max_bytes:
                self._bytes -= len(self._items.popitem(last=False)[1][1])


_tavily_cache = _TavilyQueryCache()


REQUEST_TIMEOUT = _positive_env("LITE_REQUEST_TIMEOUT", 8.0)
CONNECT_TIMEOUT = _positive_env("LITE_CONNECT_TIMEOUT", _positive_env("LITE_REQUEST_TIMEOUT", 3.0))
READ_TIMEOUT = _positive_env("LITE_READ_TIMEOUT", _positive_env("LITE_REQUEST_TIMEOUT", 5.0))
PAGE_BUDGET = _positive_env("LITE_PAGE_BUDGET", 10.0)
TAVILY_TIMEOUT = _positive_env("LITE_TAVILY_TIMEOUT", 5.0)
TOTAL_DEADLINE = _positive_env("LITE_TOTAL_DEADLINE", 20.0)

# Immutable per-context value; workers get distinct context copies.
_total_deadline = ContextVar("lite_total_deadline", default=None)
# Coordinator-owned state. Explicitly cleared from fetch worker contexts.
_partial_state = ContextVar("lite_partial_state", default=None)


class _RetrievalTimeout(TimeoutError):
    pass


class _PageTimeout(TimeoutError):
    pass


# Each adapter invocation owns its Event; copied contexts share only that claim's signal.
_cancellation_event = ContextVar("lite_cancellation_event", default=None)


class _RetrievalCancelled(Exception):
    pass


def _remaining(stage):
    event = _cancellation_event.get()
    if event is not None and event.is_set():
        raise _RetrievalCancelled(stage)
    deadline = _total_deadline.get()
    if deadline is None:
        return float("inf")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _RetrievalTimeout(stage)
    return remaining


def _page_remaining(deadline, stage):
    remaining = min(_remaining(stage), deadline - time.monotonic())
    if remaining <= 0:
        raise _PageTimeout(stage)
    return remaining


class _TavilyCapabilityError(Exception):
    pass


class _MissingTavilyKey(Exception):
    pass


def _provider_defaults():
    return dict(search_provider="tavily", provider_ok=None,
                provider_partial_failure=False, provider_error_kind=None,
                provider_http_status=None, provider_error_message_safe=None,
                tavily_query_count=0, successful_query_count=0,
                failed_query_count=0, skipped_query_count=0, provider_result_count=0,
                cache_enabled=_tavily_cache.enabled, cache_hit_count=0, cache_miss_count=0,
                avoided_provider_call_count=0, cache_max_age_seconds=0.0,
                generated_query_count=0, unique_query_count=0, planned_query_count=0)


def _classify_provider_error(exc):
    # Never inspect error text/body: mapped SDK errors often lose HTTP status.
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status is None:
        status = getattr(exc, "status_code", None)
    if type(status) is not int or not 100 <= status <= 599:
        status = None
    try:
        from tavily import errors
        def is_sdk_error(name):
            cls = getattr(errors, name, None)
            return isinstance(cls, type) and isinstance(exc, cls)
        usage = is_sdk_error("UsageLimitExceededError")
        auth = is_sdk_error("InvalidAPIKeyError") or is_sdk_error("MissingAPIKeyError")
        timeout = is_sdk_error("TimeoutError")
    except ImportError:
        usage = auth = timeout = False
    if status == 429:
        kind = "rate_limited"
    elif status in (401, 403) or auth or isinstance(exc, _MissingTavilyKey):
        kind = "auth_error"
    elif status is not None and status >= 500:
        kind = "service_error"
    elif timeout or isinstance(exc, requests.exceptions.Timeout):
        kind = "timeout"
    elif usage:
        kind = "usage_limited"
    else:
        kind = "provider_error"
    # No reliable quota-specific signal is exposed by the installed keyed SDK.
    messages = {
        "rate_limited": "Tavily rate limit reached",
        "usage_limited": "Tavily usage limit reached",
        "auth_error": "Tavily authentication failed",
        "service_error": "Tavily service unavailable",
        "timeout": "Tavily request timed out",
        "provider_error": "Tavily provider error",
    }
    return kind, status, messages[kind]


def _record_provider_error(diagnostics, exc):
    diagnostics["provider_ok"] = False
    if diagnostics["provider_error_kind"] is None:
        kind, status, message = _classify_provider_error(exc)
        diagnostics.update(provider_error_kind=kind, provider_http_status=status,
                           provider_error_message_safe=message)


def _provider_rows(response):
    if not isinstance(response, dict) or not isinstance(response.get("results"), list):
        raise ValueError("Invalid provider response")
    rows = response["results"]
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid provider row")
        for key in ("url", "title", "content"):
            if row.get(key) is not None and not isinstance(row[key], str):
                raise ValueError("Invalid provider field")
        if not math.isfinite(float(row.get("score") or 0.0)):
            raise ValueError("Invalid provider score")
    return rows


def _tavily_search(client, _on_start=None, **kwargs):
    _remaining("tavily")
    try:
        parameter = inspect.signature(client.search).parameters.get("timeout")
    except (TypeError, ValueError):
        raise _TavilyCapabilityError() from None
    # **kwargs alone is not proof that the SDK implements a network timeout.
    if parameter is None or parameter.kind not in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY,
    ):
        raise _TavilyCapabilityError()
    remaining = _remaining("tavily")
    if _on_start is not None:
        _on_start()
    return client.search(timeout=min(TAVILY_TIMEOUT, remaining), **kwargs)


MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MIN_FETCHED_TEXT_CHARS = int(os.getenv("LITE_MIN_FETCHED_TEXT_CHARS", "350"))
MIN_SNIPPET_CHARS = int(os.getenv("LITE_MIN_SNIPPET_CHARS", "60"))
CHUNK_TARGET_WORDS = int(os.getenv("LITE_CHUNK_TARGET_WORDS", "90"))
CHUNK_MAX_WORDS = int(os.getenv("LITE_CHUNK_MAX_WORDS", "135"))

LEXICAL_WEIGHT = 0.62
SEARCH_WEIGHT = 0.23
STRUCTURAL_WEIGHT = 0.15

MMR_RELEVANCE_WEIGHT = 0.84
MMR_REDUNDANCY_WEIGHT = 0.16
SAME_DOMAIN_PENALTY = 0.10

STOP_WORDS = {
    "ve", "veya", "ile", "bir", "bu", "şu", "o", "da", "de",
    "mi", "mı", "mu", "mü", "için", "olan", "olarak", "ise",
    "ki", "hem", "çok", "daha", "gibi", "göre", "sonra",
    "önce", "tarafından",

    "the", "a", "an", "and", "or", "of", "to", "in", "on",
    "for", "by", "with", "from", "as", "is", "are", "was",
    "were", "be", "been", "that", "this", "it", "at",
}

SOCIAL_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "youtu.be",
}

_tavily_client = None


# ==========================================================
# TEXT HELPERS
# ==========================================================

def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")

    text = "".join(
        char
        for char in text
        if unicodedata.category(char) != "Mn"
    )

    text = text.casefold()

    text = re.sub(
        r"[^\w%+.,-]+",
        " ",
        text,
        flags=re.UNICODE,
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def _tokens(text: str) -> list[str]:
    raw = re.findall(
        r"\b[\w%+.,-]{2,}\b",
        _normalize(text),
        flags=re.UNICODE,
    )

    return [
        token
        for token in raw
        if token not in STOP_WORDS
    ]


def _token_set(text: str) -> set[str]:
    return set(_tokens(text))


def _unique(values) -> list[str]:
    result = []
    seen = set()

    for value in values:
        value = re.sub(
            r"\s+",
            " ",
            str(value or ""),
        ).strip()

        key = _normalize(value)

        if value and key and key not in seen:
            seen.add(key)
            result.append(value)

    return result


def _coverage(
    claim: str,
    text: str,
) -> float:

    claim_tokens = _token_set(claim)
    text_tokens = _token_set(text)

    if not claim_tokens:
        return 0.0

    return (
        len(claim_tokens & text_tokens)
        / len(claim_tokens)
    )


def _jaccard(
    a: str,
    b: str,
) -> float:

    a_tokens = _token_set(a)
    b_tokens = _token_set(b)

    if not a_tokens or not b_tokens:
        return 0.0

    return (
        len(a_tokens & b_tokens)
        / len(a_tokens | b_tokens)
    )


def _lexical(
    claim: str,
    text: str,
) -> float:

    return (
        0.72 * _coverage(claim, text)
        + 0.28 * _jaccard(claim, text)
    )


def _years(text: str) -> set[str]:
    return set(
        re.findall(
            r"\b(?:19|20)\d{2}\b",
            text or "",
        )
    )


def _numbers(text: str) -> set[str]:
    return set(
        re.findall(
            r"(?<!\w)[+-]?\d+(?:[.,]\d+)?\s*%?",
            text or "",
        )
    )


def _structural(
    claim: str,
    evidence: str,
) -> float:

    score = 0.0
    weight = 0.0

    claim_years = _years(claim)

    if claim_years:
        weight += 0.50

        if claim_years & _years(evidence):
            score += 0.50

    if _numbers(claim):
        weight += 0.25

        if _numbers(evidence):
            score += 0.25

    claim_tokens = list(
        dict.fromkeys(
            _tokens(claim)
        )
    )[:8]

    if claim_tokens:
        weight += 0.25

        evidence_tokens = _token_set(
            evidence
        )

        hits = sum(
            1
            for token in claim_tokens
            if token in evidence_tokens
        )

        score += (
            0.25
            * hits
            / len(claim_tokens)
        )

    if weight == 0:
        return _coverage(
            claim,
            evidence,
        )

    return max(
        0.0,
        min(
            1.0,
            score / weight,
        ),
    )


# ==========================================================
# URL HELPERS
# ==========================================================

def _domain(url: str) -> str:
    try:
        host = (
            urlparse(url or "")
            .netloc
            .lower()
        )

        if host.startswith("www."):
            host = host[4:]

        return host

    except Exception:
        return ""


def _canonical_url(url: str) -> str:
    try:
        parsed = urlparse(
            (url or "").strip()
        )

        scheme = (
            parsed.scheme
            or "https"
        )

        netloc = parsed.netloc.lower()

        path = re.sub(
            r"/+$",
            "",
            parsed.path or "",
        )

        return urlunparse(
            (
                scheme,
                netloc,
                path,
                "",
                "",
                "",
            )
        )

    except Exception:
        return (
            url or ""
        ).strip()


def _is_social(url: str) -> bool:
    return (
        _domain(url)
        in SOCIAL_DOMAINS
    )


def _is_pdf(url: str) -> bool:
    try:
        return (
            urlparse(url or "")
            .path
            .lower()
            .endswith(".pdf")
        )

    except Exception:
        return False


# ==========================================================
# OPTIONAL CLAIM FRAME
# ==========================================================

def _frame_hints(
    claim_frame,
) -> list[str]:

    if not isinstance(
        claim_frame,
        dict,
    ):
        return []

    hints = []

    def add(value):

        if (
            isinstance(value, str)
            and value.strip()
        ):
            hints.append(
                value.strip()
            )

        elif isinstance(
            value,
            (int, float),
        ):
            hints.append(
                str(value)
            )

        elif isinstance(
            value,
            list,
        ):
            for item in value:
                add(item)

        elif isinstance(
            value,
            dict,
        ):
            for key in (
                "text",
                "name",
                "canonical",
                "value",
                "year",
            ):
                if key in value:
                    add(
                        value[key]
                    )

    for key in (
        "subject",
        "entity",
        "entities",
        "location",
        "locations",
        "year",
        "years",
        "time",
        "predicate",
        "metric",
        "topic",
    ):
        if key in claim_frame:
            add(
                claim_frame[key]
            )

    return _unique(
        hints
    )


# ==========================================================
# QUERY GENERATION
# ==========================================================

def generate_queries(
    claim_text: str,
    claim_frame=None,
) -> list[str]:

    base = re.sub(
        r"\s+",
        " ",
        claim_text or "",
    ).strip().rstrip(".?!")

    if not base:
        return []

    hints = _frame_hints(
        claim_frame
    )

    important_tokens = list(
        dict.fromkeys(
            _tokens(base)
        )
    )[:16]

    short_query = " ".join(
        _unique(
            hints
            + sorted(_years(base))
            + important_tokens
        )
    )

    queries = [
        base,
        short_query,
        f"{base} official source",
    ]

    unique = _unique(queries)
    state = _partial_state.get()
    if state is not None:
        state["diagnostics"].update(generated_query_count=len(queries), unique_query_count=len(unique))
    return unique[:MAX_QUERY_COUNT]


# ==========================================================
# TAVILY
# ==========================================================

def _get_tavily_client():
    global _tavily_client

    if _tavily_client is not None:
        return _tavily_client

    api_key = (
        os.getenv(
            "TAVILY_API_KEY",
            "",
        )
        .strip()
    )

    if not api_key:
        raise _MissingTavilyKey(
            "TAVILY_API_KEY bulunamadı. "
            "Render > Environment bölümüne ekle."
        )

    from tavily import TavilyClient

    _tavily_client = TavilyClient(
        api_key=api_key
    )

    return _tavily_client


def _search_web(
    claim_text: str,
    claim_frame=None,
) -> tuple[list[dict], list[str]]:

    state = _partial_state.get()
    diagnostics = state["diagnostics"] if state is not None else _provider_defaults()
    queries = generate_queries(claim_text, claim_frame)
    diagnostics["planned_query_count"] = len(queries)
    results = []
    seen_urls = set()
    try:
        _remaining("tavily")
        client = _get_tavily_client()
    except (_RetrievalTimeout, _RetrievalCancelled):
        diagnostics["skipped_query_count"] += len(queries)
        raise
    except Exception as exc:
        _record_provider_error(diagnostics, exc)
        diagnostics["skipped_query_count"] += len(queries)
        return results, queries

    for index, query in enumerate(queries):
        started = False
        def on_start():
            nonlocal started
            started = True

        params = dict(query=query, search_depth="basic",
                      max_results=SEARCH_RESULTS_PER_QUERY, include_raw_content=False)
        key = _tavily_cache.key(params)
        cached = None
        try:
            _remaining("tavily")
            if _tavily_cache.enabled:
                cached = _tavily_cache.get(key)
                if cached is None:
                    diagnostics["cache_miss_count"] += 1
            _remaining("tavily")
            if cached is not None:
                response, age = cached
                diagnostics["cache_hit_count"] += 1
                diagnostics["avoided_provider_call_count"] += 1
                diagnostics["cache_max_age_seconds"] = max(diagnostics["cache_max_age_seconds"], age)
            else:
                response = _tavily_search(client, _on_start=on_start, **params)
            rows = _provider_rows(response)
        except (_RetrievalTimeout, _RetrievalCancelled):
            diagnostics["skipped_query_count"] += len(queries) - index
            raise
        except Exception as exc:
            if started:
                diagnostics["tavily_query_count"] += 1
                diagnostics["failed_query_count"] += 1
            else:
                diagnostics["skipped_query_count"] += 1
            _record_provider_error(diagnostics, exc)
            rows = None
        else:
            if started:
                diagnostics["tavily_query_count"] += 1
                diagnostics["successful_query_count"] += 1
                diagnostics["provider_result_count"] += len(rows)
                if diagnostics["provider_ok"] is None:
                    diagnostics["provider_ok"] = True
        diagnostics["provider_partial_failure"] = bool(
            diagnostics["successful_query_count"] and diagnostics["failed_query_count"])
        try:
            _remaining("tavily")
            if rows and started and _tavily_cache.enabled:
                _tavily_cache.put(key, response)
        except (_RetrievalTimeout, _RetrievalCancelled):
            diagnostics["skipped_query_count"] += len(queries) - index - 1
            raise
        if rows is None:
            continue

        for row in rows:

            url = (
                row.get("url")
                or ""
            ).strip()

            if not url:
                continue

            canonical = _canonical_url(
                url
            )

            if canonical in seen_urls:
                continue

            seen_urls.add(
                canonical
            )

            results.append({
                "title": re.sub(
                    r"\s+",
                    " ",
                    row.get(
                        "title",
                        "",
                    )
                    or "",
                ).strip(),

                "url": url,

                "content": re.sub(
                    r"\s+",
                    " ",
                    row.get(
                        "content",
                        "",
                    )
                    or "",
                ).strip(),

                "tavily_score": float(
                    row.get(
                        "score"
                    )
                    or 0.0
                ),

                "published_date": (
                    row.get(
                        "published_date"
                    )
                ),
            })

    return (
        results,
        queries,
    )


# ==========================================================
# PREFILTER
# ==========================================================

def _prefilter(
    claim_text: str,
    rows: list[dict],
) -> list[dict]:

    scored = []

    for row in rows:

        if _is_social(
            row.get(
                "url",
                "",
            )
        ):
            continue

        combined = (
            f"{row.get('title', '')} "
            f"{row.get('content', '')}"
        )

        lexical = _lexical(
            claim_text,
            combined,
        )

        tavily_score = max(
            0.0,
            min(
                1.0,
                float(
                    row.get(
                        "tavily_score"
                    )
                    or 0.0
                ),
            ),
        )

        search_score = (
            0.46 * lexical
            + 0.54 * tavily_score
        )

        item = dict(row)

        item["search_score"] = (
            search_score
        )

        scored.append(
            item
        )

    scored.sort(
        key=lambda item: (
            item["search_score"]
        ),
        reverse=True,
    )

    return scored[
        :PREFILTER_SOURCE_LIMIT
    ]


# ==========================================================
# HTML FETCH
# ==========================================================

def _html_to_text(
    html: str,
) -> str:

    soup = BeautifulSoup(
        html or "",
        "html.parser",
    )

    for tag in soup([
        "script",
        "style",
        "noscript",
        "svg",
        "canvas",
        "form",
        "nav",
        "footer",
        "header",
        "aside",
        "iframe",
    ]):
        tag.decompose()

    root = (
        soup.find("article")
        or soup.find("main")
        or soup.body
        or soup
    )

    return re.sub(
        r"\s+",
        " ",
        root.get_text(
            " ",
            strip=True,
        ),
    ).strip()


def _is_safe_source_url(url: str) -> bool:
    """Allow only HTTPS destinations whose resolved addresses are public."""
    try:
        # Reject characters that URL parsers or HTTP clients may normalize away.
        if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in url):
            return False
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port
        if (
            parsed.scheme != "https"
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or "%" in host  # Includes IPv6 zone IDs and encoded host ambiguities.
            or "\\" in parsed.netloc
            or parsed.netloc.endswith(":")
            or port == 0
        ):
            return False
        host = host.rstrip(".").lower()
        if host == "localhost" or host.endswith(".localhost"):
            return False

        def public_address(value):
            address = ipaddress.ip_address(value)
            if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
                if not public_address(str(address.ipv4_mapped)):
                    return False
            return address.is_global and not (
                address.is_private or address.is_loopback or address.is_link_local
                or address.is_reserved or address.is_unspecified or address.is_multicast
            )

        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            literal = None
        if literal is not None and not public_address(str(literal)):
            return False
        # DNS is cooperative only: getaddrinfo cannot be forcibly stopped here.
        _remaining("dns")
        addresses = socket.getaddrinfo(
            host, port or 443, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM,
        )
        return bool(addresses) and all(
            family in (socket.AF_INET, socket.AF_INET6)
            and public_address(sockaddr[0])
            for family, _, _, _, sockaddr in addresses
        )
    except (_RetrievalTimeout, _RetrievalCancelled):
        raise
    except (ValueError, TypeError, OSError):
        return False


class _SourceSession(requests.Session):
    def resolve_redirects(self, response, request, **kwargs):
        # Session.send prepares Response.next even with allow_redirects=False.
        # Suppress only that preparation, which otherwise consumes redirect bodies.
        if kwargs.get("yield_requests", False):
            return iter(())
        return super().resolve_redirects(response, request, **kwargs)


def _fetch_page(
    url: str,
) -> str:

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 "
            "Chrome/124 Safari/537.36"
        )
    }

    try:
        page_deadline = min(time.monotonic() + PAGE_BUDGET,
                            _total_deadline.get() or float("inf"))
        with _SourceSession() as session:
            session.trust_env = False
            for redirects in range(4):
                _page_remaining(page_deadline, "dns")
                safe = _is_safe_source_url(url)
                remaining = _page_remaining(page_deadline, "dns")
                if not safe:
                    return ""
                # Residual DNS rebinding / TOCTOU risk: requests resolves again
                # when connecting. This preflight does not pin the validated IP.
                remaining = _page_remaining(page_deadline, "fetch")
                with session.get(
                    url, headers=headers, timeout=(min(CONNECT_TIMEOUT, remaining),
                                                  min(READ_TIMEOUT, remaining)),
                    allow_redirects=False, stream=True,
                ) as response:
                    _page_remaining(page_deadline, "fetch")
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("Location")
                        if not location or redirects == 3:
                            return ""
                        url = urljoin(url, location)
                        continue
                    if 300 <= response.status_code < 400:
                        return ""
                    response.raise_for_status()
                    content_type = response.headers.get("Content-Type", "").lower()
                    if "html" not in content_type and "text" not in content_type:
                        return ""
                    length = response.headers.get("Content-Length", "").strip()
                    if re.fullmatch(r"[0-9]+", length):
                        # Compare decimal strings to avoid unbounded integer parsing.
                        length = length.lstrip("0") or "0"
                        limit = str(MAX_RESPONSE_BYTES)
                        if len(length) > len(limit) or (
                            len(length) == len(limit) and length > limit
                        ):
                            return ""
                    body = bytearray()
                    # iter_content yields decompressed bytes, not wire byte counts.
                    _page_remaining(page_deadline, "streaming")
                    chunks = iter(response.iter_content(chunk_size=16 * 1024))
                    while True:
                        _page_remaining(page_deadline, "streaming")
                        try:
                            chunk = next(chunks)
                        except StopIteration:
                            break
                        _page_remaining(page_deadline, "streaming")
                        if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                            return ""
                        body.extend(chunk)
                    _page_remaining(page_deadline, "decode")
                    try:
                        html = body.decode(response.encoding or "utf-8", errors="replace")
                    except LookupError:
                        html = body.decode("utf-8", errors="replace")
                    del body
                    _page_remaining(page_deadline, "html_extraction")
                    text = _html_to_text(html)
                    _page_remaining(page_deadline, "html_extraction")
                    return text
        return ""

    except (_RetrievalTimeout, _RetrievalCancelled):
        raise
    except Exception:
        _remaining("fetch")
        return ""


def _source_text(
    row: dict,
    fetched_text=None,
) -> tuple[str, str]:

    snippet = re.sub(
        r"\s+",
        " ",
        row.get(
            "content",
            "",
        )
        or "",
    ).strip()

    url = row.get(
        "url",
        "",
    )

    if _is_pdf(url):

        if (
            len(snippet)
            >= MIN_SNIPPET_CHARS
        ):
            return (
                snippet,
                "tavily_pdf_snippet",
            )

        return (
            "",
            "none",
        )

    _remaining("fetch")
    fetched = _fetch_page(url) if fetched_text is None else fetched_text

    _remaining("fetch")
    if (
        len(fetched)
        >= MIN_FETCHED_TEXT_CHARS
    ):
        return (
            fetched,
            "requests",
        )

    if (
        len(snippet)
        >= MIN_SNIPPET_CHARS
    ):
        return (
            snippet,
            "tavily_snippet",
        )

    if fetched:
        return (
            fetched,
            "requests_short",
        )

    return (
        "",
        "none",
    )


# ==========================================================
# CHUNKING
# ==========================================================

def _sentences(
    text: str,
) -> list[str]:

    text = re.sub(
        r"\s+",
        " ",
        text or "",
    ).strip()

    if not text:
        return []

    protected = re.sub(
        r"(?<=\d)\.(?=\d)",
        "<DOT>",
        text,
    )

    parts = re.split(
        r"(?<=[.!?])\s+",
        protected,
    )

    return [
        part.replace(
            "<DOT>",
            ".",
        ).strip()

        for part in parts

        if part.strip()
    ]


def _chunk_text(
    text: str,
) -> list[str]:

    sentences = _sentences(
        text
    )

    if not sentences:
        return []

    chunks = []

    current = []
    word_count = 0

    for sentence in sentences:
        _remaining("chunking")

        sentence_words = len(
            sentence.split()
        )

        if (
            current
            and word_count
            + sentence_words
            > CHUNK_MAX_WORDS
        ):
            chunk = " ".join(
                current
            ).strip()

            if len(chunk) >= 60:
                chunks.append(
                    chunk
                )

            current = (
                current[-1:]
            )

            word_count = sum(
                len(item.split())
                for item in current
            )

        current.append(
            sentence
        )

        word_count += (
            sentence_words
        )

        if (
            word_count
            >= CHUNK_TARGET_WORDS
        ):
            chunk = " ".join(
                current
            ).strip()

            if len(chunk) >= 60:
                chunks.append(
                    chunk
                )

            current = (
                current[-1:]
            )

            word_count = sum(
                len(item.split())
                for item in current
            )

    if current:

        chunk = " ".join(
            current
        ).strip()

        if len(chunk) >= 60:
            chunks.append(
                chunk
            )

    return _unique(
        chunks
    )


def _focus(
    claim_text: str,
    chunk: str,
    max_sentences: int = 3,
) -> str:

    sentences = _sentences(
        chunk
    )

    if (
        len(sentences)
        <= max_sentences
    ):
        return chunk.strip()

    best_index = max(
        range(
            len(sentences)
        ),
        key=lambda index: (
            _lexical(
                claim_text,
                sentences[index],
            )
        ),
    )

    indexes = {
        best_index
    }

    if best_index > 0:
        indexes.add(
            best_index - 1
        )

    if (
        best_index + 1
        < len(sentences)
    ):
        indexes.add(
            best_index + 1
        )

    return " ".join(
        sentences[index]
        for index in sorted(
            indexes
        )[:max_sentences]
    ).strip()


# ==========================================================
# CANDIDATES
# ==========================================================

def _intent_normalize(text: str) -> str:
    # Turkish dotless i is not decomposed by NFKD. Keep this normalization
    # local to intent detection so existing lexical ranking stays unchanged.
    return re.sub(r"[\W_]+", " ", _normalize(text).replace("ı", "i")).strip()


_QUESTION_TOKEN = r"(?:soru(?:lar)?|cevap(?:lar)?|cozum(?:ler)?|odev(?:ler)?|questions?|answers?|solutions?|quizzes|quiz|tests?|homework|exercises?)"
_QUESTION_PATH_TOKEN = re.compile(rf"(?:{_QUESTION_TOKEN})+")
# Whole-token category matching also accepts compounds (e.g. questionanswer),
# without matching incidental substrings such as 'contest' or 'testimony'.
def _question_path(url: str) -> bool:
    path = _intent_normalize(unquote(urlparse(url).path))
    return (any(_QUESTION_PATH_TOKEN.fullmatch(token) for token in path.split())
            or bool(re.search(r"\bdogru mu yanlis mi\b", path)))


_INSTRUCTION = re.compile(
    r"\b(?:isaretle|cevapla|yanitla|siniflandir|eslestir|sec|doldur)(?:yin|yiniz|in|iniz|unuz)\b"
    r"|\b(?:boslugu|bosluklari) doldurunuz\b"
    r"|\basagidaki\b.{0,100}\b(?:yaziniz|belirtiniz|bulunuz)\b"
)
# Classification labels require a question particle;
# a discussion of objective/subjective statements alone is not an exercise.
_CLASSIFICATION_QUESTION = re.compile(
    r"\b(?:nesnel|oznel|objective|subjective)\b.{0,35}\b(?:mi|midir|mu|mudur)\b"
    r"|\bhangisi\b.{0,35}\b(?:dogru|yanlis)(?:dur|tur|tir|dir)?\b"
)
_ASSESSMENT_CONTEXT = re.compile(
    r"\b(?:dogru (?:mu |veya |ya da |ve )?yanlis(?: mi)?"
    r"|asagidakilerden hangisi|sorunun cevabi|true or false"
    r"|choose the correct answer|answer the following|fill in the blanks)\b"
)
_TITLE_CONTEXT = re.compile(r"\b(?:hangisi|asagidaki|soru|cevap|cozum|quiz|homework|exercise)\b")


def _exercise_context(text: str) -> bool:
    normalized = _intent_normalize(text)
    return bool(_INSTRUCTION.search(normalized)
                or _CLASSIFICATION_QUESTION.search(normalized)
                or _ASSESSMENT_CONTEXT.search(normalized)
                or re.search(r"\b(?:soru|question)\s*:", text, re.IGNORECASE))


def _evidence_intent(url: str, title: str, focused: str) -> tuple[float, list[str]]:
    """Bounded, stance-neutral context cost; never excludes a candidate.

    Each channel contributes once, so repeated keywords cannot amplify it.
    A question mark alone is weak; explicit exercise instructions are stronger.
    No claim matching or domain reputation is used.
    """
    flags = []
    penalty = 0.0
    if _question_path(url):
        flags.append("question_path")
        penalty += 0.04
    normalized_title = _intent_normalize(title)
    if _exercise_context(title):
        flags.append("exercise_title")
        penalty += 0.10
    elif _TITLE_CONTEXT.search(normalized_title):
        flags.append("question_title")
        penalty += 0.04
    elif title.rstrip().endswith("?"):
        flags.append("question_mark_title")
        penalty += 0.02
    if _exercise_context(focused):
        flags.append("exercise_text")
        penalty += 0.14
    return min(0.25, round(penalty, 4)), flags


def _evidence_quality(intent_flags: list[str]) -> dict:
    """Suitability is independent of relevance score and claim truth.

    Require two distinct channels, including an explicit exercise channel.
    Single-channel signals and combinations of weak cues remain eligible.
    Keep this policy separate so future quality features can contribute here.
    """
    flags = set(intent_flags)
    exercise_channels = flags & {"exercise_title", "exercise_text"}
    strong = bool(exercise_channels) and (
        "question_path" in flags or len(exercise_channels) == 2
    )
    return {
        "evidence_intent_level": "strong_exercise" if strong else "weak_question" if flags else "normal",
        "evidence_eligible": not strong,
    }


def _build_candidates_batch(
    claim_text: str,
    rows: list[dict],
    fetched_text=None,
) -> tuple[list[dict], dict]:

    candidates = []

    requests_count = 0
    snippet_count = 0

    for row in rows[
        :FETCH_SOURCE_LIMIT
    ]:

        _remaining("fetch")
        text, fetch_method = (
            _source_text(row, fetched_text)
        )

        if not text:
            continue

        if fetch_method.startswith(
            "requests"
        ):
            requests_count += 1

        elif fetch_method.startswith(
            "tavily"
        ):
            snippet_count += 1

        _remaining("chunking")
        chunks = _chunk_text(
            text
        )

        if (
            not chunks
            and len(text)
            >= MIN_SNIPPET_CHARS
        ):
            chunks = [
                text
            ]

        _remaining("ranking")
        chunks = sorted(
            chunks,
            key=lambda chunk: (
                _lexical(
                    claim_text,
                    chunk,
                )
            ),
            reverse=True,
        )[:MAX_CHUNKS_PER_SOURCE]

        for chunk in chunks:
            _remaining("ranking")

            focused = _focus(
                claim_text,
                chunk,
            )

            ranking_text = (
                f"{row.get('title', '')}\n"
                f"{focused}"
            )

            lexical = _lexical(
                claim_text,
                ranking_text,
            )

            structural = _structural(
                claim_text,
                focused,
            )

            search_score = max(
                0.0,
                min(
                    1.0,
                    float(
                        row.get(
                            "search_score"
                        )
                        or 0.0
                    ),
                ),
            )

            retrieval_score = (
                LEXICAL_WEIGHT
                * lexical

                + SEARCH_WEIGHT
                * search_score

                + STRUCTURAL_WEIGHT
                * structural
            )

            intent_penalty, intent_flags = _evidence_intent(
                row.get("url") or "", row.get("title") or "", focused,
            )

            candidates.append({
                **_evidence_quality(intent_flags),
                "evidence_intent_penalty": intent_penalty,
                "evidence_intent_flags": intent_flags,
                "text": focused,

                "title": (
                    row.get(
                        "title",
                        "",
                    )
                    or ""
                ),

                "url": (
                    row.get(
                        "url",
                        "",
                    )
                    or ""
                ),

                "domain": _domain(
                    row.get(
                        "url",
                        "",
                    )
                ),

                "published_date": (
                    row.get(
                        "published_date"
                    )
                ),

                "fetch_method": (
                    fetch_method
                ),

                "lexical_score": (
                    lexical
                ),

                "search_score": (
                    search_score
                ),

                "structural_score": (
                    structural
                ),

                "retrieval_score": max(
                    0.0,
                    min(
                        1.0,
                        retrieval_score - intent_penalty,
                    ),
                ),
            })

    candidates.sort(
        key=lambda item: (
            item[
                "retrieval_score"
            ]
        ),
        reverse=True,
    )

    diagnostics = {
        "requests_sources": (
            requests_count
        ),

        "snippet_sources": (
            snippet_count
        ),
    }

    return (
        candidates,
        diagnostics,
    )


def _merge_candidate_pages(pages):
    candidates = []
    diagnostics = {"requests_sources": 0, "snippet_sources": 0}
    # Restore prefilter order; sorting below is stable for equal scores/chunks.
    for index in sorted(pages):
        page_candidates, page_diagnostics = pages[index]
        candidates.extend(page_candidates)
        for key in diagnostics:
            diagnostics[key] += page_diagnostics[key]
    candidates.sort(key=lambda item: item["retrieval_score"], reverse=True)
    return candidates, diagnostics


def _process_ready_page(claim_text, row, index, fetched_text=None, completed_at=None):
    _remaining("fetch")
    deadline = _total_deadline.get()
    if completed_at is not None and deadline is not None and completed_at >= deadline:
        raise _RetrievalTimeout("fetch")
    # A page's chunks/scores enter the pool only after the whole page succeeds.
    page = _build_candidates_batch(claim_text, [row], fetched_text)
    _remaining("ranking")
    state = _partial_state.get()
    if state is not None:
        state["pages"][index] = page
        all_candidates, counts = _merge_candidate_pages(state["pages"])
        state["diagnostics"].update(counts, candidate_count=len(all_candidates))
        # Normal retrieval still includes snippets. Timeout snapshots are stricter.
        eligible = [c for c in all_candidates if c["fetch_method"] in
                    ("requests", "requests_short")]
        if eligible:
            selected = _select_diverse(eligible, state["max_sources"])
            snapshot = deepcopy(_sources_from_selected(selected))
            # Authoritative commit check, after ranking, serialization and copying.
            _remaining("partial_commit")
            state["snapshot"] = snapshot
    return page


def _build_candidates(claim_text, rows):
    pages = {}
    for index, row in enumerate(rows[:FETCH_SOURCE_LIMIT]):
        pages[index] = _process_ready_page(claim_text, row, index)
    return _merge_candidate_pages(pages)


# ==========================================================
# MMR / SOURCE DIVERSITY
# ==========================================================

def _select_diverse(
    candidates: list[dict],
    k: int,
) -> list[dict]:

    if (
        not candidates
        or k <= 0
    ):
        return []

    # Deduplicate before the pool limit so repeated chunks cannot crowd out
    # other pages. Stable sorting keeps the first candidate on score ties.
    pages = {}
    for candidate in sorted(candidates, key=lambda item: item["retrieval_score"], reverse=True):
        _remaining("ranking")
        # Shared by normal output and committed timeout snapshots. Keep all
        # candidates upstream for diagnostics; never fill slots with exercises.
        if not candidate.get("evidence_eligible", True):
            continue
        canonical = _canonical_url(candidate["url"])
        if canonical not in pages:
            pages[canonical] = candidate
    pool = [dict(candidate) for candidate in list(pages.values())[:30]]

    selected = []

    used_domains = Counter()

    while (
        pool
        and len(selected)
        < k
    ):

        _remaining("ranking")
        best_candidate = None
        best_score = -999.0

        for candidate in pool:

            if selected:
                redundancy = max(
                    _jaccard(
                        candidate["text"],
                        chosen["text"],
                    )
                    for chosen
                    in selected
                )

            else:
                redundancy = 0.0

            domain = candidate.get(
                "domain",
                "",
            )

            domain_penalty = (
                SAME_DOMAIN_PENALTY

                if (
                    domain
                    and used_domains[
                        domain
                    ] > 0
                )

                else 0.0
            )

            mmr_score = (
                MMR_RELEVANCE_WEIGHT
                * candidate[
                    "retrieval_score"
                ]

                - MMR_REDUNDANCY_WEIGHT
                * redundancy

                - domain_penalty
            )

            if (
                mmr_score
                > best_score
            ):
                best_score = (
                    mmr_score
                )

                best_candidate = (
                    candidate
                )

        if best_candidate is None:
            break

        best_candidate[
            "mmr_score"
        ] = best_score

        selected.append(
            best_candidate
        )

        domain = (
            best_candidate.get(
                "domain",
                "",
            )
        )

        if domain:
            used_domains[
                domain
            ] += 1

        pool.remove(
            best_candidate
        )

    return selected


# ==========================================================
# PUBLIC API
# ==========================================================

def _sources_from_selected(selected):
    sources = []

    for index, candidate in enumerate(
        selected,
        start=1,
    ):

        _remaining("result_construction")
        sources.append({
            "id": (
                f"source_{index}"
            ),

            "url": (
                candidate[
                    "url"
                ]
            ),

            "text": (
                candidate[
                    "text"
                ]
            ),

            "title": (
                candidate[
                    "title"
                ]
            ),

            "domain": (
                candidate[
                    "domain"
                ]
            ),

            "published_date": (
                candidate[
                    "published_date"
                ]
            ),

            "retrieval_score": round(
                candidate[
                    "retrieval_score"
                ],
                4,
            ),

            "candidate_type": (
                "lite_chunk"
            ),

            "metadata": {
                # Keep ordinary source metadata byte-for-byte compatible.
                **({
                    "evidence_intent_penalty": candidate["evidence_intent_penalty"],
                    "evidence_intent_flags": candidate["evidence_intent_flags"],
                    **_evidence_quality(candidate["evidence_intent_flags"]),
                } if candidate.get("evidence_intent_penalty", 0.0) else {}),
                "retrieval_version": (
                    SURUM
                ),

                "api_version": (
                    RETRIEVAL_API_VERSION
                ),

                "scoring_mode": (
                    "lite_lexical"
                ),

                "lexical_score": round(
                    candidate[
                        "lexical_score"
                    ],
                    4,
                ),

                "search_score": round(
                    candidate[
                        "search_score"
                    ],
                    4,
                ),

                "structural_score": round(
                    candidate[
                        "structural_score"
                    ],
                    4,
                ),

                "mmr_score": round(
                    candidate.get(
                        "mmr_score",
                        0.0,
                    ),
                    4,
                ),

                "fetch_method": (
                    candidate[
                        "fetch_method"
                    ]
                ),
            },
        })

    return sources


def _search_detailed_impl(
    claim_text: str,
    max_sources: int = 5,
    claim_frame=None,
    debug: bool = False,
) -> dict:

    if (
        not isinstance(
            claim_text,
            str,
        )
        or not claim_text.strip()
    ):
        return {
            "version": SURUM,

            "api_version": (
                RETRIEVAL_API_VERSION
            ),

            "claim": claim_text,

            "status": (
                "invalid_claim"
            ),

            "sources": [],

            "diagnostics": {},
        }

    claim_text = re.sub(
        r"\s+",
        " ",
        claim_text,
    ).strip()

    try:
        max_sources = int(
            max_sources
        )

    except (
        TypeError,
        ValueError,
    ):
        max_sources = 5

    max_sources = max(
        1,
        min(
            max_sources,
            10,
        ),
    )

    state = _partial_state.get()
    if state is not None:
        state["max_sources"] = max_sources
    search_rows, queries = (
        _search_web(
            claim_text,
            claim_frame,
        )
    )

    if state is not None:
        state["diagnostics"].update(queries=queries, raw_search_results=len(search_rows))
    _remaining("prefilter")
    prefiltered = _prefilter(
        claim_text,
        search_rows,
    )

    if state is not None:
        state["diagnostics"]["prefiltered_sources"] = len(prefiltered)
    candidates, fetch_diagnostics = (
        _build_candidates(
            claim_text,
            prefiltered,
        )
    )

    _remaining("ranking")
    selected = _select_diverse(
        candidates,
        max_sources,
    )

    _remaining("ranking")
    sources = _sources_from_selected(selected)

    result = {
        "version": SURUM,

        "api_version": (
            RETRIEVAL_API_VERSION
        ),

        "claim": (
            claim_text
        ),

        "status": (
            "evidence_found"
            if sources
            else "not_enough_evidence"
        ),

        "sources": (
            sources
        ),

        "diagnostics": {
            "mode": (
                "LITE"
            ),

            "queries": (
                queries
            ),

            "raw_search_results": len(
                search_rows
            ),

            "prefiltered_sources": len(
                prefiltered
            ),

            "candidate_count": len(
                candidates
            ),

            "selected_sources": len(
                sources
            ),

            **fetch_diagnostics,

            "heavy_features_disabled": {
                "sentence_transformers": True,
                "pytorch": True,
                "cross_encoder": True,
                "playwright": True,
                "chromium": True,
                "local_embeddings": True,
            },

            "truth_decision_in_retrieval": (
                False
            ),
        },
    }

    if debug:

        print(
            "\n"
            "=== VERIFY RETRIEVAL LITE ==="
        )

        print(
            "Claim:",
            claim_text,
        )

        print(
            "Queries:",
            queries,
        )

        print(
            "Search results:",
            len(search_rows),
        )

        print(
            "Candidates:",
            len(candidates),
        )

        print(
            "Selected:",
            len(sources),
        )

        for source in sources:

            print(
                "\n---"
            )

            print(
                source["id"],
                source["title"],
            )

            print(
                source["url"]
            )

            print(
                "score:",
                source[
                    "retrieval_score"
                ],
            )

            print(
                source["text"]
            )

    return result


def _initial_diagnostics():
    return {
        **_provider_defaults(),
        "cancelled": False, "cancellation_stage": None,
        "mode": "LITE", "queries": [], "raw_search_results": 0,
        "prefiltered_sources": 0, "candidate_count": 0, "selected_sources": 0,
        "requests_sources": 0, "snippet_sources": 0,
        "heavy_features_disabled": {
            "sentence_transformers": True, "pytorch": True, "cross_encoder": True,
            "playwright": True, "chromium": True, "local_embeddings": True,
        },
        "truth_decision_in_retrieval": False,
    }


def search_detailed(claim_text: str, max_sources: int = 5, claim_frame=None,
                    debug: bool = False) -> dict:
    started = time.monotonic()
    token = _total_deadline.set(started + TOTAL_DEADLINE)
    state = {"snapshot": [], "pages": {}, "max_sources": 5,
             "diagnostics": _initial_diagnostics()}
    state_token = _partial_state.set(state)
    try:
        _remaining("start")
        result = _search_detailed_impl(claim_text, max_sources, claim_frame, debug)
        _remaining("result_construction")
        result["diagnostics"].update({key: state["diagnostics"][key]
                                      for key in _provider_defaults()})
        if (not result["sources"] and state["diagnostics"]["provider_ok"] is False
                and not state["diagnostics"]["successful_query_count"]):
            result["status"] = "search_provider_error"
        result["diagnostics"].update(cancelled=False, cancellation_stage=None,
                                     timed_out=False, partial_result=False,
                                     timeout_stage=None,
                                     completed_source_count=len(result["sources"]),
                                     elapsed_seconds=time.monotonic() - started)
        return result
    except _RetrievalCancelled as exc:
        diagnostics = dict(state["diagnostics"])
        diagnostics.update(cancelled=True, cancellation_stage=str(exc), timed_out=False,
                           timeout_stage=None, partial_result=False, completed_source_count=0,
                           selected_sources=0, elapsed_seconds=time.monotonic() - started)
        return {"version": SURUM, "api_version": RETRIEVAL_API_VERSION,
                "claim": claim_text, "status": "cancelled", "sources": [], "diagnostics": diagnostics}
    except _RetrievalTimeout as exc:
        sources = state["snapshot"]
        diagnostics = dict(state["diagnostics"])
        diagnostics.update(timed_out=True, partial_result=bool(sources),
                           timeout_stage=str(exc), elapsed_seconds=time.monotonic() - started,
                           completed_source_count=len(sources), selected_sources=len(sources))
        return {
            "version": SURUM, "api_version": RETRIEVAL_API_VERSION,
            "claim": claim_text,
            "status": ("evidence_found" if sources else
                       "search_provider_error" if diagnostics["provider_ok"] is False
                       and not diagnostics["successful_query_count"] else "not_enough_evidence"),
            "sources": sources, "diagnostics": diagnostics,
        }
    finally:
        _partial_state.reset(state_token)
        _total_deadline.reset(token)


def search(
    claim_text: str,
    max_sources: int = 5,
    claim_frame=None,
) -> list[dict]:

    """
    backend/main.py ile uyumlu drop-in fonksiyon.

    Mevcut backend:

        raw_sources = search(
            claim.text,
            max_sources=5
        )

    şeklinde çalışmaya devam eder.
    """

    return search_detailed(
        claim_text=claim_text,
        max_sources=max_sources,
        claim_frame=claim_frame,
        debug=False,
    )["sources"]


# ==========================================================
# SELF TEST
# ==========================================================

def _run_self_tests():

    checks = [
        (
            "Turkish normalization",

            "turkiye"
            in _normalize(
                "Türkiye"
            ),
        ),

        (
            "Query generation",

            len(
                generate_queries(
                    "Orion 2024 yılında "
                    "Atlas pazarında "
                    "yüzde 20 büyüdü."
                )
            )
            >= 2,
        ),

        (
            "Year extraction",

            _years(
                "2024 ve 2023"
            )
            == {
                "2023",
                "2024",
            },
        ),

        (
            "Counter evidence stays relevant",

            _structural(
                (
                    "Orion 2024 yılında "
                    "satışlarını yüzde 20 artırdı."
                ),
                (
                    "Orion'un 2024 satışları "
                    "yüzde 12 arttı."
                ),
            )
            > 0.40,
        ),
    ]

    passed = sum(
        1
        for _, success
        in checks
        if success
    )

    print(
        f"Lite self-tests: "
        f"{passed}/{len(checks)}"
    )

    for name, success in checks:

        print(
            (
                "PASS"
                if success
                else "FAIL"
            ),
            "-",
            name,
        )

    if passed != len(checks):
        raise SystemExit(1)


# ==========================================================
# CLI TEST
# ==========================================================

def main():

    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "VERIFY Search/Retrieval Lite"
        )
    )

    parser.add_argument(
        "claim",
        nargs="*",
    )

    parser.add_argument(
        "--max-sources",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
    )

    args = parser.parse_args()

    if args.self_test:

        _run_self_tests()

        return

    claim = " ".join(
        args.claim
    ).strip()

    if not claim:

        claim = input(
            "Atomic claim: "
        ).strip()

    search_detailed(
        claim_text=claim,
        max_sources=(
            args.max_sources
        ),
        debug=True,
    )


if __name__ == "__main__":
    main()
