from __future__ import annotations

import copy
import unittest

from scripts import kesher_content_controller as controller
from scripts import kesher_content_controller_entry as entry


def item(
    slug: str,
    status: str,
    *,
    technical: bool | None = None,
    uploaded: bool = False,
    day: str | None = None,
) -> dict:
    row = {
        "id": f"video-{slug}",
        "status": status,
        "uploaded": uploaded,
        "source": {"slug": slug},
    }
    if day:
        row["israel_date"] = day
        row["source"]["date"] = day
    if technical is not None:
        row["technical_verified"] = technical
    return row


class FakeCorrelationGitHub:
    def __init__(self) -> None:
        self.runs = {}
        self.article_results = {}
        self.saved_state = None

    @staticmethod
    def _lookup(mapping, run_id):
        if run_id in mapping:
            return mapping[run_id]
        text = str(run_id)
        if text in mapping:
            return mapping[text]
        if text.isdigit() and int(text) in mapping:
            return mapping[int(text)]
        return None

    def workflow_run_by_id(self, run_id):
        return copy.deepcopy(self._lookup(self.runs, run_id))

    def article_result_for_run(self, run_id):
        return copy.deepcopy(self._lookup(self.article_results, run_id))

    def save_controller_state(self, state):
        self.saved_state = copy.deepcopy(state)


