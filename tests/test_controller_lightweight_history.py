from __future__ import annotations

import copy
import io
import json
import unittest
import zipfile

from scripts import kesher_content_controller as core
from scripts import kesher_content_controller_v5 as v5
from scripts import kesher_content_controller_v5_runtime_base as runtime_base


class _HistoryGitHub:
    def __init__(self, snapshot: dict) -> None:
        self.api = "https://api.github.test/repos/yanivsa/kesher-website"
        self.snapshot = copy.deepcopy(snapshot)
        self.requested_urls: list[str] = []
        self.downloads: list[str] = []

    def request(self, method: str, url: str, body=None, allow_404=False):
        self.requested_urls.append(url)
        self.assert_get(method)
        return {
            "artifacts": [{
                "id": 1,
                "expired": False,
                "created_at": "2026-10-12T08:00:00Z",
                "archive_download_url": "https://api.github.test/artifacts/1/zip",
            }]
        }

    @staticmethod
    def assert_get(method: str) -> None:
        if method != "GET":
            raise AssertionError(f"unexpected method {method}")

    def download_artifact_archive(self, url: str) -> bytes:
        self.downloads.append(url)
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("state.json", json.dumps(self.snapshot))
        return payload.getvalue()


class ControllerLightweightHistoryTests(unittest.TestCase):
    def test_historical_long_lookup_uses_only_lightweight_controller_state_artifacts(self):
        source = {"slug": "today-article", "content_sha256": "a" * 64}
        item = {
            "id": "long-1",
            "status": "uploaded",
            "uploaded": True,
            "source": copy.deepcopy(source),
            "youtube_id": "public123",
            "youtube_url": "https://youtu.be/public123",
            "youtube_verification": {
                "channel_id": core.YOUTUBE_CHANNEL_ID,
                "privacy_status": "public",
                "processing_status": "succeeded",
            },
        }
        github = _HistoryGitHub({"version": 1, "items": [item]})
        controller = object.__new__(runtime_base.RuntimeV5Controller)
        controller.github = github

        recovered = controller._verified_long_from_artifact_history(source)

        self.assertIsNotNone(recovered)
        self.assertEqual(recovered["id"], "long-1")
        self.assertEqual(len(github.requested_urls), 1)
        url = github.requested_urls[0]
        self.assertIn(f"name={v5.LONG_VIDEO_CONTROLLER_STATE_ARTIFACT}", url)
        self.assertNotIn(f"name={v5.LONG_VIDEO_STATE_ARTIFACT}", url)
        self.assertEqual(github.downloads, ["https://api.github.test/artifacts/1/zip"])


if __name__ == "__main__":
    unittest.main()
