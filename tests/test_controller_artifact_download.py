from __future__ import annotations

import email.message
import io
import json
import unittest
import urllib.error
import zipfile
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


def state_zip(payload: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("state.json", json.dumps(payload))
    return buffer.getvalue()


class ArtifactFallbackClient(controller.GitHubClient):
    def __init__(self, archives):
        super().__init__("yanivsa/kesher-website", "token")
        self.archives = list(archives)

    def request(self, method, url, body=None, **kwargs):
        if "actions/artifacts?" in url:
            return {
                "artifacts": [
                    {
                        "id": index + 1,
                        "created_at": f"2026-08-19T{20-index:02d}:00:00Z",
                        "expired": False,
                        "archive_download_url": f"https://api.github.test/artifact/{index + 1}",
                    }
                    for index in range(len(self.archives))
                ]
            }
        raise AssertionError(f"unexpected request {method} {url}")

    def download_artifact_archive(self, url):
        index = int(url.rsplit("/", 1)[1]) - 1
        value = self.archives[index]
        if isinstance(value, Exception):
            raise value
        return value


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

    def test_newest_broken_artifact_falls_back_to_older_valid_state(self):
        expected = {"version": 1, "items": [{"id": "older-valid"}]}
        client = ArtifactFallbackClient(
            [
                controller.ControllerError("GITHUB_ARTIFACT_DOWNLOAD_FAILED: transient"),
                state_zip(expected),
            ]
        )
        self.assertEqual(client.newest_video_state(), expected)

    def test_corrupt_newest_artifact_falls_back_to_older_valid_state(self):
        expected = {"version": 1, "items": [{"id": "older-valid"}]}
        client = ArtifactFallbackClient([b"not-a-zip", state_zip(expected)])
        self.assertEqual(client.newest_video_state(), expected)

    def test_all_existing_artifacts_invalid_fail_closed(self):
        client = ArtifactFallbackClient(
            [
                controller.ControllerError("GITHUB_ARTIFACT_DOWNLOAD_FAILED: one"),
                b"not-a-zip",
            ]
        )
        with self.assertRaisesRegex(
            controller.ControllerError, "VIDEO_STATE_ARTIFACTS_UNRECOVERABLE"
        ):
            client.newest_video_state()

    def test_no_artifacts_is_clean_empty_state(self):
        client = ArtifactFallbackClient([])
        self.assertEqual(client.newest_video_state(), {"version": 1, "items": []})


if __name__ == "__main__":
    unittest.main()
