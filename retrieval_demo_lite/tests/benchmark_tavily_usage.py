"""Offline usage benchmark. Prototype only; production modules are never edited.

Run: python3 -B retrieval_demo_lite/tests/benchmark_tavily_usage.py
Cache-adjusted counters are benchmark observations, not production diagnostics.
"""
from collections import OrderedDict, defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import json
import platform
from pathlib import Path
import re
import socket
import sys
import threading
import time
import unicodedata
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'retrieval_demo_lite'))
import search_retrieval_lite as mod

ACTIVE = ContextVar('benchmark_measurement', default=None)
GENERATING = ContextVar('benchmark_generating', default=False)
TEXT = 'Annual production growth increased in 2024 according to the published report. ' * 15
CLAIM = 'Annual production growth in 2024'
PARAMS = dict(search_depth='basic', max_results=5, include_raw_content=False)


class Cache:
    def __init__(self):
        self.ttl = 60
        self.max_entries = 128
        self.budget = 4 * 1024 * 1024
        self.entry_max = 128 * 1024
        self.items = OrderedDict()
        self.lock = threading.Lock()
        self.offset = 0
        self.evictions = 0
        self.expired = 0
        self.oversize = 0
        self.peak_bytes = 0
        self.peak_entries = 0

    @staticmethod
    def key(query, params):
        query = re.sub(r'\s+', ' ', unicodedata.normalize('NFC', query)).strip()
        return json.dumps(['tavily', 1, query, params], sort_keys=True, ensure_ascii=False)

    def get(self, key):
        with self.lock:
            item = self.items.get(key)
            if item is None:
                return None
            expires, data = item
            if expires <= time.monotonic() + self.offset:
                del self.items[key]
                self.expired += 1
                return None
            self.items.move_to_end(key)
        return json.loads(data)

    def put(self, key, response):
        rows = mod._provider_rows(response)
        if not rows:
            return
        data = json.dumps(response, ensure_ascii=False).encode()
        with self.lock:
            if len(data) > self.entry_max:
                self.oversize += 1
                return
            now = time.monotonic() + self.offset
            for old in list(self.items):
                if self.items[old][0] <= now:
                    del self.items[old]
                    self.expired += 1
            self.items[key] = (now + self.ttl, data)
            self.items.move_to_end(key)
            while len(self.items) > self.max_entries or self.bytes() > self.budget:
                self.items.popitem(last=False)
                self.evictions += 1
            self.peak_bytes = max(self.peak_bytes, self.bytes())
            self.peak_entries = max(self.peak_entries, len(self.items))

    def bytes(self):
        return sum(len(data) for _, data in self.items.values())

    def stats(self):
        with self.lock:
            return dict(cache_entry_count=len(self.items), approximate_serialized_cache_bytes=self.bytes(),
                        peak_entries=self.peak_entries, peak_serialized_bytes=self.peak_bytes,
                        evictions=self.evictions, expired=self.expired, oversized_entries_rejected=self.oversize)


def payload(query):
    tag = hashlib.sha256(query.encode()).hexdigest()[:12]
    return {'results': [dict(url=f'https://evidence.example/{suffix}', title='Annual production report',
                             content=TEXT, score=0.9) for suffix in ('shared', tag)]}


class Response:
    status_code = 200
    headers = {'Content-Type': 'text/html'}
    encoding = 'utf-8'
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def raise_for_status(self): pass
    def iter_content(self, chunk_size):
        data = ('<article>' + TEXT + '</article>').encode()
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]


def http_get(session, url, **kwargs):
    assert session.trust_env is False
    assert kwargs['stream'] is True and kwargs['allow_redirects'] is False
    ACTIVE.get()['fetch_count'] += 1
    return Response()


def failure(kind):
    from tavily import errors
    if kind in ('429', '5xx', 'auth'):
        response = mod.requests.Response()
        response.status_code = {'429': 429, '5xx': 503, 'auth': 401}[kind]
        return mod.requests.HTTPError('fixture', response=response)
    if kind == 'usage_limited': return errors.UsageLimitExceededError('fixture')
    if kind == 'timeout': return mod.requests.Timeout('fixture')
    return RuntimeError('fixture')


