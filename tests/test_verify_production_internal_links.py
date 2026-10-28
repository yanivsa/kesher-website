from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-production-internal-links.py"


class _Handler(BaseHTTPRequestHandler):
    routes: dict[str, tuple[int, str]] = {}

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        status, body = self.routes.get(self.path, (404, "not found"))
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format: str, *_args: object) -> None:
        return


class VerifyProductionInternalLinksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address
        cls.base_url = f"http://{host}:{port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.server_close()

    def _run(self, routes: dict[str, tuple[int, str]]) -> subprocess.CompletedProcess[str]:
        _Handler.routes = routes
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.json"
            plan.write_text(
                json.dumps([{"source": "source", "targets": ["target"]}]),
                encoding="utf-8",
            )
            return subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--base-url",
                    self.base_url,
                    "--plan",
                    str(plan),
                    "--retries",
                    "1",
                    "--delay",
                    "0",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=15,
                check=False,
            )

    def test_passes_when_source_contains_exact_link_and_target_is_public(self) -> None:
        result = self._run(
            {
                "/blog/source": (200, '<a href="/blog/target">target</a>'),
                "/blog/target": (200, "ok"),
            }
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1/1 planned links verified", result.stdout)

    def test_fails_when_planned_link_is_missing(self) -> None:
        result = self._run(
            {
                "/blog/source": (200, "<p>no planned link</p>"),
                "/blog/target": (200, "ok"),
            }
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected exactly once", result.stdout + result.stderr)

    def test_fails_when_planned_link_is_duplicated(self) -> None:
        result = self._run(
            {
                "/blog/source": (
                    200,
                    '<a href="/blog/target">one</a><a href="/blog/target">two</a>',
                ),
                "/blog/target": (200, "ok"),
            }
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("found 2", result.stdout + result.stderr)

    def test_fails_when_target_is_not_public(self) -> None:
        result = self._run(
            {
                "/blog/source": (200, '<a href="/blog/target">target</a>'),
                "/blog/target": (404, "missing"),
            }
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("target returned HTTP 404", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
