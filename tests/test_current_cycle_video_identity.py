from __future__ import annotations

import copy
import unittest
from unittest import mock

from scripts import kesher_content_controller_stabilized as stabilized
from scripts import kesher_content_controller_v5 as v5


SOURCE = {
    "slug": "relocation-loneliness-accompanying-partner",
    "content_sha256": "93bd8eb7d057faf9ede979e86c891504604c80766287f170b011f05065bd326c",
}


class FakeGitHub:
    def __init__(self, items=None):
        self.snapshot = {"version": 1, "items": copy.deepcopy(items or [])}

    def newest_video_state(self):
        return copy.deepcopy(self.snapshot)


class CurrentCycleVideoIdentityTests(unittest.TestCase):
    def make_controller(self, items=None):
        controller = object.__new__(stabilized.StabilizedRuntimeV5Controller)
        controller.github = FakeGitHub(items)
        controller._article_source = lambda: copy.deepcopy(SOURCE)
        return controller

    @staticmethod
    def state(*, item_id=None):
        stage = v5.v3._stage_template()
        stage["item_id"] = item_id
        return {
            "status": "long_video_retry_wait",
            "video": stage,
            "history": [],
        }

    def test_current_cycle_matching_never_returns_cross_slug_backlog_item(self):
        stale = {
            "id": "video-20261004-034718-199f8fed91",
            "status": "pending_review",
            "uploaded": False,
            "source": {
                "slug": "older-article",
                "content_sha256": "1" * 64,
            },
        }
        matches = stabilized._current_cycle_video_matching(
            {"version": 1, "items": [stale]},
            SOURCE["slug"],
        )
        self.assertEqual(matches, [])

    def test_stale_upload_without_exact_item_becomes_fresh_exact_full_dispatch(self):
        controller = self.make_controller()
        state = self.state(item_id="video-20261004-034718-199f8fed91")

        with mock.patch.object(v5.core.GitHubClient, "dispatch") as dispatch:
            controller._dispatch_budgeted(
                state,
                "video",
                v5.LONG_VIDEO_WORKFLOW,
                {"operation": "upload"},
            )

        dispatch.assert_called_once_with(
            controller.github,
            v5.LONG_VIDEO_WORKFLOW,
            {
                "operation": "full",
                "target_slug": SOURCE["slug"],
                "target_content_sha256": SOURCE["content_sha256"],
            },
        )
        self.assertIsNone(state["video"]["item_id"])
        self.assertEqual(
            state["video"]["stale_source_binding_previous"]["item_id"],
            "video-20261004-034718-199f8fed91",
        )
        self.assertEqual(
            state["history"][-1]["reason"],
            "current_cycle_stale_video_binding_cleared",
        )

    def test_exact_current_item_is_bound_to_upload_dispatch(self):
        exact = {
            "id": "video-current-exact",
            "status": "pending_review",
            "uploaded": False,
            "source": copy.deepcopy(SOURCE),
        }
        controller = self.make_controller([exact])
        state = self.state()

        with mock.patch.object(v5.core.GitHubClient, "dispatch") as dispatch:
            controller._dispatch_budgeted(
                state,
                "video",
                v5.LONG_VIDEO_WORKFLOW,
                {"operation": "upload"},
            )

        dispatch.assert_called_once_with(
            controller.github,
            v5.LONG_VIDEO_WORKFLOW,
            {
                "operation": "upload",
                "target_slug": SOURCE["slug"],
                "target_content_sha256": SOURCE["content_sha256"],
                "target_item_id": "video-current-exact",
            },
        )

    def test_rebuild_without_exact_current_item_fails_closed(self):
        controller = self.make_controller()
        state = self.state()

        with self.assertRaisesRegex(
            v5.core.ControllerError,
            "LONG_VIDEO_EXACT_ITEM_NOT_UNIQUE",
        ):
            controller._dispatch_budgeted(
                state,
                "video",
                v5.LONG_VIDEO_WORKFLOW,
                {
                    "operation": "rebuild",
                    "rebuild_item_id": "video-old-rejected",
                },
            )


if __name__ == "__main__":
    unittest.main()
