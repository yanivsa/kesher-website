from __future__ import annotations

import unittest
from datetime import datetime
from unittest import mock

import scripts.kesher_content_controller_v4 as v4
import scripts.kesher_content_controller_v5 as v5
import scripts.kesher_content_controller_stabilized as stabilized
import scripts.kesher_content_controller as core
from zoneinfo import ZoneInfo

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


class ArticleNormalizationHeadTrackingTests(unittest.TestCase):
    def test_exhausted_auto_merge_recovers_exact_pr_after_late_jules_head_change(self) -> None:
        github = mock.MagicMock()
        site = mock.MagicMock()
        controller = stabilized.StabilizedRuntimeV5Controller(
            now=datetime(2026, 10, 23, 16, 0, tzinfo=ISRAEL_TZ),
            github=github,
            site=site,
        )
        old_head = "4d922a592dd7cd46d9ea4cbf2be9a026d2b9243e"
        new_head = "7baf8d39ad4173b9816b15b9e2b9df06c8e534cf"
        state = {
            "cycle": "2026-10-23",
            "status": "blocked",
            "schema_version": 5,
            "last_error": {
                "stage": "article",
                "code": "ARTICLE_ATTEMPTS_EXHAUSTED",
                "message": "PR #1182 exceeded maximum auto-merge dispatch budget (3 dispatches)",
            },
            "article": {
                "pr_number": 1182,
                "status": "exhausted",
                "current_pr_head_sha": old_head,
                "normalized_head_sha": old_head,
                "merge_candidate_sha": old_head,
                "normalization_status": "complete",
                "merge_dispatch_count": 3,
                "merge_dispatch_at": "2026-10-23T12:06:28+00:00",
            },
            "image": {"status": "complete", "run_id": 123},
            "pending_dispatches": {
                "auto-merge-article-prs.yml": {
                    "workflow": "auto-merge-article-prs.yml",
                    "cycle": "2026-10-23",
                    "status": "dispatched",
                    "inputs": {"pr_number": "1182", "slot": "2026-10-23"},
                }
            },
        }
        pr = {
            "number": 1182,
            "state": "open",
            "html_url": "https://github.com/yanivsa/kesher-website/pull/1182",
            "head": {"sha": new_head},
            "body": "",
        }

        def request(method, url, **kwargs):
            if url.endswith("/pulls/1182"):
                return pr
            if f"/commits/{new_head}" in url:
                return {"parents": [{"sha": old_head}]}
            if "/issues/1182/comments" in url:
                return []
            return {}

        github.request.side_effect = request
        github.article_pr_normalization_required.return_value = (True, "2026-10-23")
        github.active_normalizer_run.return_value = None

        action = controller._recover_exhausted_article_after_late_head_change(state)

        self.assertIsNotNone(action)
        self.assertEqual(action.kind, "dispatch_normalize")
        self.assertEqual(state["article"]["current_pr_head_sha"], new_head)
        self.assertEqual(state["article"]["merge_dispatch_count"], 0)
        self.assertNotIn("auto-merge-article-prs.yml", state["pending_dispatches"])
        self.assertEqual(state["article"]["normalization_status"], "running")
        self.assertEqual(state["image"]["status"], "pending")
        self.assertEqual(state["status"], "article_normalizing")
        self.assertIsNone(state.get("last_error"))
        github.dispatch.assert_called_once_with(
            "normalize-article-pr.yml",
            {"pr_number": "1182", "slot": "2026-10-23"},
        )

    def test_exhausted_auto_merge_does_not_reopen_when_exact_pr_head_is_unchanged(self) -> None:
        github = mock.MagicMock()
        site = mock.MagicMock()
        controller = stabilized.StabilizedRuntimeV5Controller(
            now=datetime(2026, 10, 23, 16, 0, tzinfo=ISRAEL_TZ),
            github=github,
            site=site,
        )
        head = "4d922a592dd7cd46d9ea4cbf2be9a026d2b9243e"
        state = {
            "cycle": "2026-10-23",
            "status": "blocked",
            "schema_version": 5,
            "last_error": {"stage": "article", "code": "ARTICLE_ATTEMPTS_EXHAUSTED"},
            "article": {
                "pr_number": 1182,
                "status": "exhausted",
                "current_pr_head_sha": head,
                "normalized_head_sha": head,
                "merge_dispatch_count": 3,
            },
        }
        github.request.return_value = {
            "number": 1182,
            "state": "open",
            "head": {"sha": head},
        }

        action = controller._recover_exhausted_article_after_late_head_change(state)

        self.assertIsNone(action)
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["article"]["merge_dispatch_count"], 3)
        github.dispatch.assert_not_called()

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
            "pending_dispatches": {
                "auto-merge-article-prs.yml": {
                    "workflow": "auto-merge-article-prs.yml",
                    "cycle": "2026-10-16",
                    "status": "dispatched",
                    "inputs": {"pr_number": "1130", "slot": "2026-10-16"},
                }
            },
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
        self.assertNotIn("auto-merge-article-prs.yml", state["pending_dispatches"])
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

    def test_stabilized_controller_recovers_after_blocked_drift_head_becomes_stable(self) -> None:
        github = mock.MagicMock()
        site = mock.MagicMock()
        controller = stabilized.StabilizedRuntimeV5Controller(
            now=datetime(2026, 10, 21, 12, 30, tzinfo=ISRAEL_TZ),
            github=github,
            site=site,
        )
        stable_head = "7" * 40
        state = {
            "cycle": "2026-10-20",
            "status": "blocked",
            "schema_version": 5,
            "article": {
                "pr_number": 1162,
                "status": "blocked",
                "current_pr_head_sha": stable_head,
                "normalized_head_sha": "1" * 40,
                "normalization_status": "complete",
                "normalization_drift_count": 6,
                "last_normalization_drift_head_sha": stable_head,
                "last_error": {"code": "ARTICLE_JULES_UNSTABLE_MUTATION"},
            },
            "image": {"status": "pending"},
            "last_error": {"code": "ARTICLE_JULES_UNSTABLE_MUTATION"},
        }
        pr = {"number": 1162, "html_url": "https://github.com/yanivsa/kesher-website/pull/1162", "head": {"sha": stable_head}}
        github.request.side_effect = lambda method, url, **kwargs: [] if "/issues/1162/comments" in url else {"parents": [{"sha": "3" * 40}]}
        github.article_pr_normalization_required.return_value = (True, "2026-10-20")
        github.active_normalizer_run.return_value = None

        action = controller._handle_open_article_pr(state, pr)

        self.assertEqual(action.kind, "dispatch_normalize")
        self.assertEqual(state["article"]["normalization_drift_count"], 1)
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
        self.assertEqual(state["idea_queue"][0]["idea_id"], "parenting-p1-potty-training-age-4")
        self.assertEqual(state["idea_queue"][-1]["idea_id"], "separate-room-transition-20261019-v1")
        self.assertFalse(state["idea_queue"][-1]["run_now"])
        self.assertEqual(state["idea_queue"][-1]["status"], "queued")
        self.assertEqual(state["idea_queue"][-1]["deferred_reason"], "RUN_NOW_SLOT_OCCUPIED_AFTER_ROLLOVER")
        self.assertTrue(any(h.get("reason") == "run_now_slot_occupied_after_rollover" for h in state["history"]))

    def test_successful_deferred_auto_merge_refunds_one_dispatch_idempotently(self) -> None:
        github = mock.MagicMock()
        controller = stabilized.StabilizedRuntimeV5Controller(
            now=datetime(2026, 10, 25, 15, 30, tzinfo=ISRAEL_TZ),
            github=github,
            site=mock.MagicMock(),
        )
        state = {
            "cycle": "2026-10-25",
            "status": "article_pr_open",
            "article": {
                "pr_number": 1201,
                "current_pr_head_sha": "a" * 40,
                "merge_candidate_sha": "a" * 40,
                "merge_dispatch_count": 3,
            },
            "history": [],
        }
        pr = {"number": 1201, "state": "open", "head": {"sha": "a" * 40}}
        notification = {
            "workflow": "Auto-merge Kesher article PRs",
            "run_id": "40194959063",
            "conclusion": "success",
            "source_slug": "",
            "slot": "2026-10-25",
            "source_sha": "",
        }

        with mock.patch.object(controller, "_child_notification_env", return_value=notification):
            first = controller._refund_deferred_auto_merge_success(state, pr)
            second = controller._refund_deferred_auto_merge_success(state, pr)

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(state["article"]["merge_dispatch_count"], 2)
        self.assertEqual(state["article"]["last_refunded_auto_merge_run_id"], 40194959063)
        self.assertEqual(state["history"][-1]["reason"], "successful_deferred_auto_merge_refunded")


    def test_trusted_image_commit_head_is_not_treated_as_jules_normalization_drift(self) -> None:
        github = mock.MagicMock()
        controller = stabilized.StabilizedRuntimeV5Controller(
            now=datetime(2026, 10, 27, 2, 8, tzinfo=ISRAEL_TZ),
            github=github,
            site=mock.MagicMock(),
        )
        normalized_head = "1" * 40
        image_head = "2" * 40
        state = {
            "cycle": "2026-10-27",
            "status": "article_pr_open",
            "schema_version": 5,
            "article": {
                "pr_number": 1227,
                "status": "running",
                "current_pr_head_sha": normalized_head,
                "normalized_head_sha": normalized_head,
                "normalization_status": "complete",
                "normalization_drift_count": 3,
            },
            "image": {
                "status": "running",
                "attempt_count": 3,
                "run_id": 40424206418,
            },
            "history": [],
            "pending_dispatches": {},
        }
        pr = {
            "number": 1227,
            "state": "open",
            "html_url": "https://github.com/yanivsa/kesher-website/pull/1227",
            "head": {"sha": image_head},
            "body": "\n".join([
                "Image Provider: LocalEditorial",
                "Image SHA-256: " + "a" * 64,
                "Image Source URL: local-editorial://kindergarten-adjustment-difficulties/5",
                "Image Evidence Head: " + image_head,
            ]),
        }
        evidence = {
            "provider": "LocalEditorial",
            "sha256": "a" * 64,
            "source": "local-editorial://kindergarten-adjustment-difficulties/5",
        }
        github.article_pr_image_ready.return_value = (True, evidence)
        github.article_pr_normalization_required.return_value = (False, "2026-10-27")
        github.active_normalizer_run.return_value = None
        github.request.return_value = {"parents": [{"sha": "3" * 40}]}

        with mock.patch.object(controller, "_pr_repair_status", return_value=(0, set())), \
             mock.patch.object(controller, "_pr_content_structure_errors", return_value=[]), \
             mock.patch.object(controller, "_dispatch_auto_merge_v4") as merge_gate:
            action = controller._handle_open_article_pr(state, pr)

        self.assertEqual(action.kind, "wait")
        self.assertEqual(state["article"]["normalized_head_sha"], image_head)
        self.assertEqual(state["article"]["image_head_sha"], image_head)
        self.assertEqual(state["article"]["merge_candidate_sha"], image_head)
        self.assertEqual(state["article"]["normalization_drift_count"], 0)
        self.assertEqual(state["image"]["attempt_count"], 3)
        self.assertEqual(state["image"]["status"], "complete")
        self.assertNotEqual(state["status"], "article_normalizing")
        github.dispatch.assert_not_called()
        merge_gate.assert_called_once()


    def test_exhausted_image_budget_reattaches_prior_trusted_artifact_after_normalizer_removed_pixels(self) -> None:
        self._exercise_recovery_only_dispatch(False)

    def test_existing_head_only_rebind_also_forbids_replacement_generation(self) -> None:
        self._exercise_recovery_only_dispatch(True)

    def _exercise_recovery_only_dispatch(self, rebindable: bool) -> None:
        github = mock.MagicMock()
        controller = stabilized.StabilizedRuntimeV5Controller(
            now=datetime(2026, 10, 27, 14, 0, tzinfo=ISRAEL_TZ),
            github=github,
            site=mock.MagicMock(),
        )
        prior_image_head = "3" * 40
        current_head = "4" * 40
        state = {
            "cycle": "2026-10-27",
            "status": "article_pr_open",
            "schema_version": 5,
            "article": {
                "pr_number": 1227,
                "status": "running",
                "current_pr_head_sha": current_head,
                "normalized_head_sha": current_head,
                "normalization_status": "complete",
            },
            "image": {
                "status": "exhausted",
                "attempt_count": 3,
                "attempts": 3,
                "run_id": 40424206418,
                "last_error": "IMAGE_OUTPUT_MISSING",
            },
            "history": [],
            "pending_dispatches": {},
        }
        pr = {
            "number": 1227,
            "state": "open",
            "html_url": "https://github.com/yanivsa/kesher-website/pull/1227",
            "head": {"sha": current_head},
            "body": "\n".join([
                "Image Provider: LocalEditorial",
                "Image SHA-256: " + "a" * 64,
                "Image Source URL: local-editorial://kindergarten-adjustment-difficulties/5",
                "Image Evidence Head: " + prior_image_head,
            ]),
        }
        github.article_pr_normalization_required.return_value = (False, "2026-10-27")
        github.article_pr_image_ready.return_value = (False, {})
        github.article_pr_image_rebindable.return_value = (rebindable, {})
        github.article_pr_prior_image_recoverable.return_value = (
            True,
            {"provider": "LocalEditorial", "sha256": "a" * 64, "source": "local-editorial://kindergarten-adjustment-difficulties/5"},
        )
        github.active_image_run.return_value = None

        with mock.patch.object(controller, "_pr_repair_status", return_value=(0, set())), \
             mock.patch.object(controller, "_pr_content_structure_errors", return_value=[]), \
             mock.patch.object(v4.core.GitHubClient, "dispatch") as dispatch:
            action = controller._handle_open_article_pr(state, pr)

        self.assertEqual(action.kind, "dispatch_image_rebind")
        self.assertEqual(state["status"], "article_image_rebinding")
        self.assertEqual(state["image"]["attempt_count"], 3)
        self.assertEqual(state["image"]["attempts"], 3)
        self.assertEqual(state["image"]["evidence_rebind_head_sha"], current_head)
        self.assertEqual(state["image"]["status"], "running")
        dispatch.assert_called_once_with(github, v4.v3.IMAGE_WORKFLOW, {"pr_number": "1227", "recovery_only": "true", "expected_head_sha": current_head})


    def test_run_now_adopts_exact_matching_open_pr_from_prior_slot_instead_of_redispatching_jules(self) -> None:
        github = mock.MagicMock()
        github.api = "https://api.github.com/repos/yanivsa/kesher-website"
        controller_cls = v5.owner_pr_rehome_controller(stabilized.StabilizedRuntimeV5Controller)
        controller = controller_cls(
            now=datetime(2026, 10, 27, 21, 45, tzinfo=ISRAEL_TZ),
            github=github,
            site=mock.MagicMock(),
        )
        head_sha = "e" * 40
        pr = {
            "number": 1226,
            "title": "Publish Kesher article: changing-kindergarten-midyear",
            "html_url": "https://github.com/yanivsa/kesher-website/pull/1226",
            "body": "Primary Keyword: מעבר גן באמצע שנה\n",
            "base": {"ref": "main"},
            "head": {
                "sha": head_sha,
                "repo": {"full_name": "yanivsa/kesher-website"},
            },
        }
        state = {
            "cycle": "2026-10-27",
            "status": "article_retry_wait",
            "schema_version": 5,
            "article": {
                "attempts": 3,
                "attempt_count": 3,
                "status": "retry_wait",
                "next_retry_at": None,
            },
            "active_idea": {
                "idea_id": "parenting-p1-changing-kindergarten-midyear",
                "run_now": True,
                "status": "claimed",
                "publication_slot": "2026-10-27",
                "required_primary_keyword": "מעבר גן באמצע שנה",
                "topic_brief": "Canonical ID נדרש: changing-kindergarten-midyear. כותרת עבודה",
            },
            "history": [],
        }
        github.request.return_value = [pr]
        github.contents_json.return_value = [{
            "id": "changing-kindergarten-midyear",
            "date": "2026-10-26",
            "title": "מעבר גן באמצע שנה",
        }]
        github.active_normalizer_run.return_value = None

        action = controller._run_now_article_phase(state)

        self.assertEqual(action.kind, "dispatch_normalize")
        self.assertEqual(state["article"]["pr_number"], 1226)
        self.assertEqual(state["article"]["owner_rehome_source_slot"], "2026-10-26")
        self.assertEqual(state["article"]["normalization_slot"], "2026-10-27")
        self.assertEqual(state["article"]["attempt_count"], 3)
        github.dispatch.assert_called_once_with(
            "normalize-article-pr.yml",
            {"pr_number": "1226", "slot": "2026-10-27", "source_slot": "2026-10-26"},
        )


    def test_successful_deferred_auto_merge_is_refunded_after_three_prior_deferrals(self) -> None:
        github = mock.MagicMock()
        controller = stabilized.StabilizedRuntimeV5Controller(
            now=datetime(2026, 10, 28, 19, 0, tzinfo=ISRAEL_TZ),
            github=github,
            site=mock.MagicMock(),
        )
        state = {
            "cycle": "2026-10-28",
            "status": "article_pr_open",
            "article": {
                "pr_number": 1244,
                "current_pr_head_sha": "a" * 40,
                "merge_candidate_sha": "a" * 40,
                "merge_dispatch_count": 3,
                "deferred_auto_merge_refund_count": 3,
                "last_refunded_auto_merge_run_id": 40637034405,
            },
            "history": [],
        }
        pr = {"number": 1244, "state": "open", "head": {"sha": "a" * 40}}
        notification = {
            "workflow": "Auto-merge Kesher article PRs",
            "run_id": "40696399137",
            "conclusion": "success",
            "source_slug": "",
            "slot": "2026-10-28",
            "source_sha": "",
        }

        with mock.patch.object(controller, "_child_notification_env", return_value=notification):
            refunded = controller._refund_deferred_auto_merge_success(state, pr)

        self.assertTrue(refunded)
        self.assertEqual(state["article"]["merge_dispatch_count"], 2)
        self.assertEqual(state["article"]["deferred_auto_merge_refund_count"], 4)
        self.assertEqual(state["article"]["last_refunded_auto_merge_run_id"], 40696399137)


    def test_content_preflight_rejects_blog_target_absent_from_public_catalog(self) -> None:
        github = mock.MagicMock()
        controller = stabilized.StabilizedRuntimeV5Controller(
            now=datetime(2026, 10, 28, 20, 0, tzinfo=ISRAEL_TZ),
            github=github,
            site=mock.MagicMock(),
        )
        base_sha = "a" * 40
        head_sha = "b" * 40
        base_post = {"id": "published-one", "slug": "published-one", "date": "2026-10-27"}
        content = (
            "<h3>א</h3><h3>ב</h3><h3>ג</h3><h3>ד</h3><h3>ה</h3>"
            + ("מילה " * 700)
            + '<a href="/blog/published-one">אחד</a>'
            + '<a href="/blog/published-two">שתיים</a>'
            + '<a href="/blog/retired-target">שלוש</a>'
        )
        target = {
            "id": "first-grade-maturity",
            "slug": "first-grade-maturity",
            "date": "2026-10-28",
            "content": content,
        }
        published = [
            {"id": "published-one", "slug": "published-one"},
            {"id": "published-two", "slug": "published-two"},
        ]

        def contents(path, ref):
            if path == "src/data/posts.json" and ref == head_sha:
                return [target, base_post]
            if path == "src/data/posts.json" and ref == base_sha:
                return [base_post]
            if path == "src/data/postSummaries.json" and ref == base_sha:
                return published
            raise AssertionError((path, ref))

        github.contents_json.side_effect = contents
        pr = {"head": {"sha": head_sha}, "base": {"sha": base_sha}}
        with mock.patch.object(stabilized.quality, "full_article_violations", return_value=[]):
            errors = controller._pr_content_structure_errors(pr)

        self.assertIn("internal_blog_link_missing: /blog/retired-target", errors)
        self.assertNotIn("internal_blog_link_missing: /blog/published-one", errors)
        self.assertNotIn("internal_blog_link_missing: /blog/published-two", errors)



if __name__ == "__main__":
    unittest.main()
