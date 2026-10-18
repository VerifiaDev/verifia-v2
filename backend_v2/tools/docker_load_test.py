"""Bounded, standard-library-only local HTTP/RAM probe. Never sends valid AI input."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def local_url(value):
    p = urllib.parse.urlsplit(value)
    if (p.scheme != 'http' or p.hostname != '127.0.0.1' or p.username or p.password
            or p.path not in ('', '/') or p.query or p.fragment):
        raise argparse.ArgumentTypeError('Only http://127.0.0.1:PORT is permitted')
    try:
        if not p.port:
            raise ValueError()
    except ValueError:
        raise argparse.ArgumentTypeError('An explicit valid port is required') from None
    return value.rstrip('/')


def request(base, path, post=False):
    start = time.perf_counter()
    result = dict(path=path, status=None, error=None, retry_after=None, unexpected=True)
    # Ignore environment proxies; never follow redirects, including to paid services.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    req = urllib.request.Request(base + path, data=b'{}' if post else None,
                                 headers={'Content-Type': 'application/json'})
    try:
        try:
            response = opener.open(req, timeout=3)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            result['status'] = response.code
            result['retry_after'] = response.headers.get('Retry-After')
            raw = response.read(65537)
            body = json.loads(raw) if len(raw) <= 65536 else {}
            result['error'] = body.get('error') if isinstance(body, dict) else None
            result['unexpected'] = not (
                (not post and response.code == 200)
                or (post and (response.code, result['error']) in {
                    (422, 'VALIDATION_ERROR'), (429, 'RATE_LIMITED'),
                    (429, 'BUSY'), (503, 'LOW_MEMORY')})
            )
            if response.code == 429 and not (result['retry_after'] or '').isdigit():
                result['unexpected'] = True
    except (OSError, ValueError, urllib.error.URLError) as exc:
        result['error'] = type(exc).__name__
    result['ms'] = round((time.perf_counter() - start) * 1000, 3)
    return result


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, timeout=5,
                                   stderr=subprocess.PIPE).strip()


CGROUP = """import json,pathlib
def read(paths):
 for name in paths:
  try: return int(pathlib.Path(name).read_text())
  except (OSError,ValueError): pass
 return None
