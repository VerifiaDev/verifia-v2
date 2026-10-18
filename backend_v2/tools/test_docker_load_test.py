"""Offline safety checks for the standalone probe; no backend or Docker required."""
import argparse
from contextlib import contextmanager
import http.server
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from tools import docker_load_test as probe


@contextmanager
def server():
    seen = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append((self.path, None))
            if self.path == '/redirect':
                self.send_response(302)
                self.send_header('Location', '/paid')
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"degraded"}')

        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length']))
            seen.append((self.path, body))
            self.send_response(429)
            self.send_header('Retry-After', '30')
            self.end_headers()
            self.wfile.write(b'{"error":"RATE_LIMITED"}')

        def log_message(self, *args):
            pass

    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{srv.server_port}', seen
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join()


class ProbeTests(unittest.TestCase):
    def test_restricts_target(self):
        for url in ('https://127.0.0.1:80', 'http://example.com:80',
                    'http://127.0.0.1:80/health', 'http://user@127.0.0.1:80',
                    'http://127.0.0.1:99999', 'http://127.0.0.1'):
            with self.subTest(url=url), self.assertRaises(argparse.ArgumentTypeError):
                probe.local_url(url)

    def test_no_redirect_and_expected_responses(self):
        with server() as (base, seen):
            self.assertFalse(probe.request(base, '/health')['unexpected'])
            row = probe.request(base, '/verify', True)
            self.assertFalse(row['unexpected'])
            self.assertEqual(row['retry_after'], '30')
            self.assertTrue(probe.request(base, '/redirect')['unexpected'])
            self.assertNotIn(('/paid', None), seen)
            self.assertIn(('/verify', b'{}'), seen)

    def test_memory_stop_and_failure(self):
        monitor = probe.MemoryMonitor('test')
        with patch.object(probe, 'docker', return_value=json.dumps({'current': 320*1024**2, 'peak': None})):
            monitor.sample()
        self.assertTrue(monitor.abort.is_set())
        monitor = probe.MemoryMonitor('test')
        with patch.object(probe, 'docker', side_effect=OSError):
            monitor.sample()
        self.assertTrue(monitor.abort.is_set())
        self.assertEqual(monitor.errors, ['OSError'])

    def test_full_http_only_run_is_bounded_and_not_docker_success(self):
        with server() as (base, seen), tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / 'report.md'
            with patch('sys.argv', ['probe', '--url', base, '--report', str(report)]), \
                    patch.object(probe.shutil, 'which', return_value=None):
                self.assertEqual(probe.main(), 1)  # incomplete Docker measurement
            data = json.loads(report.read_text(encoding='utf-8').split('```json\n')[1].split('```')[0])
            self.assertEqual(len(seen), 72)
            self.assertEqual([p['concurrency'] for p in data['phases']], [1, 2, 4])
            self.assertEqual(data['docker'], {})
            self.assertTrue(data['notes'])
            self.assertTrue(all(body == b'{}' for _, body in seen if body is not None))
            self.assertTrue(all(path in ('/', '/health', '/verify', '/verify/stream') for path, _ in seen))


if __name__ == '__main__':
    unittest.main()
