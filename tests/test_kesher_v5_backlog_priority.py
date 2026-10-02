from __future__ import annotations

import unittest

from scripts import kesher_content_controller_v5 as v5

from scripts import kesher_content_controller_v5_runtime as runtime


class KesherV5BacklogPriorityTests(unittest.TestCase):
    def test_newest_recoverable_backlog_wins_over_old_exhausted_short(self):
        rows = [
            {
                "cycle": "2026-09-02",
                "media": {
                    "short_status": "exhausted",
                    "last_error": "BACKLOG_SHORT_ATTEMPTS_EXHAUSTED",
                },
            },
            {"cycle": "2026-09-05", "media": {}},
            {"cycle": "2026-09-03", "media": {}},
        ]

        ordered = runtime.ordered_recoverable_backlog(rows)

        self.assertEqual([row["cycle"] for row in ordered], ["2026-09-05", "2026-09-03"])

    def test_completed_and_terminal_seed_rows_are_not_reselected(self):
        rows = [
            {"cycle": "2026-09-05", "media": {"complete": True}},
            {
                "cycle": "2026-09-04",
                "media": {
                    "long_status": "exhausted",
                    "last_error": "BACKLOG_EXACT_SEED_ATTEMPTS_EXHAUSTED",
                },
            },
            {"cycle": "2026-09-03", "media": {}},
        ]

        ordered = runtime.ordered_recoverable_backlog(rows)

        self.assertEqual([row["cycle"] for row in ordered], ["2026-09-03"])

    def test_incomplete_actionable_current_cycle_blocks_backlog(self):
        self.assertFalse(
            runtime.backlog_may_run(
                {"status": "long_video_running"},
                current_cycle_complete=False,
            )
        )
        self.assertFalse(
            runtime.backlog_may_run(
                {"status": "short_running"},
                current_cycle_complete=False,
            )
        )

    def test_waiting_for_publication_window_can_use_idle_capacity_for_backlog(self):
        self.assertTrue(
            runtime.backlog_may_run(
                {"status": "waiting_for_article_window"},
                current_cycle_complete=False,
            )
        )

    def test_completed_current_cycle_allows_backlog_cleanup(self):
        self.assertTrue(
            runtime.backlog_may_run(
                {"status": "complete"},
                current_cycle_complete=True,
            )
        )


    def test_legacy_missing_evidence_routes_exact_item_to_bounded_rebuild(self):
        post = {
            "id": "legacy",
            "slug": "legacy",
            "title": "מאמר ישן",
            "date": "2026-10-01",
            "category": "זוגיות",
            "excerpt": "תקציר",
            "content": "<p>תוכן</p>",
        }
        source = v5.article_source_identity(post)
        legacy = {
            "id": "video-legacy",
            "status": "pending_review",
            "uploaded": False,
            "technical_verified": True,
            "source": dict(source),
            "final_sha256": "f" * 64,
            # Deliberately missing immutable evidence hashes.
        }
        row = {"cycle": "2026-10-01", "media": {}}
        state = {"status": "complete", "backlog": [row], "history": []}

        class FakeGitHub:
            api = "https://api.github.test/repos/yanivsa/kesher-website"

            def __init__(self):
                self.dispatches = []

            def newest_video_state(self):
                return {"version": 1, "items": [legacy]}

            def active_workflow_run(self, workflow, production_only=False):
                return None

            def request(self, method, path, body=None, allow_404=False):
                if method == "POST" and "/actions/workflows/" in path and path.endswith("/dispatches"):
                    self.dispatches.append(body["inputs"])
                    return {}
                raise AssertionError((method, path))

        controller = object.__new__(runtime.RuntimeV5Controller)
        controller.github = FakeGitHub()
        controller._published_backlog_source = lambda _state: (row, source)

        action = controller._backlog_media_preflight(state)

        self.assertEqual(action.kind, "dispatch_backlog_long_rebuild")
        self.assertEqual(
            controller.github.dispatches,
            [{
                "operation": "rebuild",
                "rebuild_item_id": "video-legacy",
                "target_slug": "legacy",
                "target_content_sha256": source["content_sha256"],
                "target_item_id": "video-legacy",
            }],
        )
        self.assertEqual(row["media"]["long_evidence_rebuild_count"], 1)
        self.assertNotIn("long_resume_count", row["media"])

    def test_legacy_evidence_rebuild_is_bounded(self):
        item = {
            "status": "approved",
            "uploaded": False,
            "technical_verified": True,
            "final_sha256": "f" * 64,
        }
        self.assertTrue(runtime.legacy_immutable_evidence_gap(item))
        complete = dict(item)
        complete.update({
            "manifest_sha256": "m",
            "transcript_sha256": "t",
            "source_file_sha256": "s",
            "visual_review_sha256": "v",
            "frame_sha256": {"frame.png": "h"},
        })
        self.assertFalse(runtime.legacy_immutable_evidence_gap(complete))


if __name__ == "__main__":
    unittest.main()
