from __future__ import annotations

import copy
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller as controller

TZ = ZoneInfo("Asia/Jerusalem")


def article(slug: str = "today-article", title: str = "כותרת מאמר") -> dict:
    return {
        "id": slug,
        "title": title,
        "date": "2026-08-19",
        "category": "הדרכת הורים",
        "excerpt": "תקציר",
        "content": "<p>תוכן</p>",
    }


class FakeGitHub:
    def __init__(self) -> None:
        self.saved_state = None
        self.posts = []
        self.prs = []
        self.active = {}
        self.video_state = {"version": 1, "items": []}
        self.dispatches = []

    def load_controller_state(self):
        return copy.deepcopy(self.saved_state)

    def save_controller_state(self, state):
        self.saved_state = copy.deepcopy(state)

    def contents_json(self, path, ref="main"):
        assert path == "src/data/posts.json"
        assert ref == "main"
        return copy.deepcopy(self.posts)

    def open_article_prs(self):
        return copy.deepcopy(self.prs)

    def active_workflow_run(self, workflow, *, production_only=False):
        value = self.active.get(workflow)
        if value and production_only and value.get("event") == "pull_request":
            return None
        return copy.deepcopy(value) if value else None

    def dispatch(self, workflow, inputs=None):
        self.dispatches.append((workflow, copy.deepcopy(inputs)))
        self.active[workflow] = {"id": len(self.dispatches), "status": "in_progress"}

    def newest_video_state(self):
        return copy.deepcopy(self.video_state)


class FakeSite:
    def __init__(self, status=200, body="") -> None:
        self.status = status
        self.body = body
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        return self.status, self.body


