"""Hermetic read-only YouTube reconciliation: no uploads or inferred task creation."""
from __future__ import annotations

import unittest
from scripts.kesher_runtime.ghonly_youtube_gap_audit import (
    CHANNEL, TARGETS, IncompleteYouTubeInventory, audit_channel,
)


class _Endpoint:
    def __init__(self, fn):
        self.fn = fn

    def list(self, **kwargs):
        return _Execution(self.fn(kwargs))


class _Execution:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class FakeYouTube:
    def __init__(self):
        self.calls = []
        self.pages = [
            {"items":[{"contentDetails":{"videoId":"PubAb1234xy"}}],"nextPageToken":"NEXT"},
            {"items":[{"contentDetails":{"videoId":"Private001x"}}]},
        ]
        self.videos_map = {
            "PubAb1234xy": self.record(
                "PubAb1234xy", "public", "succeeded",
                TARGETS[0][1], TARGETS[0][2],
            ),
            "Private001x": self.record(
                "Private001x", "private", "succeeded",
                TARGETS[1][1], TARGETS[1][2],
            ),
        }

    @staticmethod
    def record(vid, privacy, status, slug, sha):
        return {"id":vid, "snippet":{
            "channelId":CHANNEL,
            "description":"source_slug="+slug+" content_sha256="+sha,
        }, "status":{"privacyStatus":privacy},
            "processingDetails":{"processingStatus":status}}

    def channels(self):
        def result(kwargs):
            self.calls.append(("channels.list", kwargs))
            return {"items":[{"id":CHANNEL,"contentDetails":{
                "relatedPlaylists":{"uploads":"UPLOADS"}}}]}
        return _Endpoint(result)

    def playlistItems(self):
        def result(kwargs):
            self.calls.append(("playlistItems.list", kwargs))
            return self.pages[1] if kwargs.get("pageToken") else self.pages[0]
        return _Endpoint(result)

    def videos(self):
        def result(kwargs):
            self.calls.append(("videos.list", kwargs))
            ids = kwargs["id"].split(",")
            return {"items":[self.videos_map[x] for x in ids if x in self.videos_map]}
        return _Endpoint(result)


class DeletedUploadFake(FakeYouTube):
    """A deleted YouTube video must have both authentic marker and exact 404."""

    def __init__(self, reason="videoNotFound"):
        super().__init__()
        del self.videos_map["Private001x"]
        self.reason = reason
        self.pages[1]["items"][0].update({
            "snippet": {
                "channelId": CHANNEL, "playlistId": "UPLOADS",
                "resourceId": {"kind":"youtube#video","videoId":"Private001x"},
                "title": "Deleted video",
            },
            "status": {"privacyStatus": "privacyStatusUnspecified"},
        })

    def playlistItems(self):
        base = super().playlistItems()
        def request(kwargs):
            if kwargs.get("videoId"):
                class NotFound(Exception):
                    def __init__(self, reason):
                        import json
                        from types import SimpleNamespace
                        self.resp = SimpleNamespace(status=404)
                        self.content = json.dumps({
                            "error":{"code":404,"errors":[{
                                "reason": reason, "domain":"youtube.playlistItem",
                                "location":"videoId",
                            }]}
                        }).encode()
                raise NotFound(self.reason)
            return base.list(**kwargs).execute()
        return _Endpoint(request)