def run_mode(name, claims, enabled, kind='success', concurrent=False, prefill=None, params_change=False):
    cache = Cache()
    if prefill:
        size = 100_000 if prefill == 'bytes' else 100
        count = 43 if prefill == 'bytes' else 128
        for i in range(count):
            cache.put(cache.key(f'prefill {i}', PARAMS), {'results': [{'content': 'x' * size}]})
    barrier = threading.Barrier(2) if concurrent else None
    original_search, original_generate, original_unique = mod._tavily_search, mod.generate_queries, mod._unique

    failing_query = original_generate(CLAIM)[1]

    class Client:
        def search(self, query, timeout=5, **params):
            m = ACTIVE.get()
            m['actual_calls'] += 1
            if barrier and m['actual_calls'] == 1:
                barrier.wait(timeout=5)
            if kind == 'deadline':
                mod._total_deadline.set(time.monotonic() - 1)
            if kind == 'mixed' and query == failing_query:
                raise failure('429')
            if kind not in ('success', 'mixed', 'zero', 'malformed', 'deadline'):
                raise failure(kind)
            if kind == 'zero': return {'results': []}
            if kind == 'malformed': return {'results': 'invalid'}
            return payload(query)

    def unique(values):
        values = list(values)
        answer = original_unique(values)
        if GENERATING.get():
            ACTIVE.get()['generated_query_count'] = len(values)
            ACTIVE.get()['unique_query_count'] = len(answer)
        return answer

    def generate(claim, frame=None):
        token = GENERATING.set(True)
        try:
            answer = original_generate(claim, frame)
            ACTIVE.get()['planned_query_count'] = len(answer)
            return answer
        finally:
            GENERATING.reset(token)

    def search(client, _on_start=None, **kwargs):
        m = ACTIVE.get()
        started = time.monotonic()
        record = dict(position=len(m['queries']) + 1, query=kwargs['query'], raw_result_count=0,
                      new_unique_url_count=0, duplicate_url_count=0, final_selected_source_contribution=0,
                      cache_hit=False, provider_started=False)
        m['queries'].append(record)
        params = {k: v for k, v in kwargs.items() if k != 'query'}
        if params_change and m['invocation'] == 1:
            params['max_results'] += 1
        key = cache.key(kwargs['query'], params)
        try:
            mod._remaining('tavily')
            response = cache.get(key) if enabled else None
            if response is not None:
                record['cache_hit'] = True
                m['cache_hit_count'] += 1
            else:
                if enabled: m['cache_miss_count'] += 1
                def start():
                    record['provider_started'] = True
                    if _on_start: _on_start()
                try:
                    response = original_search(client, _on_start=start, query=kwargs['query'], **params)
                    rows = mod._provider_rows(response)
                except Exception as exc:
                    if record['provider_started']:
                        m['failed_query_count'] += 1
                        record['error_kind'] = mod._classify_provider_error(exc)[0]
                    raise
                m['successful_query_count'] += 1
                m['provider_result_count'] += len(rows)
                if enabled:
                    mod._remaining('tavily')
                    cache.put(key, response)
            rows = mod._provider_rows(response)
            record['raw_result_count'] = len(rows)
            for row in rows:
                url = mod._canonical_url(row.get('url', ''))
                if url in m['seen']:
                    record['duplicate_url_count'] += 1
                else:
                    m['seen'][url] = record['position']
                    record['new_unique_url_count'] += 1
            return response
        finally:
            record['query_latency_seconds'] = time.monotonic() - started

    def invoke(index, claim):
        m = dict(invocation=index, claim=claim, actual_calls=0, successful_query_count=0, failed_query_count=0,
                 provider_result_count=0, cache_hit_count=0, cache_miss_count=0, fetch_count=0, queries=[], seen={})
        token = ACTIVE.set(m)
        started = time.monotonic()
        try:
            result = mod.search_detailed(claim)
            m['latency_seconds'] = time.monotonic() - started
            m['sources'] = result['sources']
            m['production_diagnostics'] = result['diagnostics']
            m['tavily_query_count'] = m.pop('actual_calls')
            m['skipped_query_count'] = result['diagnostics']['skipped_query_count']
            m['deduplicated_result_count'] = result['diagnostics']['raw_search_results']
            m['avoided_provider_call_count'] = m['cache_hit_count']
            for source in result['sources']:
                position = m['seen'].get(mod._canonical_url(source['url']))
                if position: m['queries'][position - 1]['final_selected_source_contribution'] += 1
            del m['seen']
            assert m['tavily_query_count'] == m['successful_query_count'] + m['failed_query_count']
            return m
        finally:
            ACTIVE.reset(token)

    dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))]
    isolated_cache = mod._TavilyQueryCache()
    isolated_cache.enabled = False
    with patch.object(mod, '_tavily_cache', isolated_cache), \
         patch.object(mod, '_get_tavily_client', return_value=Client()), \
         patch.object(mod, '_tavily_search', side_effect=search), \
         patch.object(mod, 'generate_queries', side_effect=generate), \
         patch.object(mod, '_unique', side_effect=unique), \
         patch.object(mod.socket, 'getaddrinfo', return_value=dns), \
         patch.object(mod.requests.Session, 'get', http_get):
        if concurrent:
            with ThreadPoolExecutor(max_workers=2) as pool:
                measurements = list(pool.map(lambda pair: invoke(*pair), enumerate(claims)))
        else:
            measurements = []
            for index, claim in enumerate(claims):
                if name == 'ttl_expired' and index: cache.offset += 61
                measurements.append(invoke(index, claim))
    counts = defaultdict(int)
    for m in measurements:
        for q in m['queries']:
            if q['provider_started']: counts[q['query']] += 1
    return dict(cache_enabled=enabled, claims=measurements, cache=cache.stats(),
                duplicate_provider_calls=sum(max(0, n-1) for n in counts.values()) if concurrent else 0)


