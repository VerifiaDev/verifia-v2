"""Offline source-fetch security and integration regression tests."""
import asyncio
import gzip
import io
import os
from copy import deepcopy
from types import SimpleNamespace
import importlib.util
import inspect
import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "retrieval_demo_lite"))
import search_retrieval_lite as mod

PUBLIC = "93.184.216.34"
TEXT = ("Evidence about annual production and reported growth. " * 20)


def answers(*ips):
    return [(socket.AF_INET6 if ":" in ip else socket.AF_INET,
             socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in ips]


def response(status=200, location=None):
    result = MagicMock()
    result.__enter__.return_value = result
    result.status_code = status
    result.headers = {"Content-Type": "text/html"}
    if location is not None:
        result.headers["Location"] = location
    result.encoding = "utf-8"
    result.iter_content.return_value = iter([("<article>" + TEXT + "</article>").encode()])
    return result


def setUpModule():
    # Existing regression fixtures exercise live provider behavior, independently of cache state.
    global _original_cache
    _original_cache = mod._tavily_cache
    mod._tavily_cache = mod._TavilyQueryCache()
    mod._tavily_cache.enabled = False


def tearDownModule():
    mod._tavily_cache = _original_cache


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.dns = patch.object(mod.socket, "getaddrinfo", return_value=answers(PUBLIC)).start()
        self.factory = patch.object(mod, "_SourceSession").start()
        self.session = self.factory.return_value.__enter__.return_value
        self.session.get.side_effect = lambda *a, **k: response()
        self.addCleanup(patch.stopall)

    def test_https_and_proxy_environment(self):
        with patch.dict("os.environ", {"HTTPS_PROXY": "http://localhost:9999"}):
            self.assertEqual(mod._fetch_page("https://public.example/page"), TEXT.strip())
        self.assertIs(self.session.trust_env, False)
        self.assertFalse(self.session.get.call_args.kwargs["allow_redirects"])
        self.assertTrue(self.session.get.call_args.kwargs["stream"])
        self.factory.return_value.__exit__.assert_called_once()

    def test_invalid_urls_never_connect(self):
        for url in ["http://public.example", "ftp://public.example", "//public.example",
                    "https:///missing", "https://user@public.example", "https://u:p@public.example",
                    "https://public.example:bad", "https://public.example:65536",
                    "https://public.example:0", "https://public.example:",
                    "https://[fe80::1%25eth0]", "https://[bad", "https://localHOST.",
                    "https://a.localhost", "https://public.example\n", "https://a\\b"]:
            with self.subTest(url=url):
                self.assertEqual(mod._fetch_page(url), "")
        self.session.get.assert_not_called()

    def test_non_public_literals(self):
        ips = ["127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.1.1", "169.254.169.254",
               "0.0.0.0", "100.64.0.1", "224.0.0.1", "240.0.0.1", "192.0.2.1",
               "::1", "::", "fc00::1", "fe80::1", "ff02::1", "2001:db8::1",
               "::ffff:127.0.0.1", "::ffff:10.0.0.1"]
        for ip in ips:
            with self.subTest(ip=ip):
                host = f"[{ip}]" if ":" in ip else ip
                self.assertEqual(mod._fetch_page(f"https://{host}/"), "")
        self.session.get.assert_not_called()

    def test_all_dns_results_checked(self):
        for ips in [("10.0.0.1",), (PUBLIC, "::1"), (PUBLIC, "192.168.1.1"),
                    ("ff02::1",), ("100.64.0.1",), ()]:
            with self.subTest(ips=ips):
                self.dns.return_value = answers(*ips)
                self.assertEqual(mod._fetch_page("https://public.example"), "")
        self.session.get.assert_not_called()

    def test_public_ipv4_ipv6(self):
        self.dns.return_value = answers(PUBLIC, "2606:4700:4700::1111")
        self.assertTrue(mod._fetch_page("https://public.example"))
        self.assertTrue(mod._fetch_page(f"https://{PUBLIC}"))
        self.assertTrue(mod._fetch_page("https://[2606:4700:4700::1111]"))

    def test_dns_failure_and_alternative_ipv4(self):
        self.dns.side_effect = socket.gaierror("unavailable")
        self.assertEqual(mod._fetch_page("https://public.example"), "")
        self.dns.side_effect = None
        self.dns.return_value = answers("127.0.0.1")
        for host in ["127.1", "2130706433", "0x7f000001", "0177.0.0.1"]:
            self.assertEqual(mod._fetch_page(f"https://{host}"), "")
        self.session.get.assert_not_called()

    def test_redirect_targets_checked(self):
        for target in ["http://public.example", "https://127.0.0.1", "https://localhost",
                       "https://[::1]", "https://u:p@public.example"]:
            with self.subTest(target=target):
                self.session.get.reset_mock()
                self.session.get.side_effect = [response(302, target)]
                self.assertEqual(mod._fetch_page("https://public.example"), "")
                self.assertEqual(self.session.get.call_count, 1)
        self.dns.side_effect = [answers(PUBLIC), answers("10.0.0.1")]
        self.session.get.reset_mock()
        self.session.get.side_effect = [response(302, "https://other.example")]
        self.assertEqual(mod._fetch_page("https://public.example"), "")
        self.assertEqual(self.session.get.call_count, 1)

    def test_redirect_statuses_relative_location_and_closure(self):
        for status in [301, 302, 303, 307, 308]:
            with self.subTest(status=status):
                first, last = response(status, "../next"), response()
                self.session.get.side_effect = [first, last]
                self.assertTrue(mod._fetch_page("https://public.example/path/start"))
                self.assertEqual(self.session.get.call_args.args[0], "https://public.example/next")
                first.__exit__.assert_called_once()
                last.__exit__.assert_called_once()

    def test_redirect_limit(self):
        self.session.get.side_effect = [response(302, f"/{i}") for i in range(3)] + [response()]
        self.assertTrue(mod._fetch_page("https://public.example"))
        self.assertEqual(self.session.get.call_count, 4)
        self.session.get.reset_mock()
        self.session.get.side_effect = [response(302, f"/{i}") for i in range(4)]
        self.assertEqual(mod._fetch_page("https://public.example"), "")
        self.assertEqual(self.session.get.call_count, 4)

    def test_unhandled_redirect_and_missing_location(self):
        for status in [300, 304, 305, 306, 302]:
            self.session.get.reset_mock()
            self.session.get.side_effect = [response(status)]
            self.assertEqual(mod._fetch_page("https://public.example"), "")
            self.assertEqual(self.session.get.call_count, 1)

    def test_snippet_fallback(self):
        row = {"url": "https://127.0.0.1", "content": TEXT}
        self.assertEqual(mod._source_text(row), (TEXT.strip(), "tavily_snippet"))
        self.assertEqual(mod._source_text({**row, "content": "short"}), ("", "none"))
        self.assertEqual(mod._source_text({**row, "url": "https://127.0.0.1/a.pdf"}),
                         (TEXT.strip(), "tavily_pdf_snippet"))
        self.session.get.assert_not_called()

    def test_public_contract(self):
        signature = inspect.signature(mod.search)
        self.assertEqual(signature.parameters["max_sources"].default, 5)
        rows = [{"url": "https://public.example", "content": TEXT, "title": "Production",
                 "tavily_score": 0.9}]
        with patch.object(mod, "_search_web", return_value=(rows, ["production"])):
            result = mod.search("annual production growth", max_sources=5)
        self.assertIsInstance(result, list)
        self.assertTrue(0 < len(result) <= 5)
        self.assertTrue({"id", "url", "text", "title", "domain", "metadata"} <= result[0].keys())

    def test_lite_retriever_compatibility(self):
        spec = importlib.util.spec_from_file_location("security_adapter", ROOT / "backend_v2/app/retrieval.py")
        adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter)
        rows = [{"url": f"https://public.example/{i}", "content": TEXT,
                 "title": "Production", "tavily_score": 0.9} for i in range(3)]
        original_fetch, original_build = mod._fetch_page, mod._build_candidates
        previous = getattr(mod, "_verify_parallel", None)
        try:
            with patch.object(mod, "_search_web", return_value=(rows, [])):
                sequential = mod.search("annual production growth", 5)
                retriever = adapter.LiteRetriever()
                parallel = asyncio.run(retriever("annual production growth"))
                self.assertTrue(retriever.parallel_fetch)
                self.assertEqual(sequential, parallel)
                self.dns.return_value = answers("10.0.0.1")
                self.session.get.reset_mock()
                fallback = asyncio.run(retriever("annual production growth"))
                self.assertTrue(fallback)
                self.assertTrue(all(s["metadata"]["fetch_method"] == "tavily_snippet" for s in fallback))
                self.session.get.assert_not_called()
        finally:
            mod._fetch_page, mod._build_candidates = original_fetch, original_build
            if previous is None:
                del mod._verify_parallel
            else:
                mod._verify_parallel = previous


    def test_streaming_sizes_and_headers(self):
        limit = mod.MAX_RESPONSE_BYTES
        for size, header, accepted in [
            (limit - 1, None, True), (limit, str(limit), True),
            (limit + 1, None, False), (limit + 1, "1", False),
            (limit + 1, "invalid", False), (limit + 1, "-1", False),
            (limit + 1, "+1", False), (limit, None, True),
        ]:
            with self.subTest(size=size, header=header):
                resp = response()
                if header is not None:
                    resp.headers["Content-Length"] = header
                body = b"x" * size
                resp.iter_content.return_value = (
                    body[i:i + 16384] for i in range(0, size, 16384)
                )
                self.session.get.side_effect = [resp]
                with patch.object(mod, "_html_to_text", return_value="parsed") as parse:
                    self.assertEqual(mod._fetch_page("https://public.example"), "parsed" if accepted else "")
                    self.assertEqual(parse.call_count, int(accepted))
                    if accepted:
                        self.assertEqual(len(parse.call_args.args[0]), size)
                resp.__exit__.assert_called_once()

    def test_large_content_length_does_not_read(self):
        resp = response()
        resp.headers["Content-Length"] = str(mod.MAX_RESPONSE_BYTES + 1)
        self.session.get.side_effect = [resp]
        self.assertEqual(mod._fetch_page("https://public.example"), "")
        resp.iter_content.assert_not_called()
        resp.__exit__.assert_called_once()

    def test_overflow_not_buffered_or_parsed_and_no_next_chunk(self):
        buffers = []
        class ObservedBuffer(bytearray):
            def __init__(self):
                super().__init__()
                buffers.append(self)
        advanced = []
        def chunks():
            yield b"a" * mod.MAX_RESPONSE_BYTES
            yield b"b"
            advanced.append(True)
            yield b"must not read"
        resp = response()
        resp.iter_content.return_value = chunks()
        self.session.get.side_effect = [resp]
        with patch.object(mod, "bytearray", ObservedBuffer, create=True), \
             patch.object(mod, "_html_to_text") as parse:
            self.assertEqual(mod._fetch_page("https://public.example"), "")
            parse.assert_not_called()
        self.assertEqual(len(buffers[0]), mod.MAX_RESPONSE_BYTES)
        self.assertNotIn(b"b", buffers[0])
        self.assertEqual(advanced, [])

    def test_stream_error_closes_and_falls_back(self):
        def chunks():
            yield b"partial"
            raise mod.requests.exceptions.ChunkedEncodingError("broken stream")
        resp = response()
        resp.iter_content.return_value = chunks()
        self.session.get.side_effect = [resp]
        self.assertEqual(mod._source_text({"url": "https://public.example", "content": TEXT}),
                         (TEXT.strip(), "tavily_snippet"))
        resp.__exit__.assert_called_once()
        self.factory.return_value.__exit__.assert_called_once()

    def test_size_rejection_falls_back(self):
        resp = response()
        resp.iter_content.return_value = iter([b"x" * mod.MAX_RESPONSE_BYTES, b"x"])
        self.session.get.side_effect = [resp]
        self.assertEqual(mod._source_text({"url": "https://public.example", "content": TEXT}),
                         (TEXT.strip(), "tavily_snippet"))

    def test_decode_after_complete_body(self):
        for encoding in (None, "utf-8", "invalid-charset"):
            resp = response()
            resp.encoding = encoding
            completed = []
            def chunks():
                yield b"<p>\xc4"
                yield b"\xb0stanbul</p>"
                completed.append(True)
            resp.iter_content.return_value = chunks()
            self.session.get.side_effect = [resp]
            def parse(html):
                self.assertEqual(completed, [True])
                self.assertEqual(html, "<p>İstanbul</p>")
                return "İstanbul"
            with patch.object(mod, "_html_to_text", side_effect=parse):
                self.assertEqual(mod._fetch_page("https://public.example"), "İstanbul")