class ReadOnlyGapAuditTests(unittest.TestCase):
    def test_full_pagination_and_exact_source_with_private_redaction(self):
        yt = FakeYouTube()
        result = audit_channel(yt)
        self.assertTrue(result["channel_verified"])
        self.assertTrue(result["youtube_scan_complete"])
        self.assertEqual(result["uploaded_playlist_count"], 2)
        self.assertEqual(len(result["items"]), 6)
        self.assertEqual(result["items"][0]["exact_source_candidates"][0]["public_url"],
                         "https://www.youtube.com/watch?v=PubAb1234xy")
        private = result["items"][1]["exact_source_candidates"][0]
        self.assertEqual(private["privacy"], "private")
        self.assertNotIn("public_url", private)
        self.assertNotIn("Private001x", str(result))
        self.assertTrue(all(not x["upload_authorized"] and
                            not x["new_provider_generation_authorized"]
                            for x in result["items"]))
        self.assertEqual([x[0] for x in yt.calls],
                         ["channels.list","playlistItems.list","playlistItems.list","videos.list"])

    def test_missing_source_sha_is_only_unapproved_candidate(self):
        yt = FakeYouTube()
        yt.videos_map["PubAb1234xy"]["snippet"]["description"] = (
            "source_slug=" + TARGETS[0][1] + " content_sha256=" + TARGETS[1][2])
        result = audit_channel(yt)
        self.assertEqual(result["items"][0]["exact_match_count"], 0)
        self.assertEqual(result["items"][0]["legacy_candidate_count"], 1)
        self.assertFalse(result["items"][0]["source_qa_approved"])

    def test_deleted_tombstone_requires_independent_exact_404(self):
        yt = DeletedUploadFake()
        result = audit_channel(yt)
        self.assertTrue(result["youtube_scan_complete"])
        self.assertEqual(result["confirmed_deleted_tombstones"], 1)
        self.assertEqual(result["uploaded_playlist_count"], 2)
        self.assertEqual(result["resolved_video_count"], 1)
        self.assertEqual(result["unresolved_video_fingerprints"], [])
        self.assertFalse(result["items"][1]["upload_authorized"])
        self.assertNotIn("Private001x", str(result))
        self.assertTrue(all(x[0] not in ("videos.insert","videos.update")
                            for x in yt.calls))

    def test_unverified_404_cannot_silently_exclude_video(self):
        result = audit_channel(DeletedUploadFake(reason="quotaExceeded"))
        self.assertFalse(result["youtube_scan_complete"])
        self.assertEqual(result["confirmed_deleted_tombstones"], 0)
        self.assertEqual(len(result["unresolved_video_fingerprints"]), 1)

    def test_spoofed_deleted_title_alone_not_enough(self):
        yt = DeletedUploadFake()
        yt.pages[1]["items"][0]["snippet"]["channelId"] = "WRONG_CHANNEL"
        result = audit_channel(yt)
        self.assertFalse(result["youtube_scan_complete"])
        self.assertEqual(result["confirmed_deleted_tombstones"], 0)

    def test_missing_youtube_video_cannot_claim_complete(self):
        yt = FakeYouTube()
        del yt.videos_map["Private001x"]
        result = audit_channel(yt)
        self.assertFalse(result["youtube_scan_complete"])
        self.assertEqual(len(result["unresolved_video_fingerprints"]), 1)
        self.assertNotIn("Private001x", str(result))

    def test_duplicate_page_token_fails_closed(self):
        yt = FakeYouTube()
        yt.pages[1]["nextPageToken"] = "NEXT"
        with self.assertRaisesRegex(IncompleteYouTubeInventory, "PAGINATION"):
            audit_channel(yt)

    def test_wrong_channel_fails_closed(self):
        yt = FakeYouTube()
        yt.videos_map["PubAb1234xy"]["snippet"]["channelId"] = "impostor"
        with self.assertRaisesRegex(IncompleteYouTubeInventory, "WRONG_YOUTUBE"):
            audit_channel(yt)

    def test_script_is_read_only_and_preflight_bound(self):
        from pathlib import Path
        code = Path("scripts/kesher_runtime/ghonly_youtube_gap_audit.py").read_text()
        flow = Path(".github/workflows/kesher-daily-video.yml").read_text()
        for forbidden in (".insert(", ".update(", ".delete(", "upload_only(", "start_generation("):
            self.assertNotIn(forbidden, code)
        self.assertIn('KESHER_RECOVERY_READ_ONLY', code)
        self.assertIn("KESHER_GHONLY_YOUTUBE_AUDIT", code)
        self.assertIn("inputs.operation == 'preflight'", flow)
        self.assertIn("ghonly_youtube_gap_audit", flow)


if __name__ == "__main__":
    unittest.main()
