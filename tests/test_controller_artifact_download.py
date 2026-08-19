from __future__ import annotations

import email.message
import unittest
import urllib.error
from unittest import mock

from scripts import kesher_content_controller as controller


class _FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


class _RedirectingOpener:
    def __init__(self, location: str):
        self.location = location
        self.requests = []

    def open(self, request, timeout=45):
        self.requests.append(request)
        headers = email.message.Message()
        headers["Location"] = self.location
        raise urllib.error.HTTPError(request.full_url, 302, "Found", headers, None)


class ControllerArtifactDownloadTests(unittest.TestCase):
    def test_signed_blob_redirect_drops_github_authorization_header(self):
        client = controller.GitHubClient("yanivsa/kesher-website", "github-secret")
        signed = "https://blob.example.invalid/state.zip?sig=redacted"
        opener = _RedirectingOpener(signed)
        captured = {}

        def signed_open(request, timeout=60):
            captured["url"] = request.full_url
            captured["authorization"] = request.get_header("Authorization")
            captured["user_agent"] = request.get_header("User-agent")
            return _FakeResponse(b"PK-test-archive")

        with mock.patch.object(controller.urllib.request, "build_opener", return_value=opener), mock.patch.object(
            controller.urllib.request, "urlopen", side_effect=signed_open
        ):
            payload = client.download_artifact_archive(
                "https://api.github.com/repos/yanivsa/kesher-website/actions/artifacts/123/zip"
            )

        self.assertEqual(payload, b"PK-test-archive")
        self.assertEqual(captured["url"], signed)
        self.assertIsNone(captured["authorization"])
        self.assertIn("kesher-content-controller", captured["user_agent"].lower())
        self.assertEqual(opener.requests[0].get_header("Authorization"), "Bearer github-secret")


if __name__ == "__main__":
    unittest.main()