class TimeoutTests(unittest.TestCase):
    setUp = SecurityTests.setUp
    # Keep deadline tests alongside the existing offline transport fixtures.
    def test_config_validation(self):
        for value in ("nan", "inf", "-inf", "0", "-1", "bad"):
            with patch.dict(os.environ, {"TEST_LITE_TIMEOUT": value}):
                self.assertEqual(mod._positive_env("TEST_LITE_TIMEOUT", 3), 3)
        with patch.dict(os.environ, {"TEST_LITE_TIMEOUT": "1.5"}):
            self.assertEqual(mod._positive_env("TEST_LITE_TIMEOUT", 3), 1.5)

    def test_expired_deadline_no_network(self):
        token = mod._total_deadline.set(mod.time.monotonic() - 1)
        try:
            with self.assertRaises(mod._RetrievalTimeout):
                mod._fetch_page("https://public.example")
            self.session.get.assert_not_called()
            self.dns.assert_not_called()
        finally:
            mod._total_deadline.reset(token)

    def test_dns_exhausts_budget_before_request(self):
        clock = [100.0]
        def dns(*args, **kwargs):
            clock[0] += 11
            return answers(PUBLIC)
        self.dns.side_effect = dns
        with patch.object(mod, "time", SimpleNamespace(monotonic=lambda: clock[0])):
            self.assertEqual(mod._fetch_page("https://public.example"), "")
        self.session.get.assert_not_called()

    def test_page_budget_not_reset_by_redirect(self):
        clock = [100.0]
        def get(*args, **kwargs):
            clock[0] += 6
            return response(302, "/next")
        self.session.get.side_effect = get
        with patch.object(mod, "time", SimpleNamespace(monotonic=lambda: clock[0])):
            self.assertEqual(mod._fetch_page("https://public.example"), "")
        self.assertEqual(self.session.get.call_count, 2)
        self.assertEqual(self.session.get.call_args.kwargs["timeout"],
                         (min(mod.CONNECT_TIMEOUT, 4), min(mod.READ_TIMEOUT, 4)))

    def test_stream_page_timeout_fallback(self):
        clock = [100.0]
        def chunks():
            yield b"first"
            clock[0] += 11
            yield b"late"
        resp = response()
        resp.iter_content.return_value = chunks()
        self.session.get.side_effect = [resp]
        with patch.object(mod, "time", SimpleNamespace(monotonic=lambda: clock[0])):
            self.assertEqual(mod._source_text({"url": "https://public.example", "content": TEXT}),
                             (TEXT.strip(), "tavily_snippet"))
        resp.__exit__.assert_called_once()

    def test_tavily_capability_and_remaining_timeout(self):
        calls = []
        class Supported:
            def search(self, query, timeout=60):
                calls.append(timeout)
                return {}
        class Unsupported:
            def search(self, query):
                raise AssertionError("must not call unsupported client")
        class Broken:
            def search(self, query, timeout=60):
                raise TypeError("internal SDK error")
        token = mod._total_deadline.set(mod.time.monotonic() + 1)
        try:
            mod._tavily_search(Supported(), query="test")
            self.assertTrue(0 < calls[0] <= 1)
            with self.assertRaises(mod._TavilyCapabilityError):
                mod._tavily_search(Unsupported(), query="test")
            with self.assertRaisesRegex(TypeError, "internal SDK error"):
                mod._tavily_search(Broken(), query="test")
        finally:
            mod._total_deadline.reset(token)

    def test_installed_tavily_timeout_forwarded(self):
        try:
            from tavily import TavilyClient
        except ImportError:
            self.skipTest("Tavily SDK not installed")
        client = TavilyClient(api_key="test-key")
        reply = MagicMock(status_code=200)
        reply.json.return_value = {"results": []}
        with patch.object(client.session, "post", return_value=reply) as post:
            mod._tavily_search(client, query="test")
        self.assertEqual(post.call_args.kwargs["timeout"], mod.TAVILY_TIMEOUT)

    def test_total_timeout_no_partial_and_stage(self):
        clock = [100.0]
        class Client:
            def search(self, query, timeout=60, **kwargs):
                clock[0] += 21
                return {"results": []}
        with patch.object(mod, "time", SimpleNamespace(monotonic=lambda: clock[0])), \
             patch.object(mod, "_tavily_client", Client()):
            result = mod.search_detailed("test claim")
            self.assertEqual(result["sources"], [])
            self.assertTrue(result["diagnostics"]["timed_out"])
            self.assertEqual(result["diagnostics"]["timeout_stage"], "tavily")
            self.assertEqual(mod.search("test claim"), [])
        self.session.get.assert_not_called()
        self.assertIsNone(mod._total_deadline.get())

    def test_ranking_expiry_discards_completed_sources(self):
        clock = [100.0]
        original_rank = mod._select_diverse
        def rank(*args):
            selected = original_rank(*args)
            self.assertTrue(selected)
            clock[0] += 21
            return selected
        rows = [{"url": "https://public.example", "content": TEXT, "tavily_score": 0.9}]
        with patch.object(mod, "time", SimpleNamespace(monotonic=lambda: clock[0])), \
             patch.object(mod, "_search_web", return_value=(rows, [])), \
             patch.object(mod, "_select_diverse", side_effect=rank):
            result = mod.search_detailed("test claim")
        self.assertTrue(result["diagnostics"]["timed_out"])
        self.assertEqual(result["sources"], [])


