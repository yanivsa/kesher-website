from __future__ import annotations

import copy
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller_v5 as v5
from scripts import kesher_content_controller_v5_runtime as runtime
from tests.test_v5_shared_video_controller import FakeGitHub, FakeSite, article


TZ = ZoneInfo("Asia/Jerusalem")


class V5VideoSourceBindingTests(unittest.TestCase):
    def test_current_cycle_long_video_dispatch_binds_authoritative_slug_even_with_stale_provider_backlog(self):
        gh = FakeGitHub()
        stale_source = v5.article_source_identity(article("stale-article"))
        gh.long_state["items"] = [{
            "id": "video-stale",
            "status": "generating",
            "uploaded": False,
            "source": copy.deepcopy(stale_source),
            "source_id": "source-stale",
            "task_id": "task-stale",
            "artifact_id": "task-stale",
            "created_at": "2026-08-18T10:00:00Z",
        }]
        controller = v5.V5Controller(
            gh,
            FakeSite(),
            now=datetime(2026, 8, 19, 19, 0, tzinfo=TZ),
        )

        state, action = controller.tick()

        self.assertEqual(action.kind, "dispatch_long_video")
        self.assertEqual(
            gh.dispatches,
            [(v5.LONG_VIDEO_WORKFLOW, {"operation": "full", "target_slug": "today-article"})],
        )
        self.assertEqual(state["article"]["slug"], "today-article")

    def test_backlog_exact_resume_dispatch_binds_selected_backlog_slug(self):
        gh = FakeGitHub()
        post = article("prior-article")
        post["date"] = "2026-08-18"
        source = v5.article_source_identity(post)
        gh.posts = [post]
        gh.long_state["items"] = [{
            "id": "video-prior",
            "status": "generating",
            "uploaded": False,
            "source": {**copy.deepcopy(source), "date": "2026-08-18"},
            "source_id": "source-prior",
            "task_id": "task-prior",
            "artifact_id": "task-prior",
            "created_at": "2026-08-18T10:00:00Z",
        }]
        controller = runtime.RuntimeV5Controller(
            gh,
            FakeSite(),
            now=datetime(2026, 8, 19, 0, 40, tzinfo=TZ),
        )
        state = controller.state()
        state["status"] = "waiting_for_article_window"
        state["backlog"] = [{"cycle": "2026-08-18", "media": {}}]

        action = controller._backlog_media_preflight(state)

        self.assertIsNotNone(action)
        self.assertEqual(action.kind, "dispatch_backlog_long_video")
        self.assertEqual(
            gh.dispatches,
            [(v5.LONG_VIDEO_WORKFLOW, {"operation": "full", "target_slug": "prior-article"})],
        )


if __name__ == "__main__":
    unittest.main()
