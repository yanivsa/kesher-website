from __future__ import annotations

import copy
import unittest
from datetime import date, datetime
from unittest import mock
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller as core
from scripts import kesher_content_controller_v3_entry as v3
from scripts import kesher_content_controller_v4 as v4


class DummySite:
    def get(self, url):
        return 404, ""


class DummyGithub:
    def __init__(self):
        self.saved = None
        self.video_state = {"version": 1, "items": []}
        self.normalize_required = False
        self.normalize_active = None
        self.image_ready = False
        self.image_evidence = {}

    def load_controller_state(self):
        return copy.deepcopy(self.saved)

    def save_controller_state(self, state):
        self.saved = copy.deepcopy(state)

    def article_pr_normalization_required(self, pr):
        return self.normalize_required, "2026-09-03"

    def active_normalizer_run(self, pr_number):
        return copy.deepcopy(self.normalize_active)

    def article_pr_image_ready(self, pr):
        return self.image_ready, copy.deepcopy(self.image_evidence)

    def active_image_run(self, pr_number):
        return None

    def newest_video_state(self):
        return copy.deepcopy(self.video_state)


class PipelineV4Tests(unittest.TestCase):
    def make(self, github):
        return v4.V4Controller(
            github,
            DummySite(),
            now=datetime(2026, 9, 3, 12, 0, tzinfo=ZoneInfo("Asia/Jerusalem")),
        )

    def state(self):
        state = v3.normalize_state(None, date(2026, 9, 3))
        state["schema_version"] = 4
        return state

    def test_article_pr_is_normalized_before_image_dispatch(self):
        github = DummyGithub()
        github.normalize_required = True
        controller = self.make(github)
        state = self.state()
        pr = {"number": 77, "html_url": "https://example.test/pr/77"}
        with mock.patch.object(core.GitHubClient, "dispatch", autospec=True) as dispatch:
            action = controller._handle_open_article_pr(state, pr)
        self.assertEqual(action.kind, "dispatch_normalize")
        self.assertEqual(state["article"]["normalization_status"], "running")
        dispatch.assert_called_once()
        args = dispatch.call_args.args
        self.assertEqual(args[1], v4.NORMALIZE_WORKFLOW)
        self.assertEqual(args[2], {"pr_number": "77", "slot": "2026-09-03"})
        self.assertEqual(state["image"]["attempt_count"], 0)

    def test_image_exhaustion_is_not_deferred_in_v4(self):
        github = DummyGithub()
        controller = self.make(github)
        state = self.state()
        state["image"]["attempt_count"] = 3
        pr = {"number": 88, "html_url": "https://example.test/pr/88"}
        with self.assertRaises(v3.StageAttemptsExhausted):
            controller._handle_open_article_pr(state, pr)
        self.assertNotEqual(state["image"].get("status"), "deferred")

    def test_four_failed_fresh_video_attempts_release_without_fifth_generation(self):
        github = DummyGithub()
        controller = self.make(github)
        state = self.state()
        state["article"].update({"slug": "article-1", "live": True})
        state["video"]["attempt_count"] = 4
        with mock.patch.object(core.GitHubClient, "dispatch", autospec=True) as dispatch:
            with self.assertRaises(v4.ShortReleasePending):
                controller._dispatch_budgeted(state, "video", core.VIDEO_WORKFLOW, {"operation": "full"})
        dispatch.assert_called_once()
        args = dispatch.call_args.args
        self.assertEqual(args[1], core.VIDEO_WORKFLOW)
        self.assertEqual(
            args[2],
            {"operation": "release", "release_slug": "article-1"},
        )
        self.assertEqual(state["video"]["attempt_count"], 4)

    def test_attempt_five_is_recovery_only_for_exact_generating_identity(self):
        github = DummyGithub()
        github.video_state = {
            "version": 1,
            "items": [{
                "id": "video-1",
                "status": "generating",
                "uploaded": False,
                "source_id": "source-1",
                "task_id": "task-1",
                "artifact_id": "task-1",
                "source": {"slug": "article-1", "date": "2026-09-03"},
            }],
        }
        controller = self.make(github)
        state = self.state()
        state["article"].update({"slug": "article-1", "live": True})
        state["video"]["attempt_count"] = 4
        with mock.patch.object(core.GitHubClient, "dispatch", autospec=True) as dispatch:
            controller._dispatch_budgeted(state, "video", core.VIDEO_WORKFLOW, {"operation": "full"})
        dispatch.assert_called_once()
        self.assertEqual(state["video"]["attempt_count"], 5)
        self.assertTrue(state["video"]["fifth_attempt_recovery_only_used"])

    def test_no_sixth_video_dispatch_even_with_identity(self):
        github = DummyGithub()
        github.video_state = {
            "version": 1,
            "items": [{
                "id": "video-1",
                "status": "generating",
                "uploaded": False,
                "source_id": "source-1",
                "task_id": "task-1",
                "artifact_id": "task-1",
                "source": {"slug": "article-1", "date": "2026-09-03"},
            }],
        }
        controller = self.make(github)
        state = self.state()
        state["article"].update({"slug": "article-1", "live": True})
        state["video"]["attempt_count"] = 5
        with mock.patch.object(core.GitHubClient, "dispatch", autospec=True) as dispatch:
            with self.assertRaises(v4.ShortReleasePending):
                controller._dispatch_budgeted(state, "video", core.VIDEO_WORKFLOW, {"operation": "full"})
        self.assertEqual(dispatch.call_count, 1)
        self.assertEqual(dispatch.call_args.args[2]["operation"], "release")


if __name__ == "__main__":
    unittest.main()