class PartialTests(unittest.TestCase):
    setUp = SecurityTests.setUp

    def rows(self):
        return [{"url": f"https://public{i}.example", "title": "growth",
                 "content": TEXT, "tavily_score": 0.9} for i in range(3)]

    def page(self):
        resp = response()
        resp.iter_content.return_value = iter([("<p>" + "annual production growth " * 25 + "</p>").encode()])
        return resp

    def test_sequential_partial_and_max_sources(self):
        for maximum in (1, 2):
            clock = [100.0]
            count = [0]
            def get(*args, **kwargs):
                count[0] += 1
                if count[0] == 3:
                    clock[0] += 21
                return self.page()
            self.session.get.side_effect = get
            with patch.object(mod, "time", SimpleNamespace(monotonic=lambda: clock[0])), \
                 patch.object(mod, "_search_web", return_value=(self.rows(), [])):
                result = mod.search_detailed("annual production growth", maximum)
            self.assertEqual(len(result["sources"]), maximum)
            self.assertTrue(result["diagnostics"]["partial_result"])
            self.assertEqual(result["diagnostics"]["completed_source_count"], maximum)
            self.assertTrue(all("public2" not in s["url"] for s in result["sources"]))

    def test_search_list_returns_partial(self):
        clock = [100.0]
        responses = [self.page()]
        def get(*args, **kwargs):
            if responses:
                return responses.pop()
            clock[0] += 21
            return self.page()
        self.session.get.side_effect = get
        with patch.object(mod, "time", SimpleNamespace(monotonic=lambda: clock[0])), \
             patch.object(mod, "_search_web", return_value=(self.rows(), [])):
            result = mod.search("annual production growth", 2)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_commit_is_authoritative_and_previous_snapshot_survives(self):
        for expire_on in (1, 2):
            clock = [100.0]
            calls = [0]
            original = mod._sources_from_selected
            def build(selected):
                result = original(selected)
                calls[0] += 1
                if calls[0] == expire_on:
                    clock[0] += 21
                return result
            self.session.get.side_effect = lambda *args, **kwargs: self.page()
            with patch.object(mod, "time", SimpleNamespace(monotonic=lambda: clock[0])), \
                 patch.object(mod, "_search_web", return_value=(self.rows(), [])), \
                 patch.object(mod, "_sources_from_selected", side_effect=build):
                result = mod.search_detailed("annual production growth", 3)
            self.assertEqual(len(result["sources"]), expire_on - 1)
            self.assertEqual(result["diagnostics"]["timeout_stage"], "partial_commit")
            self.assertEqual(result["diagnostics"]["partial_result"], expire_on == 2)

    def test_rejected_fetch_snippets_normal_but_not_partial(self):
        for failure in ("security", "oversize", "stream_error", "page_timeout", "network"):
            clock = [100.0]
            rows = self.rows()[:1]
            if failure == "security":
                rows[0]["url"] = "https://127.0.0.1"
            def get(*args, **kwargs):
                resp = self.page()
                if failure == "oversize":
                    resp.iter_content.return_value = iter([b"x" * mod.MAX_RESPONSE_BYTES, b"x"])
                elif failure == "stream_error":
                    def chunks():
                        yield b"incomplete"
                        raise mod.requests.exceptions.ChunkedEncodingError("broken")
                    resp.iter_content.return_value = chunks()
                elif failure == "page_timeout":
                    clock[0] += 11
                elif failure == "network":
                    raise mod.requests.exceptions.ConnectionError("offline")
                return resp
            original = mod._select_diverse
            def expire(candidates, maximum):
                # No eligible fetched candidates: only final normal ranking reaches here.
                clock[0] += 21
                return original(candidates, maximum)
            self.session.get.side_effect = get
            with patch.object(mod, "time", SimpleNamespace(monotonic=lambda: clock[0])), \
                 patch.object(mod, "_search_web", return_value=(rows, [])):
                normal = mod.search_detailed("annual production growth", 2)
                self.assertTrue(normal["sources"], failure)
                self.assertTrue(all(s["metadata"]["fetch_method"] == "tavily_snippet"
                                    for s in normal["sources"]))
                self.assertFalse(normal["diagnostics"]["partial_result"])
                with patch.object(mod, "_select_diverse", side_effect=expire):
                    expired = mod.search_detailed("annual production growth", 2)
                self.assertEqual(expired["sources"], [], failure)
                self.assertFalse(expired["diagnostics"]["partial_result"])
                self.assertEqual(expired["diagnostics"]["completed_source_count"], 0)

    def test_stable_order_immutable_snapshot_and_late_completion(self):
        snapshots = []
        for order in ((0, 1), (1, 0)):
            state = {"pages": {}, "snapshot": [], "max_sources": 2,
                     "diagnostics": mod._initial_diagnostics()}
            token = mod._partial_state.set(state)
            deadline = mod.time.monotonic() + 10
            deadline_token = mod._total_deadline.set(deadline)
            try:
                for index in order:
                    mod._process_ready_page("annual production growth", self.rows()[index], index,
                                            "annual production growth " * 25, deadline - 1)
                saved = deepcopy(state["snapshot"])
                snapshots.append(saved)
                for candidates, _ in state["pages"].values():
                    for candidate in candidates:
                        candidate["text"] = "mutated"
                self.assertEqual(state["snapshot"], saved)
                with self.assertRaises(mod._RetrievalTimeout):
                    mod._process_ready_page("annual production growth", self.rows()[2], 2,
                                            TEXT, deadline + 1)
                self.assertEqual(state["snapshot"], saved)
            finally:
                mod._partial_state.reset(token)
                mod._total_deadline.reset(deadline_token)
        self.assertEqual(snapshots[0], snapshots[1])

    def test_normal_short_result_is_not_partial(self):
        self.session.get.side_effect = lambda *args, **kwargs: self.page()
        with patch.object(mod, "_search_web", return_value=(self.rows()[:1], [])):
            result = mod.search_detailed("annual production growth", 5)
        self.assertEqual(len(result["sources"]), 1)
        self.assertFalse(result["diagnostics"]["timed_out"])
        self.assertFalse(result["diagnostics"]["partial_result"])
        self.assertEqual(result["diagnostics"]["completed_source_count"], 1)


