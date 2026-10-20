from __future__ import annotations

import unittest
from datetime import datetime
from unittest import mock

import scripts.kesher_content_controller_v4 as v4
import scripts.kesher_content_controller_stabilized as stabilized
import scripts.kesher_content_controller as core
from zoneinfo import ZoneInfo

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


class ArticleNormalizationHeadTrackingTests(unittest.TestCase):
    def test_v4_controller_invalidates_normalization_when_pr_head_changes(self) -> None:
        github = mock.MagicMock()
        site = mock.MagicMock()
        controller = v4.V4Controller(
            now=datetime(2026, 10, 16, 10, 0, tzinfo=ISRAEL_TZ),
            github=github,
            site=site,
        )

        state = {
            "cycle": "2026-10-16",
            "status": "article_pr_open",
            "schema_version": 4,
            "article": {
                "pr_number": 1130,
                "current_pr_head_sha": "3041e1b7c5c183dcb95eb95fd486c040f740bde5",
                "normalized_head_sha": "3041e1b7c5c183dcb95eb95fd486c040f740bde5",
                "normalization_status": "complete",
            },
            "image": {"status": "pending"},
        }

        # PR head has advanced to a new commit (e.g. late push by Jules)
        new_head_sha = "76f5aef91a7fa2984b7488ff25e1b29d10b48c57"
        pr = {
            "number": 1130,
            "html_url": "https://github.com/yanivsa/kesher-website/pull/1130",
            "head": {"sha": new_head_sha},
        }

        github.article_pr_normalization_required.return_value = (True, "2026-10-16")
        github.active_normalizer_run.return_value = None

        with mock.patch.object(v4.core.GitHubClient, "dispatch") as mock_dispatch:
            action = controller._handle_open_article_pr(state, pr)

        self.assertEqual(action.kind, "dispatch_normalize")
        self.assertEqual(state["article"]["current_pr_head_sha"], new_head_sha)
        self.assertNotIn("normalized_head_sha", state["article"])
        self.assertEqual(state["article"]["normalization_status"], "running")
        self.assertEqual(state["status"], "article_normalizing")
        mock_dispatch.assert_called_once_with(
            github,
            "normalize-article-pr.yml",
            {"pr_number": "1130", "slot": "2026-10-16"},
        )

    def test_v4_auto_merge_refuses_dispatch_when_head_is_not_normalized(self) -> None:
        github = mock.MagicMock()
        site = mock.MagicMock()
        controller = v4.V4Controller(
            now=datetime(2026, 10, 16, 10, 0, tzinfo=ISRAEL_TZ),
            github=github,
            site=site,
        )

        # Mismatched normalized_head_sha vs current_pr_head_sha
        state = {
            "cycle": "2026-10-16",
            "status": "article_pr_open",
            "schema_version": 4,
            "article": {
                "pr_number": 1130,
                "current_pr_head_sha": "76f5aef91a7fa2984b7488ff25e1b29d10b48c57",
                "normalized_head_sha": "3041e1b7c5c183dcb95eb95fd486c040f740bde5",
                "normalization_status": "complete",
            },
        }

        controller._dispatch_auto_merge_v4(state)
        github.dispatch.assert_not_called()

    def test_stabilized_controller_invalidates_normalization_and_image_running(self) -> None:
        github = mock.MagicMock()
        site = mock.MagicMock()
        github.posts_on_main.return_value = []
        github.open_article_prs.return_value = []
        github.active_workflow_run.return_value = None

        controller = stabilized.StabilizedRuntimeV5Controller(
            now=datetime(2026, 10, 16, 10, 0, tzinfo=ISRAEL_TZ),
            github=github,
            site=site,
        )

        old_head = "3041e1b7c5c183dcb95eb95fd486c040f740bde5"
        new_head = "76f5aef91a7fa2984b7488ff25e1b29d10b48c57"

        state = {
            "cycle": "2026-10-16",
            "status": "article_image_running",
            "schema_version": 5,
            "article": {
                "pr_number": 1130,
                "current_pr_head_sha": old_head,
                "normalized_head_sha": old_head,
                "normalization_status": "complete",
            },
            "image": {"status": "running", "run_id": 99999},
        }

        pr = {
            "number": 1130,
            "html_url": "https://github.com/yanivsa/kesher-website/pull/1130",
            "head": {"sha": new_head},
        }

        github.article_pr_normalization_required.return_value = (True, "2026-10-16")
        github.active_normalizer_run.return_value = None
        github.request.return_value = []

        action = controller._handle_open_article_pr(state, pr)

        self.assertEqual(action.kind, "dispatch_normalize")
        self.assertEqual(state["article"]["current_pr_head_sha"], new_head)
        self.assertNotIn("normalized_head_sha", state["article"])
        self.assertEqual(state["article"]["normalization_status"], "running")
        self.assertEqual(state["image"]["status"], "pending")
        self.assertNotIn("run_id", state["image"])
        self.assertEqual(state["status"], "article_normalizing")

    def test_stabilized_controller_counts_distinct_drift_heads_not_polls(self) -> None:
        github = mock.MagicMock()
        site = mock.MagicMock()
        controller = stabilized.StabilizedRuntimeV5Controller(
            now=datetime(2026, 10, 20, 2, 0, tzinfo=ISRAEL_TZ),
            github=github,
            site=site,
        )
        stable_head = "2" * 40
        state = {
            "cycle": "2026-10-19",
            "status": "blocked",
            "schema_version": 5,
            "article": {
                "pr_number": 1156,
                "status": "blocked",
                "current_pr_head_sha": stable_head,
                "normalized_head_sha": "1" * 40,
                "normalization_status": "complete",
                "normalization_drift_count": 62,
            },
            "image": {"status": "running"},
            "last_error": {"code": "ARTICLE_JULES_UNSTABLE_MUTATION"},
        }
        pr = {"number": 1156, "html_url": "https://github.com/yanivsa/kesher-website/pull/1156", "head": {"sha": stable_head}}
        github.request.side_effect = lambda method, url, **kwargs: [] if "/issues/1156/comments" in url else {"parents": [{"sha": "3" * 40}]}
        github.article_pr_normalization_required.return_value = (True, "2026-10-19")
        github.active_normalizer_run.return_value = None

        action = controller._handle_open_article_pr(state, pr)

        self.assertEqual(action.kind, "dispatch_normalize")
        self.assertEqual(state["article"]["normalization_drift_count"], 1)
        self.assertEqual(state["article"]["last_normalization_drift_head_sha"], stable_head)
        self.assertEqual(state["status"], "article_normalizing")
        self.assertIsNone(state.get("last_error"))

    def test_stabilized_controller_blocks_after_four_distinct_drift_heads(self) -> None:
        github = mock.MagicMock()
        site = mock.MagicMock()
        controller = stabilized.StabilizedRuntimeV5Controller(
            now=datetime(2026, 10, 20, 2, 0, tzinfo=ISRAEL_TZ),
            github=github,
            site=site,
        )
        state = {
            "cycle": "2026-10-19",
            "status": "article_pr_open",
            "schema_version": 5,
            "article": {
                "pr_number": 1156,
                "current_pr_head_sha": "3" * 40,
                "normalized_head_sha": "1" * 40,
                "normalization_status": "complete",
                "normalization_drift_count": 3,
                "last_normalization_drift_head_sha": "3" * 40,
            },
            "image": {"status": "pending"},
        }
        pr = {"number": 1156, "html_url": "https://github.com/yanivsa/kesher-website/pull/1156", "head": {"sha": "4" * 40}}
        github.request.return_value = {"parents": [{"sha": "5" * 40}]}

        action = controller._handle_open_article_pr(state, pr)

        self.assertEqual(action.kind, "blocked")
        self.assertEqual(state["article"]["normalization_drift_count"], 4)
        self.assertEqual(state["article"]["status"], "blocked")

    def test_repeated_pr_head_drift_blocks_fail_closed_to_prevent_infinite_loop(self) -> None:
        github = mock.MagicMock()
        site = mock.MagicMock()
        controller = v4.V4Controller(
            now=datetime(2026, 10, 16, 10, 0, tzinfo=ISRAEL_TZ),
            github=github,
            site=site,
        )

        state = {
            "cycle": "2026-10-16",
            "status": "article_pr_open",
            "schema_version": 4,
            "article": {
                "pr_number": 1130,
                "current_pr_head_sha": "head-0",
                "normalized_head_sha": "head-0",
                "normalization_drift_count": 3,  # Already drifted 3 times
            },
        }

        pr = {
            "number": 1130,
            "html_url": "https://github.com/yanivsa/kesher-website/pull/1130",
            "head": {"sha": "head-4"},
        }

        action = controller._handle_open_article_pr(state, pr)

        self.assertEqual(action.kind, "blocked")
        self.assertEqual(state["article"]["status"], "blocked")
        self.assertIn("branch quiescence failed", action.reason)

    def test_stage_sha_lineage_is_tracked_through_complete_flow(self) -> None:
        github = mock.MagicMock()
        site = mock.MagicMock()
        controller = v4.V4Controller(
            now=datetime(2026, 10, 16, 10, 0, tzinfo=ISRAEL_TZ),
            github=github,
            site=site,
        )

        state = {
            "cycle": "2026-10-16",
            "status": "article_pr_open",
            "schema_version": 4,
            "article": {},
            "image": {"status": "pending"},
        }

        pr = {
            "number": 1130,
            "html_url": "https://github.com/yanivsa/kesher-website/pull/1130",
            "head": {"sha": "jules-head-123"},
        }

        # PR is clean, already normalized
        github.article_pr_normalization_required.return_value = (False, "2026-10-16")
        github.article_pr_image_ready.return_value = (True, {
            "provider": "gemini",
            "source": "fallback",
            "sha256": "1" * 64,
        })

        action = controller._handle_open_article_pr(state, pr)

        # Full lineage must be populated
        self.assertEqual(state["article"]["jules_head_sha"], "jules-head-123")
        self.assertEqual(state["article"]["normalized_head_sha"], "jules-head-123")
        self.assertEqual(state["article"]["image_head_sha"], "jules-head-123")
        self.assertEqual(state["article"]["merge_candidate_sha"], "jules-head-123")

    def test_merge_preflight_refuses_when_head_mismatches_normalized_sha(self) -> None:
        import importlib.util
        from pathlib import Path
        spec = importlib.util.spec_from_file_location(
            "kesher_article_pr_controller_v3",
            Path(".github/scripts/article-pr-controller-v3.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Mock controller state payload with normalized_head_sha
        import base64
        import json
        state_dict = {
            "cycle": "2026-10-16",
            "article": {
                "pr_number": 1130,
                "normalized_head_sha": "trusted-head-sha",
            },
            "image": {
                "status": "complete",
                "provider_id": "test",
                "source_id": "test",
                "artifact_sha256": "test",
            },
        }
        b64_content = base64.b64encode(json.dumps(state_dict).encode("utf-8")).decode("utf-8")

        with mock.patch.object(mod.core, "request_json", return_value={"content": b64_content}):
            # PR with mismatched head must be refused
            pr_mismatch = {"number": 1130, "head": {"sha": "late-jules-mutation"}}
            res = mod.controller_image_stage_terminal("owner/repo", pr_mismatch, "token")
            self.assertFalse(res)

            # PR with exact matching head must be accepted
            pr_match = {"number": 1130, "head": {"sha": "trusted-head-sha"}}
            res_ok = mod.controller_image_stage_terminal("owner/repo", pr_match, "token")
            self.assertTrue(res_ok)

    def test_stale_run_now_slot_collision_is_deferred_before_stale_pr_handling(self) -> None:
        github = mock.MagicMock()
        site = mock.MagicMock()
        controller = stabilized.StabilizedRuntimeV5Controller(
            now=datetime(2026, 10, 20, 11, 0, tzinfo=ISRAEL_TZ),
            github=github,
            site=site,
        )
        state = {
            "cycle": "2026-10-19",
            "status": "blocked",
            "schema_version": 5,
            "last_error": {"stage": "article", "code": "ARTICLE_NORMALIZATION_ERROR"},
            "history": [],
            "article": {"attempt_count": 1, "attempts": 1, "status": "blocked"},
            "idea_queue": [
                {
                    "idea_id": "parenting-p1-potty-training-age-4",
                    "fingerprint": "potty-fp",
                    "topic_brief": "גמילה בגיל 4",
                    "required_primary_keyword": "גמילה מחיתולים בגיל 4",
                    "run_now": False,
                    "status": "queued",
                }
            ],
            "idea_history": [],
            "active_idea": {
                "idea_id": "separate-room-transition-20261019-v1",
                "fingerprint": "room-fp",
                "topic_brief": "מעבר לחדר נפרד",
                "required_primary_keyword": "מעבר לחדר נפרד",
                "run_now": True,
                "status": "claimed",
                "publication_slot": "2026-10-19",
                "claimed_at": "2026-10-19T18:00:00Z",
            },
            "owner_cycle_archive": [{"article": {"slug": "toddler-bed-transition"}}],
        }
        posts = [
            {
                "id": "toddler-bed-transition",
                "date": "2026-10-19",
                "title": "מעבר למיטת מעבר",
                "content": "<p>x</p>",
                "category": "הדרכת הורים",
                "excerpt": "x",
            }
        ]
        github.posts_on_main.return_value = posts
        github.open_article_prs.return_value = [
            {"number": 1156, "title": "Publish Kesher article: מעבר לחדר נפרד"}
        ]
        controller._active_state_ref = state

        with mock.patch.object(
            controller,
            "_handle_open_article_pr",
            side_effect=AssertionError("stale PR must not enter normalization/merge handling"),
        ):
            action = controller._run_now_article_phase(state)

        self.assertEqual(action.kind, "defer_stale_run_now")
        self.assertEqual(state["status"], "complete")
        self.assertIsNone(state["active_idea"])
        self.assertIsNone(state["last_error"])
        self.assertEqual(len(state["idea_queue"]), 1)
        self.assertEqual(state["idea_queue"][0]["idea_id"], "parenting-p1-potty-training-age-4")
        self.assertEqual(len(state["idea_history"]), 1)
        self.assertEqual(state["idea_history"][-1]["idea_id"], "separate-room-transition-20261019-v1")
        self.assertFalse(state["idea_history"][-1]["run_now"])
        self.assertEqual(state["idea_history"][-1]["status"], "deferred")
        self.assertEqual(state["idea_history"][-1]["deferred_reason"], "RUN_NOW_SLOT_OCCUPIED_AFTER_ROLLOVER")
        self.assertTrue(any(h.get("reason") == "run_now_slot_occupied_after_rollover" for h in state["history"]))


if __name__ == "__main__":
    unittest.main()