class ControllerQueueTests(unittest.TestCase):
    def test_prior_day_unresolved_item_is_selected_before_current_day(self) -> None:
        state = {
            "items": [
                item("yesterday", "generating", technical=False, day="2026-08-18"),
            ]
        }
        selected = entry.queue_aware_matching(state, "today")
        self.assertEqual([row["source"]["slug"] for row in selected], ["yesterday"])

    def test_verified_prior_day_upload_does_not_block_current_day(self) -> None:
        old = item("yesterday", "uploaded", uploaded=True, day="2026-08-18")
        old.update({
            "youtube_id": "old-id",
            "youtube_url": "https://www.youtube.com/watch?v=old-id",
            "youtube_verification": {
                "channel_id": controller.YOUTUBE_CHANNEL_ID,
                "privacy_status": "public",
                "processing_status": "succeeded",
            },
        })
        current = item("today", "generating", technical=False, day="2026-08-19")
        state = {"items": [old, current]}
        selected = entry.queue_aware_matching(state, "today")
        self.assertEqual(selected, [current])

    def test_unverified_prior_day_upload_is_recovery_backlog(self) -> None:
        old = item("yesterday", "uploaded", uploaded=True, day="2026-08-18")
        old.update({"youtube_id": "old-id"})
        selected = entry.queue_aware_matching({"items": [old]}, "today")
        self.assertEqual(selected, [old])

    def test_multiple_unresolved_videos_form_fifo_queue(self) -> None:
        oldest = item("two-days-ago", "generating", technical=False, day="2026-08-17")
        yesterday = item("yesterday", "source_selected", technical=False, day="2026-08-18")
        current = item("today", "generating", technical=False, day="2026-08-19")
        state = {"items": [current, yesterday, oldest]}
        selected = entry.queue_aware_matching(state, "today")
        self.assertEqual(selected, [oldest])

    def test_fifo_tie_breaker_is_deterministic(self) -> None:
        first = item("a", "generating", technical=False, day="2026-08-18")
        second = item("b", "generating", technical=False, day="2026-08-18")
        first["created_at"] = "2026-08-18T01:00:00+00:00"
        second["created_at"] = "2026-08-18T02:00:00+00:00"
        selected = entry.queue_aware_matching({"items": [second, first]}, "today")
        self.assertEqual(selected, [first])

    def test_jules_rejected_prior_day_item_remains_recoverable(self) -> None:
        old = item("yesterday", "rejected", technical=True, day="2026-08-18")
        selected = entry.queue_aware_matching({"items": [old]}, "today")
        self.assertEqual(selected, [old])

    def test_named_article_run_matches_only_exact_publication_slot(self) -> None:
        current = {
            "id": 10,
            "event": "workflow_dispatch",
            "display_title": "Kesher Article 2026-08-19",
            "created_at": "2026-08-19T01:00:00Z",
        }
        stale = dict(
            current,
            id=9,
            display_title="Kesher Article 2026-08-18",
            created_at="2026-08-18T01:00:00Z",
        )
        self.assertTrue(entry.article_run_matches_cycle(current, "2026-08-19", {}))
        self.assertFalse(entry.article_run_matches_cycle(stale, "2026-08-19", {}))

    def test_tracked_legacy_article_run_survives_rolling_upgrade(self) -> None:
        legacy = {
            "id": 77,
            "event": "workflow_dispatch",
            "display_title": "Kesher Article Generation",
            "created_at": "2026-08-19T03:57:05Z",
        }
        self.assertTrue(
            entry.article_run_matches_cycle(
                legacy,
                "2026-08-19",
                {"run_id": 77, "last_dispatch_at": "2026-08-19T03:57:05Z"},
            )
        )

    def test_recent_dispatch_correlates_legacy_article_run_without_run_name(self) -> None:
        legacy = {
            "id": 78,
            "event": "workflow_dispatch",
            "display_title": "Kesher Article Generation",
            "created_at": "2026-08-19T04:00:03Z",
        }
        state = {"last_dispatch_at": "2026-08-19T04:00:00+00:00"}
        self.assertTrue(entry.article_run_matches_cycle(legacy, "2026-08-19", state))

    def test_fast_article_completion_is_adopted_before_controller_retry(self) -> None:
        gh = FakeCorrelationGitHub()
        state = {
            "schema_version": 2,
            "cycle": "2026-08-19",
            "article": {
                "last_dispatch_at": "2026-08-19T04:00:00+00:00",
                "run_id": None,
            },
            "video": {},
        }
        gh.runs[88] = {
            "id": 88,
            "status": "completed",
            "conclusion": "failure",
            "event": "workflow_dispatch",
            "display_title": "Kesher Article Generation",
            "created_at": "2026-08-19T04:00:02Z",
        }
        adopted = entry.adopt_triggered_child(
            gh,
            state,
            "2026-08-19",
            {
                "KESHER_TRIGGER_EVENT": "workflow_run",
                "KESHER_CHILD_WORKFLOW": entry.ARTICLE_WORKFLOW_NAME,
                "KESHER_CHILD_RUN_ID": "88",
            },
        )
        self.assertTrue(adopted)
        self.assertEqual(state["article"]["run_id"], 88)
        self.assertEqual(gh.saved_state["article"]["run_id"], 88)

    def test_article_result_slot_can_correlate_completion_after_dispatch_metadata_loss(self) -> None:
        gh = FakeCorrelationGitHub()
        state = {
            "schema_version": 2,
            "cycle": "2026-08-19",
            "article": {"run_id": None},
            "video": {},
        }
        gh.runs[89] = {
            "id": 89,
            "status": "completed",
            "event": "workflow_dispatch",
            "display_title": "Kesher Article Generation",
            "created_at": "2026-08-19T05:00:00Z",
        }
        gh.article_results[89] = {
            "schema_version": 1,
            "slot": "2026-08-19",
            "outcome": "JULES_CREATE_ERROR",
            "retryable": True,
        }
        self.assertTrue(
            entry.adopt_triggered_child(
                gh,
                state,
                "2026-08-19",
                {
                    "KESHER_TRIGGER_EVENT": "workflow_run",
                    "KESHER_CHILD_WORKFLOW": entry.ARTICLE_WORKFLOW_NAME,
                    "KESHER_CHILD_RUN_ID": "89",
                },
            )
        )

    def test_stale_previous_day_article_completion_is_not_adopted(self) -> None:
        gh = FakeCorrelationGitHub()
        state = {
            "schema_version": 2,
            "cycle": "2026-08-19",
            "article": {"run_id": None},
            "video": {},
        }
        gh.runs[90] = {
            "id": 90,
            "status": "completed",
            "event": "workflow_dispatch",
            "display_title": "Kesher Article 2026-08-18",
            "created_at": "2026-08-18T05:00:00Z",
        }
        self.assertFalse(
            entry.adopt_triggered_child(
                gh,
                state,
                "2026-08-19",
                {
                    "KESHER_TRIGGER_EVENT": "workflow_run",
                    "KESHER_CHILD_WORKFLOW": entry.ARTICLE_WORKFLOW_NAME,
                    "KESHER_CHILD_RUN_ID": "90",
                },
            )
        )
        self.assertIsNone(state["article"]["run_id"])
        self.assertIsNone(gh.saved_state)

    def test_fast_video_completion_is_correlated_by_dispatch_time(self) -> None:
        gh = FakeCorrelationGitHub()
        state = {
            "schema_version": 2,
            "cycle": "2026-08-19",
            "article": {},
            "video": {
                "last_dispatch_at": "2026-08-19T06:00:00+00:00",
                "run_id": None,
            },
        }
        gh.runs[91] = {
            "id": 91,
            "status": "completed",
            "conclusion": "failure",
            "event": "workflow_dispatch",
            "display_title": "Kesher Daily NotebookLM Video Overview",
            "created_at": "2026-08-19T06:00:04Z",
        }
        self.assertTrue(
            entry.adopt_triggered_child(
                gh,
                state,
                "2026-08-19",
                {
                    "KESHER_TRIGGER_EVENT": "workflow_run",
                    "KESHER_CHILD_WORKFLOW": entry.VIDEO_WORKFLOW_NAME,
                    "KESHER_CHILD_RUN_ID": "91",
                },
            )
        )
        self.assertEqual(state["video"]["run_id"], 91)


if __name__ == "__main__":
    unittest.main()