class RealSessionStreamingTests(unittest.TestCase):
    """Exercise Requests redirect preparation and urllib3 decompression offline."""
    def test_redirect_body_unread_closed_before_final_and_final_limited(self):
        import requests
        from urllib3.response import HTTPResponse
        for oversized in (False, True):
            redirect_body = MagicMock()
            redirect = requests.Response()
            redirect.status_code = 302
            redirect.headers["Location"] = "/final"
            redirect.raw = redirect_body
            final = requests.Response()
            final.status_code = 200
            final.headers["Content-Type"] = "text/html"
            final.encoding = "utf-8"
            payload = b"x" * (mod.MAX_RESPONSE_BYTES + 1) if oversized else b"<p>accepted</p>"
            final.raw = HTTPResponse(body=io.BytesIO(payload), preload_content=False)
            calls = []
            def send(adapter, request, **kwargs):
                calls.append(request.url)
                self.assertTrue(kwargs["stream"])
                if len(calls) == 1:
                    result = redirect
                else:
                    redirect_body.close.assert_called_once()
                    redirect_body.read.assert_not_called()
                    redirect_body.stream.assert_not_called()
                    result = final
                result.request = request
                result.url = request.url
                return result
            with patch.object(mod.socket, "getaddrinfo", return_value=answers(PUBLIC)), \
                 patch.object(requests.adapters.HTTPAdapter, "send", new=send):
                self.assertEqual(mod._fetch_page("https://public.example/start"), "" if oversized else "accepted")
            self.assertEqual(calls, ["https://public.example/start", "https://public.example/final"])
            self.assertTrue(final.raw.closed)

    def test_decompressed_bytes_are_limited(self):
        import requests
        from urllib3.response import HTTPResponse
        compressed = gzip.compress(b"x" * (mod.MAX_RESPONSE_BYTES + 1))
        self.assertLess(len(compressed), mod.MAX_RESPONSE_BYTES)
        resp = requests.Response()
        resp.status_code = 200
        resp.encoding = "utf-8"
        resp.headers.update({"Content-Type": "text/html", "Content-Length": str(len(compressed)),
                             "Content-Encoding": "gzip"})
        resp.raw = HTTPResponse(body=io.BytesIO(compressed),
                                headers={"Content-Encoding": "gzip"}, preload_content=False)
        with patch.object(mod.socket, "getaddrinfo", return_value=answers(PUBLIC)), \
             patch.object(requests.adapters.HTTPAdapter, "send", return_value=resp):
            self.assertEqual(mod._fetch_page("https://public.example"), "")
        self.assertTrue(resp.raw.closed)