print(json.dumps({'current':read(['/sys/fs/cgroup/memory.current','/sys/fs/cgroup/memory/memory.usage_in_bytes']), 'peak':read(['/sys/fs/cgroup/memory.peak','/sys/fs/cgroup/memory/memory.max_usage_in_bytes'])}))
"""


class MemoryMonitor:
    def __init__(self, container):
        self.container = container
        self.samples = []
        self.errors = []
        self.stop = threading.Event()
        self.abort = threading.Event()

    def sample(self):
        try:
            sample = json.loads(docker('exec', self.container, 'python', '-c', CGROUP))
            if not isinstance(sample.get('current'), int):
                raise ValueError('cgroup memory usage unavailable')
            self.samples.append(sample)
            if sample['current'] >= 320 * 1024**2:
                self.abort.set()
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            self.errors.append(type(exc).__name__)
            self.abort.set()  # stop adding load when RAM monitoring is lost

    def run(self):
        while not self.stop.wait(1):
            self.sample()


def summary(rows):
    lat = sorted(r['ms'] for r in rows)
    return dict(requests=len(rows), http=dict(Counter(str(r['status']) for r in rows)),
                errors=dict(Counter(r['error'] for r in rows if r['error'])),
                retry_after=dict(Counter(r['retry_after'] for r in rows if r['retry_after'])),
                transport_errors=sum(r['status'] is None for r in rows),
                http_5xx=sum((r['status'] or 0) >= 500 for r in rows),
                http_4xx=sum(400 <= (r['status'] or 0) < 500 for r in rows),
                transport_error_rate_pct=round(100 * sum(r['status'] is None for r in rows) / len(rows), 2),
                http_5xx_rate_pct=round(100 * sum((r['status'] or 0) >= 500 for r in rows) / len(rows), 2),
                http_4xx_rate_pct=round(100 * sum(400 <= (r['status'] or 0) < 500 for r in rows) / len(rows), 2),
                unexpected_rate_pct=round(100 * sum(r['unexpected'] for r in rows) / len(rows), 2),
                p50_ms=lat[math.ceil(len(lat)*.5)-1],
                p95_ms=lat[math.ceil(len(lat)*.95)-1], max_ms=lat[-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', type=local_url, default='http://127.0.0.1:18001')
    parser.add_argument('--container', default='verifia-health-test')
    parser.add_argument('--report', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'LOAD_TEST_REPORT.md')
    args = parser.parse_args()
    started = time.monotonic()
    info, notes, phases = {}, [], []
    monitor = None
    if shutil.which('docker'):
        try:
            obj = json.loads(docker('inspect', args.container))[0]
            port = str(urllib.parse.urlsplit(args.url).port)
            bindings = obj['NetworkSettings']['Ports'].get('8000/tcp') or []
            if not any(b['HostPort'] == port for b in bindings):
                raise ValueError('Target port does not match container port 8000')
            limit = obj['HostConfig']['Memory']
            if limit != 512 * 1024**2 or not obj['State']['Running']:
                raise ValueError('A running container limited to exactly 512 MiB is required')
            info = dict(image=obj['Config']['Image'], memory_limit_bytes=limit,
                        health_before=obj['State'].get('Health', {}).get('Status'))
            monitor = MemoryMonitor(args.container)
            monitor.sample()
        except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as exc:
            notes.append('Docker preflight failed; HTTP load skipped: ' + str(exc))
            info['preflight_failed'] = True
    else:
        notes.append('Docker CLI unavailable: HTTP-only run; Docker RAM/health/OOM NOT measured.')
    thread = None
    if monitor and not monitor.abort.is_set():
        thread = threading.Thread(target=monitor.run, daemon=True)
        thread.start()
    try:
        if not info.get('preflight_failed'):
            with ThreadPoolExecutor(max_workers=4) as pool:
                for concurrency in (1, 2, 4):
                    rows = []
                    phase_start = time.monotonic()
                    # Six bounded waves: 24 requests per phase, 72 total, 36 POSTs.
                    for wave in range(6):
                        if time.monotonic() - started >= 60 or (monitor and monitor.abort.is_set()):
                            notes.append('Safety stop: time budget, memory threshold or monitor failure.')
                            break
                        jobs = [('/health', False), ('/', False),
                                ('/verify', True), ('/verify/stream', True)]
                        for offset in range(0, 4, concurrency):
                            if monitor and monitor.abort.is_set():
                                break
                            futures = [pool.submit(request, args.url, path, post)
                                       for path, post in jobs[offset:offset+concurrency]]
                            rows.extend(f.result() for f in futures)
                        time.sleep(.25)
                    if rows:
                        phases.append(dict(concurrency=concurrency,
                                           wall_s=round(time.monotonic()-phase_start, 3),
                                           throughput_rps=round(len(rows)/(time.monotonic()-phase_start), 3),
                                           endpoints={p: summary([r for r in rows if r['path'] == p])
                                                      for p in sorted({r['path'] for r in rows})}))
                    if time.monotonic() - started >= 60 or (monitor and monitor.abort.is_set()):
                        break
    finally:
        if monitor:
            monitor.stop.set()
            if thread:
                thread.join(timeout=6)
            monitor.sample()
    if monitor:
        info['ram_samples'] = monitor.samples
        info['monitor_errors'] = monitor.errors
        try:
            state = json.loads(docker('inspect', '--format', '{{json .State}}', args.container))
            info.update(health_after=state.get('Health', {}).get('Status'),
                        oom_killed_after=state.get('OOMKilled'), running_after=state.get('Running'))
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            notes.append('Final Docker state unavailable: ' + type(exc).__name__)
    result = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(), url=args.url,
                  container=args.container, docker=info, phases=phases, notes=notes)
    text = '# Docker yük / RAM testi\n\n'
    text += ('Bu dosya araç tarafından üretilmiştir. Geçerli AI girdisi ve /health/deep kullanılmadı. '
             'POST gövdesi yalnızca `{}`; 422 ve 429 kontrollü retlerdir. '
             '503 LOW_MEMORY ayrıca 5xx sayısında gösterilir; kapasite başarısı değildir.\n\n'
             'En fazla 72 istek, 4 eşzamanlı istek, istek başına 3s timeout; 60s yük kabul bütçesi '
             '(son dalga ve Docker ölçümleri ek süre alabilir). RAM >=320 MiB olduğunda yeni yük durur; '
             'bu örneklemeli bir korumadır, OOM olmayacağı garantisi değildir. '
             'cgroup current container belleğidir (RSS değildir); örneklenmiş maksimum alt sınırdır. '
             'cgroup peak container ömrüne aittir, yalnızca bu teste ait değildir. '
             'Ölçüm docker exec Python sürecinin küçük ek maliyetini içerir.\n\n'
             'BUSY/RATE_LIMITED yalnızca hata kodu sayımlarında gözlenirse raporlanır; '
             'gözlenmemesi limitlerin doğrulandığı anlamına gelmez. Kota pencere sınırları ve önceki '
             'trafik sonuçları etkiler; araç Retry-After bekleyip yeniden denemez veya kota aşmaz. '
             'Gerçek AI, SSE akışı, uzun işlem kapasitesi, OOM ve bellek sızıntısı test edilmedi.\n\n')
    if monitor and monitor.samples:
        current = [s['current']/1024**2 for s in monitor.samples]
        peaks = [s['peak']/1024**2 for s in monitor.samples if s.get('peak') is not None]
        text += f'RAM MiB: önce={current[0]:.2f}, örneklenen maksimum={max(current):.2f}, sonra={current[-1]:.2f}. '
        text += f'Container ömrü tepe MiB: {max(peaks) if peaks else "ölçülemedi"}.\n\n'
    text += 'Gecikmeler istemci uçtan uca süreleridir; p50/p95 nearest-rank ile hesaplanır.\n\n```json\n'
    text += json.dumps(result, ensure_ascii=False, indent=2) + '\n```\n'
    args.report.write_text(text, encoding='utf-8')
    print(f'Report: {args.report}')
    bad = (not phases or notes or (monitor and monitor.abort.is_set())
           or any(s['unexpected_rate_pct'] or s['http_5xx'] for p in phases for s in p['endpoints'].values())
           or (monitor and (info.get('oom_killed_after') or not info.get('running_after')
                            or info.get('health_after') != 'healthy')))
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
