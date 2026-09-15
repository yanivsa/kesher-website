from __future__ import annotations

import copy
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller_stabilized as stabilized
from scripts import kesher_content_controller_v5 as v5
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
        controller = stabilized.StabilizedRuntimeV5Controller(
            gh,
            FakeSite(),
            now=datetime(2026, 8, 19, 19, 0, tzinfo=TZ),
        )

        with mock.patch.object(stabilized.quality, "article_violations", return_value=[]):
            state, action = controller.tick()

        self.assertEqual(action.kind, "dispatch_long_video")
        self.assertEqual(
            gh.dispatches,
            [(v5.LONG_VIDEO_WORKFLOW, {"operation": "full", "target_slug": "today-article"})],
        )
        self.assertEqual(state["article"]["slug"], "today-article")


if __name__ == "__main__":
    unittest.main()
