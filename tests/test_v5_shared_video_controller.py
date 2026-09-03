from __future__ import annotations

import copy
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller as core
from scripts import kesher_content_controller_v5 as v5

TZ = ZoneInfo("Asia/Jerusalem")


def article(slug: str = "today-article") -> dict:
    return {
        "id": slug,
        "slug": slug,
        "title": "כותרת מאמר",
        "date": "2026-08-19",
        "category": "הדרכת הורים",
        "excerpt": "תקציר",
        "content": "<p>תוכן מלא בעברית</p>",
    }


def verified_item(source: dict, youtube_id: str, *, item_id: str, provider: bool = True) -> dict:
    item = {
        "id": item_id,
        "status": "uploaded",
        "uploaded": True,
        "source": copy.deepcopy(source),
        "youtube_id": youtube_id,
        "youtube_url": f"https://youtu.be/{youtube_id}",
        "youtube_verification": {
            "channel_id": core.YOUTUBE_CHANNEL_ID,
            "privacy_status": "public",
            "processing_status": "succeeded",
        },
    }
    if provider:
        item.update({
            "source_id": "source-1",
            "task_id": "task-1",
            "artifact_id": "task-1",
        })
    return item


class FakeGitHub:
    def __init__(self) -> None:
        self.api = "https://api.github.test/repos/yanivsa/kesher-website"
        self.saved_state = None
        self.posts = [article()]
        self.prs = []
        self.active = {}
        self.runs = {}
        self.long_state = {"version": 1, "items": []}
        self.short_state = {"version": 1, "items": []}
        self.dispatches = []


    def request(self, method, path, body=None, allow_404=False):
        if method == "POST" and "/actions/workflows/" in path and path.endswith("/dispatches"):
            import urllib.parse
            workflow = urllib.parse.unquote(path.split("/actions/workflows/", 1)[1].rsplit("/dispatches", 1)[0])
            inputs = copy.deepcopy((body or {}).get("inputs"))
            self.dispatches.append((workflow, inputs))
            self.active[workflow] = {
                "id": len(self.dispatches),
                "status": "in_progress",
                "event": "workflow_dispatch",
            }
            return {}
        raise AssertionError(f"unexpected request {method} {path}")

    def load_controller_state(self):
        return copy.deepcopy(self.saved_state)

    def save_controller_state(self, state):
        self.saved_state = copy.deepcopy(state)

    def contents_json(self, path, ref="main"):
        assert path == "src/data/posts.json"
        return copy.deepcopy(self.posts)

    def open_article_prs(self, target_slot=None):
        return copy.deepcopy(self.prs)

    def article_pr_normalization_required(self, pr):
        return False, "2026-08-19"

    def article_pr_image_ready(self, pr):
        return False, {}

    def active_normalizer_run(self, pr_number):
        return None

    def active_image_run(self, pr_number):
        return None

    def active_workflow_run(self, workflow, *, production_only=False):
        row = self.active.get(workflow)
        if row and production_only and row.get("event") == "pull_request":
            return None
        return copy.deepcopy(row) if row else None

    def workflow_run_by_id(self, run_id):
        return copy.deepcopy(self.runs.get(run_id))

    def article_result_for_run(self, run_id):
        return None

    def dispatch(self, workflow, inputs=None):
        self.dispatches.append((workflow, copy.deepcopy(inputs)))
        self.active[workflow] = {
            "id": len(self.dispatches),
            "status": "in_progress",
            "event": "workflow_dispatch",
        }

    def newest_video_state(self):
        return copy.deepcopy(self.long_state)

    def newest_short_state(self):
        return copy.deepcopy(self.short_state)


class FakeSite:
    def get(self, url):
        return 200, "<h1>כותרת מאמר</h1>"


class V5SharedVideoControllerTests(unittest.TestCase):
    def make(self, gh: FakeGitHub) -> v5.V5Controller:
        return v5.V5Controller(
            gh,
            FakeSite(),
            now=datetime(2026, 8, 19, 19, 0, tzinfo=TZ),
        )

    def source(self, post=None):
        return v5.article_source_identity(post or article())

    def test_live_article_dispatches_long_form_before_short(self):
        gh = FakeGitHub()
        state, action = self.make(gh).tick()
        self.assertEqual(action.kind, "dispatch_long_video")
        self.assertEqual(gh.dispatches, [(v5.LONG_VIDEO_WORKFLOW, {"operation": "full"})])
        self.assertEqual(state["short"]["status"], "pending")

    def test_verified_long_form_dispatches_short_derive_with_same_identity(self):
        gh = FakeGitHub()
        source = self.source()
        gh.long_state["items"] = [verified_item(source, "long123", item_id="long-1")]
        state, action = self.make(gh).tick()
        self.assertEqual(action.kind, "dispatch_short")
        self.assertEqual(gh.dispatches, [(
            v5.SHORT_WORKFLOW,
            {
                "operation": "derive",
                "derive_slug": source["slug"],
                "derive_content_sha256": source["content_sha256"],
                "derive_long_item_id": "long-1",
            },
        )])
        self.assertEqual(state["long_video"]["youtube_id"], "long123")

    def test_both_public_outputs_complete_cycle(self):
        gh = FakeGitHub()
        source = self.source()
        gh.long_state["items"] = [verified_item(source, "long123", item_id="long-1")]
        gh.short_state["items"] = [verified_item(source, "short123", item_id="short-1", provider=False)]
        state, action = self.make(gh).tick()
        self.assertEqual(action.kind, "complete")
        self.assertEqual(state["status"], "complete")
        self.assertEqual(state["long_video"]["youtube_id"], "long123")
        self.assertEqual(state["short"]["youtube_id"], "short123")
        self.assertEqual(gh.dispatches, [])

    def test_existing_short_is_preserved_while_missing_long_form_is_dispatched(self):
        gh = FakeGitHub()
        source = self.source()
        gh.short_state["items"] = [verified_item(source, "short123", item_id="short-1", provider=False)]
        state, action = self.make(gh).tick()
        self.assertEqual(action.kind, "dispatch_long_video")
        self.assertEqual(state["short"]["youtube_id"], "short123")
        self.assertEqual(gh.dispatches, [(v5.LONG_VIDEO_WORKFLOW, {"operation": "full"})])

    def test_mismatched_content_hash_is_not_adopted(self):
        gh = FakeGitHub()
        source = self.source()
        stale = copy.deepcopy(source)
        stale["content_sha256"] = "0" * 64
        gh.long_state["items"] = [verified_item(stale, "oldlong", item_id="old-long")]
        state, action = self.make(gh).tick()
        self.assertEqual(action.kind, "blocked")
        self.assertEqual((state.get("last_error") or {}).get("code"), "LONG_VIDEO_IDENTITY_MISMATCH")
        self.assertEqual(gh.dispatches, [])


if __name__ == "__main__":
    unittest.main()