class ProviderTests(unittest.TestCase):
    def run_queries(self, outcomes, client=None):
        pending = iter(outcomes)
        class Client:
            def search(self, timeout=5, **kwargs):
                outcome = next(pending)
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
        with patch.object(mod, "_get_tavily_client", return_value=client or Client()), \
             patch.object(mod, "generate_queries", return_value=["annual production"] * len(outcomes)), \
             patch.object(mod, "_fetch_page", return_value=TEXT):
            result = mod.search_detailed("annual production growth")
        d = result["diagnostics"]
        self.assertEqual(d["tavily_query_count"], d["successful_query_count"] + d["failed_query_count"])
        return result

    @staticmethod
    def http_error(status):
        response = mod.requests.Response()
        response.status_code = status
        response._content = b"SECRET body"
        response.request = mod.requests.Request("POST", "https://api.tavily.com/search",
                                                 headers={"Authorization": "SECRET key"}).prepare()
        return mod.requests.HTTPError("SECRET exception", response=response)

    def test_classification(self):
        from tavily import errors
        cases = [
            (self.http_error(429), "rate_limited", 429),
            (errors.UsageLimitExceededError("quota SECRET"), "usage_limited", None),
            (self.http_error(503), "service_error", 503),
            (self.http_error(401), "auth_error", 401),
            (self.http_error(403), "auth_error", 403),
            (errors.InvalidAPIKeyError("SECRET"), "auth_error", None),
            (errors.ForbiddenError("403 SECRET"), "provider_error", None),
            (errors.TimeoutError(5), "timeout", None),
            (mod.requests.Timeout("SECRET"), "timeout", None),
            (RuntimeError("quota exhausted SECRET"), "provider_error", None),
            (TypeError("SDK internal SECRET"), "provider_error", None),
        ]
        for error, kind, status in cases:
            with self.subTest(kind=kind, error_type=type(error).__name__):
                r = self.run_queries([error])
                d = r["diagnostics"]
                self.assertEqual(d["provider_error_kind"], kind)
                self.assertEqual(d["provider_http_status"], status)
                self.assertIs(d["provider_ok"], False)
                self.assertFalse(d["provider_partial_failure"])
                self.assertEqual(d["failed_query_count"], 1)
                self.assertEqual(r["status"], "search_provider_error")

    def test_success_empty_and_results(self):
        empty = self.run_queries([{"results": []}])
        self.assertEqual(empty["status"], "not_enough_evidence")
        self.assertIs(empty["diagnostics"]["provider_ok"], True)
        row = {"url": "https://public.example/report", "content": TEXT, "score": 0.9}
        r = self.run_queries([{"results": [row, row]}, {"results": [row]}])
        self.assertTrue(r["sources"])
        self.assertEqual(r["diagnostics"]["provider_result_count"], 3)
        self.assertEqual(r["diagnostics"]["raw_search_results"], 1)
        self.assertEqual(r["diagnostics"]["successful_query_count"], 2)

    def test_mixed_and_all_fail(self):
        row = {"url": "https://public.example/report", "content": TEXT, "score": 0.9}
        for status in (429, 503):
            r = self.run_queries([{"results": [row]}, self.http_error(status), {"results": []}])
            d = r["diagnostics"]
            self.assertTrue(r["sources"])
            self.assertEqual(r["status"], "evidence_found")
            self.assertTrue(d["provider_partial_failure"])
            self.assertFalse(d["partial_result"])
            self.assertEqual((d["successful_query_count"], d["failed_query_count"]), (2, 1))
            all_failed = self.run_queries([self.http_error(status)] * 3)
            self.assertEqual(all_failed["status"], "search_provider_error")
            self.assertFalse(all_failed["diagnostics"]["provider_partial_failure"])

    def test_unsupported_and_malformed(self):
        class Unsupported:
            def search(self, query):
                raise AssertionError("must not call")
        r = self.run_queries([None, None], Unsupported())
        d = r["diagnostics"]
        self.assertEqual((d["tavily_query_count"], d["skipped_query_count"]), (0, 2))
        self.assertEqual(d["provider_error_kind"], "provider_error")
        for malformed in (None, {}, {"results": None}, {"results": [1]},
                          {"results": [{"score": "bad"}]}, {"results": [{"url": 3}]}):
            r = self.run_queries([malformed])
            self.assertEqual(r["diagnostics"]["failed_query_count"], 1)
            self.assertEqual(r["diagnostics"]["provider_error_kind"], "provider_error")

    def test_missing_key(self):
        with patch.object(mod, "_tavily_client", None), patch.dict(os.environ, {"TAVILY_API_KEY": ""}):
            r = mod.search_detailed("annual production growth")
            self.assertEqual(mod.search("annual production growth"), [])
        d = r["diagnostics"]
        self.assertIs(d["provider_ok"], False)
        self.assertEqual(d["provider_error_kind"], "auth_error")
        for key in ("tavily_query_count", "successful_query_count", "failed_query_count"):
            self.assertEqual(d[key], 0)

    def test_secret_leakage(self):
        import json
        from contextlib import redirect_stdout, redirect_stderr
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            r = self.run_queries([self.http_error(429)])
        self.assertNotIn("SECRET", json.dumps(r) + output.getvalue())

    def test_deadline_before_provider_and_after_failure(self):
        token = mod._total_deadline.set(mod.time.monotonic() - 1)
        state = {"diagnostics": mod._initial_diagnostics()}
        state_token = mod._partial_state.set(state)
        try:
            with patch.object(mod, "_get_tavily_client") as client:
                with self.assertRaises(mod._RetrievalTimeout):
                    mod._search_web("annual production")
                client.assert_not_called()
            self.assertIsNone(state["diagnostics"]["provider_ok"])
            self.assertEqual(state["diagnostics"]["tavily_query_count"], 0)
        finally:
            mod._partial_state.reset(state_token)
            mod._total_deadline.reset(token)

    def test_provider_timeout_exhausts_total_no_next_query(self):
        clock = [100.0]
        calls = []
        class Client:
            def search(self, timeout=5, **kwargs):
                calls.append(timeout)
                clock[0] += mod.TOTAL_DEADLINE + 1
                raise mod.requests.Timeout("SECRET")
        with patch.object(mod, "time", SimpleNamespace(monotonic=lambda: clock[0])):
            r = self.run_queries([None, None, None], Client())
        d = r["diagnostics"]
        self.assertEqual(len(calls), 1)
        self.assertEqual((d["failed_query_count"], d["skipped_query_count"]), (1, 2))
        self.assertTrue(d["timed_out"])
        self.assertFalse(d["partial_result"])
        self.assertEqual(d["provider_error_kind"], "timeout")
        self.assertEqual(r["status"], "search_provider_error")

    def test_provider_diagnostics_claim_isolation(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        barrier = Barrier(2)
        error = self.http_error(429)
        class Client:
            def search(self, query, timeout=5, **kwargs):
                barrier.wait(timeout=2)
                if query == "failed claim":
                    raise error
                return {"results": []}
        with patch.object(mod, "_get_tavily_client", return_value=Client()), \
             patch.object(mod, "generate_queries", side_effect=lambda claim, frame: [claim]), \
             ThreadPoolExecutor(max_workers=2) as pool:
            failed = pool.submit(mod.search_detailed, "failed claim")
            success = pool.submit(mod.search_detailed, "successful claim")
            a, b = failed.result()["diagnostics"], success.result()["diagnostics"]
        self.assertIs(a["provider_ok"], False)
        self.assertIs(b["provider_ok"], True)
        self.assertEqual(a["provider_error_kind"], "rate_limited")
        self.assertIsNone(b["provider_error_kind"])
        self.assertEqual((a["failed_query_count"], b["failed_query_count"]), (1, 0))
        self.assertIsNone(mod._partial_state.get())

    def test_installed_sdk_http_mapping(self):
        from tavily import TavilyClient
        client = TavilyClient(api_key="test-secret")
        for status, kind in ((429, "usage_limited"), (403, "provider_error"),
                             (401, "auth_error"), (503, "service_error")):
            response = mod.requests.Response()
            response.status_code = status
            response._content = b'{"detail":{"error":"test-secret"}}'
            with patch.object(client.session, "post", return_value=response):
                r = self.run_queries([None], client)
            self.assertEqual(r["diagnostics"]["provider_error_kind"], kind)
            self.assertNotIn("test-secret", str(r))


class CacheTests(unittest.TestCase):
    CLAIM = "Annual production growth in 2024"

    def setUp(self):
        self.cache = mod._TavilyQueryCache()
        self.cache.enabled = True
        self.calls = []
        self.outcome = None
        test = self
        class Client:
            def search(self, query, timeout=5, **kwargs):
                test.calls.append(query)
                if test.outcome:
                    return test.outcome(query)
                return test.payload()
        for context in (
            patch.object(mod, "_tavily_cache", self.cache),
            patch.object(mod, "_get_tavily_client", return_value=Client()),
            patch.object(mod.socket, "getaddrinfo", return_value=answers(PUBLIC)),
        ):
            context.start()
            self.addCleanup(context.stop)
        self.get = patch.object(mod.requests.Session, "get", autospec=True).start()
        self.addCleanup(patch.stopall)
        def get(session, url, **kwargs):
            self.assertFalse(session.trust_env)
            self.assertTrue(kwargs["stream"])
            self.assertFalse(kwargs["allow_redirects"])
            return response()
        self.get.side_effect = get

    def payload(self):
        return {"results": [{"url": "https://public.example/report", "content": TEXT,
                             "title": "Annual production", "score": 0.9}]}

    def run_claim(self, claim=None):
        result = mod.search_detailed(claim or self.CLAIM)
        d = result["diagnostics"]
        self.assertEqual(d["tavily_query_count"], d["successful_query_count"] + d["failed_query_count"])
        return result

    def test_repeated_cross_claim_exact_and_all_hit(self):
        first = self.run_claim()
        n = len(self.calls)
        self.assertEqual(n, 3)
        self.assertEqual(first["diagnostics"]["cache_miss_count"], n)
        fetches = self.get.call_count
        second = self.run_claim(self.CLAIM + ".")
        self.assertEqual(len(self.calls), n)
        self.assertGreater(self.get.call_count, fetches)
        self.assertEqual(first["sources"], second["sources"])
        self.assertTrue(first["sources"])
        d = second["diagnostics"]
        self.assertIsNone(d["provider_ok"])
        self.assertEqual(d["cache_hit_count"], n)
        self.assertEqual(d["avoided_provider_call_count"], n)
        for field in ("tavily_query_count", "successful_query_count", "failed_query_count", "provider_result_count"):
            self.assertEqual(d[field], 0)
        self.assertEqual(self.run_claim()["sources"], first["sources"])
        self.cache.enabled = False
        disabled = self.run_claim()
        self.assertEqual(disabled["sources"], first["sources"])
        self.assertEqual(disabled["diagnostics"]["cache_hit_count"], 0)
        self.assertEqual(disabled["diagnostics"]["cache_miss_count"], 0)
        self.assertEqual(len(self.calls), 2*n)

    def test_keys_and_parameters(self):
        def key(q, **params):
            return self.cache.key(dict(query=q, search_depth="basic", **params))
        self.assertEqual(key(" é  x "), key("e\u0301 x"))
        variants = ("ı", "i", "İ", "I", "ç", "c", "ş", "s", "ğ", "g", "ö", "o", "ü", "u", "a?", "a")
        self.assertEqual(len({key(q) for q in variants}), len(variants))
        self.cache.put(key("é"), self.payload())
        self.assertIsNotNone(self.cache.get(key("e\u0301")))
        self.run_claim()
        with patch.object(mod, "SEARCH_RESULTS_PER_QUERY", 6):
            self.assertEqual(self.run_claim()["diagnostics"]["cache_hit_count"], 0)
        self.assertNotEqual(key("q", max_results=5), key("q", max_results=6))
        self.assertNotEqual(key("q", include_raw_content=False), key("q", include_raw_content=True))

    def test_ttl_not_sliding_and_live_after_expiry(self):
        with patch.object(mod, "time", SimpleNamespace(monotonic=lambda: 100)):
            self.run_claim()
        with patch.object(mod, "time", SimpleNamespace(monotonic=lambda: 159)):
            d = self.run_claim()["diagnostics"]
            self.assertEqual(d["cache_hit_count"], 3)
            self.assertEqual(d["cache_max_age_seconds"], 59)
        with patch.object(mod, "time", SimpleNamespace(monotonic=lambda: 160)):
            self.assertEqual(self.run_claim()["diagnostics"]["tavily_query_count"], 3)

    def test_lru_byte_budget_and_mutation(self):
        self.cache.max_entries = 2
        self.cache.put("a", self.payload()); self.cache.put("b", self.payload())
        hit, age = self.cache.get("a")
        hit["results"].clear()
        self.assertTrue(self.cache.get("a")[0]["results"])
        self.cache.put("c", self.payload())
        self.assertIsNone(self.cache.get("b"))
        self.assertEqual(len(self.cache._items), 2)
        self.cache.max_bytes = self.cache._bytes // 2
        self.cache.put("d", self.payload())
        self.assertEqual(len(self.cache._items), 1)
        self.assertLessEqual(self.cache._bytes, self.cache.max_bytes)

    def test_oversize_does_not_break_retrieval(self):
        self.cache.max_entry_bytes = 1
        self.assertTrue(self.run_claim()["sources"])
        self.assertEqual(len(self.cache._items), 0)
        self.assertEqual(self.run_claim()["diagnostics"]["tavily_query_count"], 3)

    def test_no_cache_for_errors_zero_malformed(self):
        from tavily import errors
        outcomes = [ProviderTests.http_error(429), ProviderTests.http_error(503),
                    ProviderTests.http_error(401), errors.UsageLimitExceededError("fixture"),
                    mod.requests.Timeout("fixture"), RuntimeError("fixture"),
                    {"results": []}, {"results": "invalid"}]
        for outcome in outcomes:
            def provider(query):
                if isinstance(outcome, Exception): raise outcome
                return outcome
            self.outcome = provider
            self.run_claim(); second = self.run_claim()
            self.assertEqual(len(self.cache._items), 0)
            self.assertEqual(second["diagnostics"]["cache_hit_count"], 0)
            self.assertEqual(second["diagnostics"]["tavily_query_count"], 3)

    def test_mixed_cache_and_live_status(self):
        failing = mod.generate_queries(self.CLAIM)[1]
        def provider(query):
            if query == failing: raise ProviderTests.http_error(429)
            return self.payload()
        self.outcome = provider
        first = self.run_claim()
        self.assertTrue(first["diagnostics"]["provider_partial_failure"])
        second = self.run_claim()
        d = second["diagnostics"]
        self.assertEqual(d["cache_hit_count"], 2)
        self.assertEqual(d["failed_query_count"], 1)
        self.assertFalse(d["provider_partial_failure"])
        self.assertFalse(d["provider_ok"])
        self.assertEqual(first["sources"], second["sources"])
        self.assertEqual(second["status"], "evidence_found")

    def test_cache_and_live_success_and_query_diagnostics(self):
        first = self.run_claim()
        queries = mod.generate_queries(self.CLAIM)
        key = self.cache.key(dict(query=queries[1], search_depth="basic",
                                  max_results=mod.SEARCH_RESULTS_PER_QUERY, include_raw_content=False))
        with self.cache._lock:
            self.cache._bytes -= len(self.cache._items.pop(key)[1])
        d = self.run_claim()["diagnostics"]
        self.assertIs(d["provider_ok"], True)
        self.assertEqual((d["cache_hit_count"], d["successful_query_count"], d["tavily_query_count"]), (2, 1, 1))
        self.assertEqual((d["generated_query_count"], d["unique_query_count"], d["planned_query_count"]), (3, 3, 3))
        self.assertFalse(d["provider_partial_failure"])

    def test_late_result_not_cached(self):
        def provider(query):
            mod._total_deadline.set(mod.time.monotonic() - 1)
            return self.payload()
        self.outcome = provider
        result = self.run_claim()
        self.assertTrue(result["diagnostics"]["timed_out"])
        self.assertEqual(len(self.cache._items), 0)
        self.assertEqual(result["diagnostics"]["tavily_query_count"], 1)

    def test_unsupported_not_cached(self):
        class Unsupported:
            def search(self, query): raise AssertionError("must not start")
        with patch.object(mod, "_get_tavily_client", return_value=Unsupported()):
            d = self.run_claim()["diagnostics"]
        self.assertEqual(d["tavily_query_count"], 0)
        self.assertEqual(d["skipped_query_count"], 3)
        self.assertEqual(len(self.cache._items), 0)

    def test_concurrent_cold_miss(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        barrier = Barrier(2)
        first_query = mod.generate_queries(self.CLAIM)[0]
        def provider(query):
            if query == first_query: barrier.wait(timeout=2)
            return self.payload()
        self.outcome = provider
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(self.run_claim)
            b = pool.submit(self.run_claim)
            a, b = a.result(), b.result()
        self.assertEqual(a["sources"], b["sources"])
        self.assertEqual(self.calls.count(first_query), 2)
        self.assertEqual(self.cache._bytes, sum(len(v[1]) for v in self.cache._items.values()))
        self.assertEqual(len(self.cache._items), 3)

    def test_invalid_config(self):
        for value in ("", "bad", "0", "-1", "NaN", "Infinity", "1.5", "9"*100):
            with patch.dict(os.environ, {"LITE_TAVILY_CACHE_MAX_ENTRIES": value,
                                        "LITE_TAVILY_CACHE_MAX_BYTES": value,
                                        "LITE_TAVILY_CACHE_MAX_ENTRY_BYTES": value}):
                c = mod._TavilyQueryCache()
                self.assertEqual((c.max_entries, c.max_bytes, c.max_entry_bytes), (128, 4194304, 131072))
        for value in ("", "bad", "0", "-1", "NaN", "Infinity"):
            with patch.dict(os.environ, {"LITE_TAVILY_CACHE_TTL_SECONDS": value}):
                self.assertEqual(mod._TavilyQueryCache().ttl, 60)
        with patch.dict(os.environ, {"LITE_TAVILY_CACHE_ENABLED": "false"}):
            self.assertFalse(mod._TavilyQueryCache().enabled)


class CancellationTests(unittest.TestCase):
    def setUp(self):
        from threading import Event
        self.event = Event()
        token = mod._cancellation_event.set(self.event)
        self.addCleanup(mod._cancellation_event.reset, token)

    def test_cancel_before_query_and_fetch(self):
        self.event.set()
        with patch.object(mod, "_get_tavily_client") as client, patch.object(mod.requests.Session, "get") as get:
            result = mod.search_detailed("annual production")
            self.assertEqual(mod.search("annual production"), [])
            with self.assertRaises(mod._RetrievalCancelled):
                mod._fetch_page("https://public.example")
        client.assert_not_called(); get.assert_not_called()
        self.assertTrue(result["diagnostics"]["cancelled"])
        self.assertFalse(result["diagnostics"]["timed_out"])
        self.assertFalse(result["diagnostics"]["partial_result"])

    def test_after_query_no_next_query_or_cache_write(self):
        event = self.event
        calls = []
        class Client:
            def search(self, timeout=5, **kwargs):
                calls.append(kwargs)
                event.set()
                return {"results": [{"url": "https://public.example", "content": TEXT}]}
        cache = mod._TavilyQueryCache()
        cache.enabled = True
        cache.put("previous", {"results": [{"url": "https://old.example"}]})
        with patch.object(mod, "_get_tavily_client", return_value=Client()), patch.object(mod, "_tavily_cache", cache):
            result = mod.search_detailed("Annual production in 2024")
        self.assertEqual(len(calls), 1)
        self.assertEqual(list(cache._items), ["previous"])
        self.assertEqual(result["sources"], [])
        self.assertTrue(result["diagnostics"]["cancelled"])

    def test_stream_and_redirect_closure(self):
        for redirect in (False, True):
            self.event.clear()
            resp = response(302, "/next") if redirect else response()
            consumed = []
            def chunks(**kwargs):
                consumed.append(1)
                self.event.set()
                yield b"<p>incomplete"
                consumed.append(2)
                yield b"body</p>"
            resp.iter_content.side_effect = chunks
            if redirect:
                def close(*args): self.event.set()
                resp.__exit__.side_effect = close
            with patch.object(mod.socket, "getaddrinfo", return_value=answers(PUBLIC)), \
                 patch.object(mod.requests.Session, "get", return_value=resp) as get:
                with self.assertRaises(mod._RetrievalCancelled):
                    mod._fetch_page("https://public.example")
            self.assertEqual(get.call_count, 1)
            resp.__exit__.assert_called_once()
            self.assertEqual(consumed, [] if redirect else [1])

    def test_ranking_commit_and_chunking_checkpoints(self):
        original = mod._remaining
        for stage in ("chunking", "ranking", "partial_commit"):
            self.event.clear()
            snapshots = []
            def check(current):
                if current == stage:
                    snapshots.append(deepcopy(mod._partial_state.get()["snapshot"]))
                    self.event.set()
                return original(current)
            row = {"url": "https://public.example", "title": "annual production", "content": TEXT, "tavily_score": .9}
            with patch.object(mod, "_search_web", return_value=([row], ["annual production"])), \
                 patch.object(mod, "_fetch_page", return_value=TEXT), patch.object(mod, "_remaining", side_effect=check):
                result = mod.search_detailed("annual production")
            self.assertTrue(snapshots, stage)
            self.assertEqual(result["sources"], [])
            self.assertTrue(result["diagnostics"]["cancelled"])
            self.assertEqual(result["diagnostics"]["cancellation_stage"], stage)
            self.assertFalse(result["diagnostics"]["partial_result"])

    def test_cancel_discards_existing_snapshot_timeout_does_not(self):
        def run(*args):
            mod._partial_state.get()["snapshot"] = [{"url": "https://committed.example"}]
            self.event.set()
            mod._remaining("ranking")
        with patch.object(mod, "_search_detailed_impl", side_effect=run):
            result = mod.search_detailed("claim")
        self.assertEqual(result["sources"], [])
        self.event.clear()
        def timeout(*args):
            mod._partial_state.get()["snapshot"] = [{"url": "https://committed.example"}]
            raise mod._RetrievalTimeout("ranking")
        with patch.object(mod, "_search_detailed_impl", side_effect=timeout):
            result = mod.search_detailed("claim")
        self.assertTrue(result["sources"])
        self.assertTrue(result["diagnostics"]["timed_out"])
        self.assertFalse(result["diagnostics"]["cancelled"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