class ControllerTests(unittest.TestCase):
    def now(self, hour=19, minute=0):
        return datetime(2026, 8, 19, hour, minute, tzinfo=TZ)

    def make(self, github=None, site=None, now=None):
        return controller.Controller(
            github or FakeGitHub(),
            site or FakeSite(),
            now=now or self.now(),
        )

    def test_canonical_slug_falls_back_to_id(self):
        self.assertEqual(controller.canonical_slug({"id": "abc"}), "abc")
        self.assertEqual(controller.canonical_slug({"id": "abc", "slug": "xyz"}), "xyz")

    def test_public_success_requires_title(self):
        self.assertTrue(controller.article_is_public("<h1>כותרת מאמר</h1>", "כותרת מאמר"))
        self.assertFalse(controller.article_is_public("<h1>משהו אחר</h1>", "כותרת מאמר"))

    def test_article_windows_are_israel_local(self):
        # Wednesday
        self.assertFalse(controller.article_window_open(self.now(0, 34)))
        self.assertTrue(controller.article_window_open(self.now(0, 35)))
        # Friday
        friday = datetime(2026, 8, 21, 7, 59, tzinfo=TZ)
        self.assertFalse(controller.article_window_open(friday))
        self.assertTrue(controller.article_window_open(friday.replace(hour=8, minute=0)))
        # Saturday only one hour after Ashdod sunset
        saturday = datetime(2026, 8, 22, 20, 0, tzinfo=TZ)
        sunset = datetime(2026, 8, 22, 19, 10, tzinfo=TZ)
        self.assertFalse(controller.article_window_open(saturday, sunset))
        self.assertTrue(controller.article_window_open(saturday.replace(minute=10), sunset))

    def test_missing_article_dispatches_exactly_one_generation(self):
        gh = FakeGitHub()
        state, action = self.make(gh).tick()
        self.assertEqual(action.kind, "dispatch_article")
        self.assertEqual(gh.dispatches, [
            (controller.ARTICLE_WORKFLOW, {"slot": "2026-08-19"})
        ])
        self.assertEqual(state["article"]["attempts"], 1)

        # A later heartbeat sees the existing active run and must not duplicate it.
        state, action = self.make(gh).tick()
        self.assertEqual(action.kind, "wait")
        self.assertEqual(len(gh.dispatches), 1)
        self.assertEqual(state["status"], "article_generating")

    def test_existing_article_pr_is_resumed_not_duplicated(self):
        gh = FakeGitHub()
        gh.prs = [{"number": 500, "html_url": "https://example/pr/500"}]
        state, action = self.make(gh).tick()
        self.assertEqual(action.kind, "wait")
        self.assertEqual(state["status"], "article_pr_open")
        self.assertEqual(state["article"]["pr_number"], 500)
        self.assertEqual(gh.dispatches, [])

    def test_duplicate_article_prs_fail_closed(self):
        gh = FakeGitHub()
        gh.prs = [{"number": 1}, {"number": 2}]
        state, action = self.make(gh).tick()
        self.assertEqual(action.kind, "blocked")
        self.assertEqual(state["last_error"]["code"], "DUPLICATE_ARTICLE_PRS")

    def test_duplicate_published_articles_fail_closed(self):
        gh = FakeGitHub()
        gh.posts = [article("a"), article("b")]
        state, action = self.make(gh).tick()
        self.assertEqual(action.kind, "blocked")
        self.assertEqual(state["last_error"]["code"], "DUPLICATE_ARTICLE_DATE")

    def test_article_in_main_but_not_live_dispatches_deploy(self):
        gh = FakeGitHub()
        gh.posts = [article()]
        site = FakeSite(status=404, body="")
        state, action = self.make(gh, site).tick()
        self.assertEqual(action.kind, "dispatch_deploy")
        self.assertEqual(gh.dispatches, [(controller.DEPLOY_WORKFLOW, None)])
        self.assertEqual(state["status"], "article_deploying")

    def test_live_article_dispatches_video_only_after_http_and_title(self):
        gh = FakeGitHub()
        gh.posts = [article()]
        site = FakeSite(status=200, body="<html><h1>כותרת מאמר</h1></html>")
        state, action = self.make(gh, site).tick()
        self.assertEqual(action.kind, "dispatch_video")
        self.assertEqual(gh.dispatches, [
            (controller.VIDEO_WORKFLOW, {"operation": "full"})
        ])
        self.assertTrue(state["article"]["live"])
        self.assertEqual(state["video"]["attempts"], 1)
        self.assertEqual(state["video"]["resume_dispatches"], 0)

    def test_video_pr_validation_does_not_block_production_dispatch(self):
        gh = FakeGitHub()
        gh.posts = [article()]
        gh.active[controller.VIDEO_WORKFLOW] = {
            "id": 66, "status": "in_progress", "event": "pull_request"
        }
        site = FakeSite(status=200, body="כותרת מאמר")
        state, action = self.make(gh, site).tick()
        self.assertEqual(action.kind, "dispatch_video")
        self.assertEqual(state["status"], "video_running")
        self.assertEqual(gh.dispatches[-1], (
            controller.VIDEO_WORKFLOW, {"operation": "full"}
        ))

    def test_active_video_run_is_resumed_not_duplicated(self):
        gh = FakeGitHub()
        gh.posts = [article()]
        gh.active[controller.VIDEO_WORKFLOW] = {"id": 77, "status": "in_progress"}
        site = FakeSite(status=200, body="כותרת מאמר")
        state, action = self.make(gh, site).tick()
        self.assertEqual(action.kind, "wait")
        self.assertEqual(state["video"]["run_id"], 77)
        self.assertEqual(gh.dispatches, [])

    def test_existing_generation_resume_does_not_burn_start_attempts(self):
        gh = FakeGitHub()
        gh.posts = [article()]
        gh.video_state = {"items": [{
            "id": "video-1",
            "status": "generating",
            "technical_verified": False,
            "source": {"slug": "today-article"},
        }]}
        site = FakeSite(status=200, body="כותרת מאמר")

        state, action = self.make(gh, site).tick()
        self.assertEqual(action.kind, "dispatch_video")
        self.assertEqual(gh.dispatches[-1], (
            controller.VIDEO_WORKFLOW, {"operation": "full"}
        ))
        self.assertEqual(state["video"]["attempts"], 0)
        self.assertEqual(state["video"]["resume_dispatches"], 1)

        # Simulate the short recovery slice completing while NotebookLM is still processing.
        gh.active.pop(controller.VIDEO_WORKFLOW, None)
        state, action = self.make(gh, site).tick()
        self.assertEqual(action.kind, "dispatch_video")
        self.assertEqual(state["video"]["attempts"], 0)
        self.assertEqual(state["video"]["resume_dispatches"], 2)

    def test_jules_visual_rejection_dispatches_upload_not_rebuild(self):
        gh = FakeGitHub()
        gh.posts = [article()]
        gh.video_state = {"items": [{
            "id": "video-1",
            "status": "rejected",
            "technical_verified": True,
            "visual_review_status": "rejected",
            "semantic_review_status": "approved",
            "metadata_review_status": "approved",
            "source": {"slug": "today-article"},
        }]}
        site = FakeSite(status=200, body="כותרת מאמר")
        state, action = self.make(gh, site).tick()
        self.assertEqual(action.kind, "dispatch_video")
        self.assertEqual(gh.dispatches[-1], (
            controller.VIDEO_WORKFLOW, {"operation": "upload"}
        ))
        self.assertEqual(state["video"]["attempts"], 0)
        self.assertEqual(state["video"]["resume_dispatches"], 1)

    def test_unavailable_pending_review_dispatches_upload(self):
        gh = FakeGitHub()
        gh.posts = [article()]
        gh.video_state = {"items": [{
            "id": "video-1",
            "status": "pending_review",
            "technical_verified": True,
            "visual_review_status": "unavailable",
            "semantic_review_status": "unavailable",
            "metadata_review_status": "unavailable",
            "source": {"slug": "today-article"},
        }]}
        site = FakeSite(status=200, body="כותרת מאמר")
        _, action = self.make(gh, site).tick()
        self.assertEqual(action.kind, "dispatch_video")
        self.assertEqual(gh.dispatches[-1], (
            controller.VIDEO_WORKFLOW, {"operation": "upload"}
        ))

    def test_technical_rejection_resumes_full_same_source_recovery(self):
        gh = FakeGitHub()
        gh.posts = [article()]
        gh.video_state = {"items": [{
            "id": "video-1",
            "status": "rejected",
            "technical_verified": False,
            "source": {"slug": "today-article"},
        }]}
        site = FakeSite(status=200, body="כותרת מאמר")
        state, action = self.make(gh, site).tick()
        self.assertEqual(action.kind, "dispatch_video")
        self.assertEqual(gh.dispatches[-1], (
            controller.VIDEO_WORKFLOW, {"operation": "full"}
        ))
        self.assertEqual(state["video"]["attempts"], 0)
        self.assertEqual(state["video"]["resume_dispatches"], 1)

    def test_verified_public_youtube_is_the_only_complete_state(self):
        gh = FakeGitHub()
        gh.posts = [article()]
        gh.video_state = {"items": [{
            "id": "video-1",
            "status": "uploaded",
            "uploaded": True,
            "youtube_id": "abc123",
            "youtube_url": "https://youtu.be/abc123",
            "source": {"slug": "today-article"},
            "youtube_verification": {
                "channel_id": controller.YOUTUBE_CHANNEL_ID,
                "privacy_status": "public",
                "processing_status": "succeeded",
            },
        }]}
        site = FakeSite(status=200, body="כותרת מאמר")
        state, action = self.make(gh, site).tick()
        self.assertEqual(action.kind, "complete")
        self.assertEqual(state["status"], "complete")
        self.assertEqual(state["video"]["youtube_url"], "https://youtu.be/abc123")
        self.assertEqual(gh.dispatches, [])


if __name__ == "__main__":
    unittest.main()
