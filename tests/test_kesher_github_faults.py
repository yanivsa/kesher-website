"""Real HTTP fault injection at the transport boundary; no external API calls."""
import contextlib
import json
import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from scripts.kesher_runtime.github import GitHub, GitHubError


@contextlib.contextmanager
def fault_server(responses):
    observed = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            observed.append({'method': self.command, 'path': self.path,
                             'body': json.loads(body) if body else None})
            response = responses[min(len(observed) - 1, len(responses) - 1)]
            if response == 'accepted_then_disconnect':
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            status, payload, headers = response
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(payload.encode())

        do_GET = respond
        do_POST = respond
        do_PUT = respond

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    sleeps = []
    github = GitHub('test-only-token', api_root=f'http://127.0.0.1:{server.server_port}', sleeper=sleeps.append)
    try:
        yield github, observed, sleeps
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class GitHubFaultTests(unittest.TestCase):
    def test_accepted_dispatch_with_lost_response_is_not_repeated(self):
        with fault_server(['accepted_then_disconnect']) as (github, observed, sleeps):
            with self.assertRaises(GitHubError) as raised:
                github.request('POST', '/repos/owner/repo/actions/workflows/media.yml/dispatches',
                               {'ref': 'main', 'inputs': {'command_id': 'exact-intent'}})
            self.assertTrue(raised.exception.uncertain)
            self.assertEqual(len(observed), 1)
            self.assertEqual(sleeps, [])

    def test_accepted_state_write_with_lost_response_is_not_repeated(self):
        with fault_server(['accepted_then_disconnect']) as (github, observed, _):
            with self.assertRaises(GitHubError) as raised:
                github.request('PUT', '/repos/owner/repo/contents/state.json', {'sha': 'observed'})
            self.assertTrue(raised.exception.uncertain)
            self.assertEqual(len(observed), 1)

    def test_read_429_and_500_back_off_then_recover(self):
        with fault_server([(429, '{}', {'Retry-After': '3'}), (500, '{}', {}), (200, '{"ok":true}', {})]) as (github, observed, sleeps):
            self.assertEqual(github.request('GET', '/repos/owner/repo'), {'ok': True})
            self.assertEqual(len(observed), 3)
            self.assertEqual(sleeps, [3, 2])

    def test_persistent_read_failure_has_a_finite_budget(self):
        with fault_server([(500, '{}', {})]) as (github, observed, sleeps):
            with self.assertRaises(GitHubError):
                github.request('GET', '/repos/owner/repo')
            self.assertEqual(len(observed), 4)
            self.assertEqual(sleeps, [1, 2, 4])

    def test_auth_failures_are_not_spent_as_transient_retries(self):
        for status in (401, 403):
            with self.subTest(status=status), fault_server([(status, '{}', {})]) as (github, observed, sleeps):
                with self.assertRaises(GitHubError) as raised:
                    github.request('GET', '/repos/owner/repo')
                self.assertEqual(raised.exception.status, status)
                self.assertFalse(raised.exception.uncertain)
                self.assertEqual(len(observed), 1)
                self.assertEqual(sleeps, [])

    def test_long_rate_limit_is_returned_to_durable_scheduler(self):
        with fault_server([(429, '{}', {'Retry-After': '600'})]) as (github, observed, sleeps):
            with self.assertRaises(GitHubError) as raised:
                github.request('GET', '/repos/owner/repo')
            self.assertEqual(raised.exception.retry_after, 600)
            self.assertEqual(len(observed), 1)
            self.assertEqual(sleeps, [])

    def test_mutation_http_failure_or_invalid_response_requires_reconciliation(self):
        for response in [(500, '{}', {}), (200, 'truncated-json{', {})]:
            with self.subTest(response=response), fault_server([response]) as (github, observed, _):
                with self.assertRaises(GitHubError) as raised:
                    github.request('POST', '/repos/owner/repo/actions/workflows/test.yml/dispatches', {'ref': 'main'})
                self.assertTrue(raised.exception.uncertain)
                self.assertEqual(len(observed), 1)

    def test_cas_conflict_and_mutating_404_are_not_silently_retried(self):
        for status in (409, 404):
            with self.subTest(status=status), fault_server([(status, '{}', {})]) as (github, observed, _):
                with self.assertRaises(GitHubError) as raised:
                    github.request('PUT', '/repos/owner/repo/contents/state.json', {'sha': 'old'}, allow_404=True)
                self.assertEqual(raised.exception.status, status)
                self.assertFalse(raised.exception.uncertain)
                self.assertEqual(len(observed), 1)


if __name__ == '__main__':
    unittest.main()
