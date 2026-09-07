from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