def main():
    production = [ROOT / 'retrieval_demo_lite/search_retrieval_lite.py', ROOT / 'backend_v2/app/retrieval.py']
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in production}
    specs = [
        ('all_different', [CLAIM], {}),
        ('exact_duplicate', ['annual production growth'], {}),
        ('whitespace_duplicate', ['annual   production growth', 'annual production growth'], {}),
        ('turkish_distinct', [f'annual production {s}' for s in ('ı','i','İ','I','ç','c','ş','s','ğ','g','ö','o','ü','u')], {}),
        ('repeated_claim', [CLAIM, CLAIM], {}),
        ('cross_claim_same_query', [CLAIM, CLAIM + '.'], {}),
        ('zero', [CLAIM, CLAIM], {'kind':'zero'}),
        ('429', [CLAIM, CLAIM], {'kind':'429'}),
        ('5xx', [CLAIM, CLAIM], {'kind':'5xx'}),
        ('timeout', [CLAIM, CLAIM], {'kind':'timeout'}),
        ('mixed', [CLAIM, CLAIM], {'kind':'mixed'}),
        ('ttl_expired', [CLAIM, CLAIM], {}),
        ('max_entry_eviction', [CLAIM], {'prefill':'entries'}),
        ('byte_budget_eviction', [CLAIM], {'prefill':'bytes'}),
        ('concurrent_cold_miss', [CLAIM, CLAIM], {'concurrent':True}),
        ('parameter_change', [CLAIM, CLAIM], {'params_change':True}),
    ] + [(kind, [CLAIM, CLAIM], {'kind':kind}) for kind in ('usage_limited','auth','provider_error','malformed','deadline')]
    scenarios = []
    for name, claims, options in specs:
        baseline = run_mode(name, claims, False, **options)
        cached = run_mode(name, claims, True, **options)
        equal = [m['sources'] for m in baseline['claims']] == [m['sources'] for m in cached['claims']]
        assert equal, name
        if options.get('kind') in ('zero','429','5xx','timeout','usage_limited','auth','provider_error','malformed','deadline'):
            assert cached['cache']['cache_entry_count'] == 0, name
        if name in ('ttl_expired','parameter_change'):
            assert sum(m['cache_hit_count'] for m in cached['claims']) == 0
        if 'eviction' in name: assert cached['cache']['evictions'] > 0
        scenarios.append(dict(name=name, without_cache=baseline, with_cache=cached, exact_equality=equal))
        print(name, 'OK', flush=True)
    # Cache key semantics and admission probes, independent of production query dedup.
    variants = ('ı','i','İ','I','ç','c','ş','s','ğ','g','ö','o','ü','u')
    assert len({Cache.key(q, PARAMS) for q in variants}) == len(variants)
    assert Cache.key('a  b', PARAMS) == Cache.key('a b', PARAMS)
    assert Cache.key('é', PARAMS) == Cache.key('e\u0301', PARAMS)
    assert Cache.key('a?', PARAMS) != Cache.key('a', PARAMS)
    probe = Cache()
    probe.put('oversize', {'results':[{'content':'x' * (129 * 1024)}]})
    assert probe.stats()['cache_entry_count'] == 0
    probe.put('isolation', payload('probe'))
    retrieved = probe.get('isolation'); retrieved['results'].clear()
    assert probe.get('isolation')['results']
    before_count = sum(m['tavily_query_count'] for s in scenarios for m in s['without_cache']['claims'])
    after_count = sum(m['tavily_query_count'] for s in scenarios for m in s['with_cache']['claims'])
    contributions = defaultdict(lambda: dict(new_urls=0, duplicates=0, selected_source_contribution=0))
    for s in scenarios:
        for m in s['without_cache']['claims']:
            for q in m['queries']:
                row = contributions[q['position']]
                row['new_urls'] += q['new_unique_url_count']
                row['duplicates'] += q['duplicate_url_count']
                row['selected_source_contribution'] += q['final_selected_source_contribution']
    assert before == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in production}
    output = dict(environment=dict(python=sys.version, platform=platform.platform(), network='mocked only', production_sha256=before),
        config=dict(ttl_seconds=60,max_entries=128,serialized_budget=4*1024*1024,entry_max=128*1024,
                    max_queries=mod.MAX_QUERY_COUNT,results_per_query=mod.SEARCH_RESULTS_PER_QUERY),
        methodology=dict(counters='Benchmark-observed actual SDK calls; production diagnostics retained separately and count cache returns as success because production has no cache integration.',
                         generation='Real generate_queries and _unique, captured before/after dedup.',
                         latency='Real monotonic time; mocked network has no artificial latency.',
                         freshness='Cache hit is not live search. TTL expiry uses cache-only clock offset.',
                         prefill='Eviction fixtures are setup only, excluded from provider-call savings.',
                         contribution='First-seen canonical URL attribution, not a relevance improvement metric.'),
        scenarios=scenarios, summary=dict(exact_equality_all=True,error_cache_policy_verified=True,production_unchanged=True,
                                          query_contribution=dict(contributions),key_and_mutation_probes_passed=True),
        cache_savings=dict(provider_calls_without_cache=before_count,provider_calls_with_cache=after_count,
                           avoided_provider_calls=before_count-after_count,avoided_call_percentage=100*(before_count-after_count)/before_count),
        concurrent_cold_miss_duplicate_count=next(s['with_cache']['duplicate_provider_calls'] for s in scenarios if s['name']=='concurrent_cold_miss'))
    target = Path(__file__).with_name('benchmark_results_tavily_usage.json')
    if target.exists(): raise FileExistsError('Preserving existing benchmark output')
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(output['cache_savings']))


if __name__ == '__main__':
    main()
