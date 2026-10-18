#!/usr/bin/env python3
"""Regression tests for the canonical Schema-5 daily article and media pipeline.

Verifies:
1. Article with <5 H3 sections fails content gate early without image side-effects.
2. Hebrew slugs/paths in image validation are safe from UnicodeEncodeError.
3. Hero image duplicate SHA is strictly rejected by image gate and controller.
4. Gate failure after 3rd repair attempt causes auto-merge to exit non-zero (1).
5. Controller observing auto-merge failure / exhausted repairs caps dispatches and transitions to blocked/exhausted.
6. Successful merge advances to deploy and public verification before Long Video.
7. Long Video has exact identity and is blocked until exact article is public.
8. Short is gated on exact public verified Long Video.
9. No 4th attempt is allowed for any stage after 3 attempts are exhausted.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

# Load validate-article-pr
VALIDATE_PR_PATH = ROOT / ".github" / "scripts" / "validate-article-pr.py"
spec_val = importlib.util.spec_from_file_location("test_validate_article_pr", VALIDATE_PR_PATH)
assert spec_val and spec_val.loader
validate_pr = importlib.util.module_from_spec(spec_val)
spec_val.loader.exec_module(validate_pr)

# Load article-pr-controller-v3
PR_CTRL_PATH = ROOT / ".github" / "scripts" / "article-pr-controller-v3.py"
spec_ctrl = importlib.util.spec_from_file_location("test_article_pr_controller_v3", PR_CTRL_PATH)
assert spec_ctrl and spec_ctrl.loader
pr_ctrl_v3 = importlib.util.module_from_spec(spec_ctrl)
spec_ctrl.loader.exec_module(pr_ctrl_v3)

# Load stabilized controller
STABILIZED_PATH = ROOT / "scripts" / "kesher_content_controller_stabilized.py"
spec_stab = importlib.util.spec_from_file_location("test_stabilized_controller", STABILIZED_PATH)
assert spec_stab and spec_stab.loader
stabilized_mod = importlib.util.module_from_spec(spec_stab)
spec_stab.loader.exec_module(stabilized_mod)

from scripts import kesher_article_contract as article_contract
from scripts import kesher_content_controller as core
from scripts import kesher_content_controller_v5 as v5
from scripts.kesher_content_controller_v3_entry import V3GitHubClient
from tests.test_article_image_worker import fake_png


class CanonicalPipelineSemanticContractTests(unittest.TestCase):

    def test_1_article_content_gate_fails_when_fewer_than_five_h3_sections(self):
        """Article with < 5 H3 sections must fail content gate early without image side-effects."""
        content_with_3_h3 = (
            "<p>Intro paragraph</p>\n"
            "<h3>Section 1</h3>\n<p>" + "word " * 250 + "</p>\n"
            "<h3>Section 2</h3>\n<p>" + "word " * 250 + "</p>\n"
            "<h3>Section 3</h3>\n<p>" + "word " * 250 + "</p>\n"
        )
        post = {
            "id": "test-h3-slug",
            "slug": "test-h3-slug",
            "title": "Test Title",
            "content": content_with_3_h3,
            "image": "/images/generated/blog/test-h3-slug.jpg",
            "imageAlt": "Valid descriptive image alt text for article",
        }
        pr = {
            "state": "open",
            "draft": False,
            "title": "Publish Kesher article: Test Title",
            "base": {"ref": "main", "repo": {"full_name": "yanivsa/kesher-website"}, "sha": "base123"},
            "head": {"ref": "branch", "repo": {"full_name": "yanivsa/kesher-website"}, "sha": "head123"},
        }
        files_data = [{"filename": "src/data/posts.json"}]
        base_posts = []
        head_posts = [post]

        errors = validate_pr.evaluate_content(
            pr,
            files_data,
            base_posts,
            head_posts,
            image_loader=lambda entry: b"fake",
        )
        self.assertTrue(
            any("at least five H3 sections" in e for e in errors),
            f"Expected H3 error, got: {errors}",
        )
        # Verify content gate ordering: image validation should not run when content is broken
        self.assertFalse(
            any("Hero image" in e for e in errors),
            f"Image validation should not have run, but got: {errors}",
        )

    def test_2_hebrew_slug_in_image_validation_is_unicode_safe(self):
        """Hebrew slugs and paths must be percent-encoded without UnicodeEncodeError."""
        hebrew_slug = "מוכנות-לכיתה-א-עצמאות-ושגרה"
        repo_path = f"public/images/generated/blog/{hebrew_slug}.jpg"
        raw_url = validate_pr.raw_github_content_url("yanivsa/kesher-website", "headsha456", repo_path)

        # URL must be valid ASCII
        raw_url.encode("ascii")  # Raises UnicodeEncodeError if non-ASCII chars remain
        self.assertIn("https://raw.githubusercontent.com/yanivsa/kesher-website/headsha456/", raw_url)
        self.assertIn("%D7%9E", raw_url)  # Percent-encoded Hebrew letter Mem

    def test_3_hero_image_sha_collision_rejected_by_gate_and_controller(self):
        """Hero image SHA collision with an existing article is strictly rejected."""
        colliding_bytes = fake_png(1200, 675, marker=b"identical_hero_marker")
        colliding_sha = hashlib.sha256(colliding_bytes).hexdigest()

        content_with_5_h3 = (
            "<p>תקשורת זוגית היא הבסיס לכל מערכת יחסים בריאה ומאושרת. </p>\n"
            + "".join(f"<h3>Section {i}</h3>\n<p>" + "word " * 160 + "</p>\n" for i in range(1, 6))
        )
        base_post = {
            "id": "i-told-you-so-criticism-in-relationships",
            "content": content_with_5_h3,
            "image": "/images/generated/blog/i-told-you-so-criticism-in-relationships.jpg",
            "imageSha256": colliding_sha,
        }
        new_post = {
            "id": "couples-communication",
            "title": "תקשורת זוגית מעשית",
            "primaryKeyword": "תקשורת זוגית",
            "content": content_with_5_h3,
            "image": "/images/generated/blog/couples-communication.jpg",
            "imageAlt": "A very detailed alt text description of the image content here",
        }
        pr = {
            "state": "open",
            "draft": False,
            "title": "Publish Kesher article: couples-communication",
            "body": (
                "<!-- image-evidence -->\n"
                "- Primary Keyword: תקשורת זוגית\n"
                "Image Pipeline Version: 2\n"
                "Image Provider: Local\n"
                "Image Generation Result: local_fallback\n"
                "Image Attempt Chain: gemini-1/gemini-2/pexels/pixabay/local-curated\n"
                "Image Source URL: local://public/images/generated/blog/couples-communication.jpg\n"
                f"Image SHA-256: {colliding_sha}\n"
                "Image Dimensions: 1200x675\n"
                "Image Visual Match: A very detailed alt text description of the image content here\n"
                f"Image Article ID: {new_post['id']}\n"
                f"Image Article SHA-256: {article_contract.article_sha256(new_post)}\n"
                "Image Evidence Head: headsha789\n"
            ),
            "base": {"ref": "main", "repo": {"full_name": "yanivsa/kesher-website"}, "sha": "base123"},
            "head": {"ref": "branch", "repo": {"full_name": "yanivsa/kesher-website"}, "sha": "headsha789"},
        }
        files_data = [
            {"filename": "src/data/posts.json"},
            {"filename": "public/images/generated/blog/couples-communication.jpg"},
        ]

        def mock_loader(entry):
            return colliding_bytes

        errors = validate_pr.evaluate_content(
            pr,
            files_data,
            [base_post],
            [base_post, new_post],
            image_loader=mock_loader,
        )
        self.assertTrue(
            any("Hero image SHA-256 collides with existing article" in e for e in errors),
            f"Expected hero SHA collision error, got: {errors}",
        )

        # Controller's article_pr_image_ready must also reject this colliding asset
        client = V3GitHubClient("token", "yanivsa/kesher-website")
        client.contents_json = MagicMock(side_effect=lambda path, ref: [base_post] if "base" in ref or ref == "main" else [new_post])
        client.request = MagicMock(return_value={
            "encoding": "base64",
            "content": base64.b64encode(colliding_bytes).decode("ascii"),
        })
        ready, _ = client.article_pr_image_ready(pr)
        self.assertFalse(ready, "article_pr_image_ready must return False for colliding image SHA")

    def test_4_auto_merge_exits_nonzero_when_repair_attempts_exhausted(self):
        """Auto-merge must return exit code 1 (failure) when 3 attempts (initial + 2 repairs) are exhausted."""
        pr = {
            "number": 1113,
            "state": "open",
            "draft": False,
            "title": "Publish Kesher article: Stale Article",
            "body": "https://jules.google.com/task/123456\n"
                    "<!-- kesher-article-repair attempt=1 head=head1 -->\n"
                    "<!-- kesher-article-repair attempt=2 head=head2 -->",
            "base": {"ref": "main", "sha": "basesha"},
            "head": {"ref": "branch", "sha": "head2"},
        }
        errors = ["New article must contain at least five H3 sections"]
        verify = {"status": "completed", "conclusion": "failure"}

        # send_jules_repair_v3 must return False and log exhaustion
        stderr_buf = io.StringIO()
        with patch("sys.stderr", stderr_buf):
            with patch.object(pr_ctrl_v3.core, "existing_repair_attempts", return_value=(2, {"head1", "head2"})):
                result = pr_ctrl_v3.send_jules_repair_v3(
                    "yanivsa/kesher-website", pr, errors, verify, "token", "jules_key"
                )
        self.assertFalse(result)
        self.assertIn("ARTICLE_ATTEMPTS_EXHAUSTED", stderr_buf.getvalue())

        # process() must return 1 when repaired is False
        files = [{"filename": "src/data/posts.json"}]
        def mock_req(method, url, *a, **kw):
            if "files" in url:
                return files
            return pr

        with patch.object(pr_ctrl_v3.core, "request_json", side_effect=mock_req):
            with patch.object(pr_ctrl_v3.core, "is_article_scope", return_value=True):
                with patch.object(pr_ctrl_v3.core, "forbidden_paths", return_value=[]):
                    with patch.object(pr_ctrl_v3.core, "fetch_checks", return_value={"check_runs": [{"name": "verify", "status": "completed", "conclusion": "failure", "head_sha": "head2"}]}):
                        with patch.object(pr_ctrl_v3.core, "load_validator") as mock_val:
                            mock_validator = MagicMock()
                            mock_validator.evaluate.return_value = errors
                            mock_val.return_value = mock_validator
                            with patch.object(pr_ctrl_v3.core, "send_jules_repair", return_value=False):
                                exit_code = pr_ctrl_v3.core.process("yanivsa/kesher-website", 1113, "token", "jules_key")
                                self.assertEqual(exit_code, 1, "Auto-merge process must return 1 on exhausted repair attempts")

    def test_5_controller_transitions_to_blocked_when_repairs_exhausted(self):
        """Controller seeing exhausted PR repairs must transition to blocked/exhausted without extra dispatches."""
        mock_github = MagicMock()
        mock_site = MagicMock()
        ctrl = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)
        ctrl.now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        
        state = {
            "cycle": "2026-10-14",
            "status": "article_pr_open",
            "article": {
                "pr_number": 1113,
                "status": "running",
                "merge_dispatch_count": 2,
            },
            "image": {"status": "complete"},
            "long_video": {"status": "pending"},
            "short": {"status": "pending"},
            "history": [],
        }
        ctrl.github.load_controller_state.return_value = state
        ctrl.github.posts_on_main.return_value = []
        ctrl.github.open_article_prs.return_value = [{
            "number": 1113,
            "title": "Publish Kesher article: Broken Text",
            "html_url": "https://github.com/yanivsa/kesher-website/pull/1113",
            "head": {"sha": "b76ca3215545db83c3a68339d43bfb9f929e613f"},
            "base": {"sha": "base123"},
        }]
        ctrl.github.article_slot_open.return_value = True

        # Mock PR comments showing 2 repair attempts on this head (total 3 attempts)
        ctrl._pr_repair_status = MagicMock(return_value=(2, {"b76ca3215545db83c3a68339d43bfb9f929e613f"}))
        ctrl.github.dispatch = MagicMock()

        new_state, action = ctrl.tick()

        self.assertEqual(new_state["status"], "blocked")
        self.assertEqual(new_state["article"]["status"], "exhausted")
        self.assertEqual(new_state["last_error"]["code"], "ARTICLE_ATTEMPTS_EXHAUSTED")
        self.assertEqual(action.kind, "blocked")
        ctrl.github.dispatch.assert_not_called()

    def test_6_controller_caps_auto_merge_dispatches_at_three(self):
        """Auto-merge must never be dispatched more than 3 times; 3rd dispatch failure blocks cycle."""
        mock_github = MagicMock()
        mock_site = MagicMock()
        ctrl = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)
        ctrl.now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)

        state = {
            "cycle": "2026-10-14",
            "status": "article_pr_open",
            "article": {
                "pr_number": 1113,
                "status": "running",
                "merge_dispatch_count": 3,  # already dispatched 3 times!
            },
            "image": {"status": "complete"},
            "long_video": {"status": "pending"},
            "short": {"status": "pending"},
            "history": [],
        }
        ctrl.github.load_controller_state.return_value = state
        ctrl.github.posts_on_main.return_value = []
        ctrl.github.open_article_prs.return_value = [{
            "number": 1113,
            "title": "Publish Kesher article: Test",
            "head": {"sha": "newhead123"},
            "base": {"sha": "base123"},
        }]
        ctrl.github.article_slot_open.return_value = True
        ctrl._pr_repair_status = MagicMock(return_value=(1, {"oldhead"}))
        ctrl._pr_content_structure_errors = MagicMock(return_value=[])
        ctrl.github.dispatch = MagicMock()

        new_state, action = ctrl.tick()

        self.assertEqual(new_state["status"], "blocked")
        self.assertEqual(new_state["article"]["status"], "exhausted")
        self.assertEqual(new_state["last_error"]["code"], "ARTICLE_ATTEMPTS_EXHAUSTED")
        self.assertEqual(action.kind, "blocked")
        ctrl.github.dispatch.assert_not_called()

    def test_7_successful_merge_advances_to_deploy_then_public_verification(self):
        """When article merges, controller deploys and waits for public verification before media."""
        mock_github = MagicMock()
        mock_site = MagicMock()
        ctrl = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)
        ctrl.now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)

        post = {
            "id": "new-published-article",
            "slug": "new-published-article",
            "title": "New Published Article Title",
            "date": "2026-10-14",
            "content": "<p>Content</p>",
            "category": "זוגיות",
            "excerpt": "Valid excerpt of reasonable length for adoptable post",
            "image": "/images/generated/blog/new-published-article.jpg",
        }
        state = {
            "cycle": "2026-10-14",
            "status": "article_pr_open",
            "article": {
                "slug": "new-published-article",
                "status": "running",
            },
            "image": {"status": "complete"},
            "long_video": {"status": "pending"},
            "short": {"status": "pending"},
            "history": [],
        }
        ctrl.github.load_controller_state.return_value = state
        ctrl.github.posts_on_main.return_value = [post]
        ctrl.github.active_workflow_run.return_value = None
        ctrl.github.dispatch = MagicMock()

        # Public site returns 404 (not yet deployed)
        ctrl.site.get.return_value = (404, "Not Found")

        new_state, action = ctrl.tick()

        # Controller must transition to deploying and dispatch Deploy, NOT Long Video
        self.assertEqual(new_state["status"], "article_deploying")
        self.assertEqual(action.kind, "dispatch_deploy")
        ctrl.github.dispatch.assert_called_once_with(v5.core.DEPLOY_WORKFLOW, None)
        self.assertEqual(new_state["long_video"]["status"], "pending")

    def test_8_short_gate_requires_exact_public_verified_long_video(self):
        """Short must never be dispatched before exact Long Video is public and verified."""
        mock_github = MagicMock()
        mock_site = MagicMock()
        ctrl = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)
        ctrl.now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)

        state = {
            "cycle": "2026-10-14",
            "status": "long_video_running",
            "article": {
                "slug": "dating-burnout",
                "status": "complete",
            },
            "long_video": {
                "status": "running",  # Still running, not complete!
                "provider_id": "task-uuid-123",
            },
            "short": {"status": "pending"},
            "history": [],
        }
        ctrl.github.load_controller_state.return_value = state
        ctrl.github.newest_video_state.return_value = {
            "items": [{
                "slug": "dating-burnout",
                "status": "GENERATION_PENDING",
                "uploaded": False,
            }]
        }
        ctrl.github.dispatch = MagicMock()

        # Guarded dispatch for Short must raise when long video is not verified
        with self.assertRaises(Exception):
            ctrl._guarded_dispatch(
                state,
                v5.SHORT_WORKFLOW,
                {"operation": "derive", "slug": "dating-burnout"},
                raw_dispatch=ctrl.github.dispatch,
            )

    def test_9_budget_enforcement_max_three_attempts_fail_closed(self):
        """Budget cap of 3 attempts per stage fails closed without 4th attempt loophole."""
        self.assertEqual(v5.v3.MAX_STAGE_ATTEMPTS, 3)
        self.assertEqual(pr_ctrl_v3.MAX_TOTAL_CONTENT_ATTEMPTS, 3)
        self.assertEqual(pr_ctrl_v3.MAX_REPAIRS, 2)

    def test_10_no_fourth_attempt_through_rebind_or_redispatch(self):
        """When merge_dispatch_count reaches 3, controller blocks with ARTICLE_ATTEMPTS_EXHAUSTED."""
        mock_github = MagicMock()
        mock_site = MagicMock()
        ctrl = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)
        state = {
            "cycle": "2026-10-14",
            "status": "article_pr_open",
            "article": {
                "status": "article_pr_open",
                "merge_dispatch_count": 3,
                "pr_number": 1113,
            },
            "history": [],
        }
        ctrl._pr_repair_status = MagicMock(return_value=(0, set()))
        action = ctrl._handle_open_article_pr(state, {"number": 1113, "head": {"sha": "abc"}, "base": {"sha": "main"}})
        self.assertEqual(action.kind, "blocked")
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["article"]["status"], "exhausted")
        self.assertEqual(state["last_error"]["code"], "ARTICLE_ATTEMPTS_EXHAUSTED")

    def test_11_cycle_rollover_starts_fresh_next_day_after_exhaustion(self):
        """Exhausted cycle 2026-10-14 does not prevent cycle 2026-10-15 from starting cleanly."""
        mock_github = MagicMock()
        mock_site = MagicMock()
        ctrl = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)
        ctrl.now = datetime(2026, 10, 15, 7, 0, tzinfo=timezone.utc)

        exhausted_state = {
            "cycle": "2026-10-14",
            "status": "blocked",
            "last_error": {"code": "ARTICLE_ATTEMPTS_EXHAUSTED", "message": "budget exhausted"},
            "article": {"status": "exhausted", "attempts": 3},
            "image": {"status": "complete"},
            "long_video": {"status": "pending"},
            "short": {"status": "pending"},
            "history": [],
        }
        mock_github.load_controller_state.return_value = exhausted_state
        mock_github.posts_on_main.return_value = []
        mock_github.open_article_prs.return_value = []
        mock_github.active_workflow_run.return_value = None
        mock_github.workflow_runs.return_value = []
        mock_github.dispatch = MagicMock()

        new_state, action = ctrl.tick()
        self.assertEqual(new_state["cycle"], "2026-10-15")
        self.assertEqual(new_state["status"], "article_generating")
        self.assertEqual(action.kind, "dispatch_article")
        self.assertEqual(new_state["article"]["status"], "running")
        self.assertEqual(new_state["article"]["attempts"], 1)


    def test_12_github_run_unavailable_notification_rejected_no_state_mutation(self):
        """When child notification references a run that cannot be retrieved, it fails closed without mutating state."""
        mock_github = MagicMock()
        mock_site = MagicMock()
        ctrl = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)
        ctrl.now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        state = {
            "cycle": "2026-10-14",
            "status": "article_generating",
            "article": {"status": "running", "run_id": 111},
            "history": [],
            "processed_child_notifications": [],
        }
        ctrl.github.load_controller_state.return_value = state
        # The referenced run cannot be retrieved (returns None)
        ctrl.github.workflow_run_by_id = MagicMock(return_value=None)

        with patch.dict(os.environ, {
            "KESHER_TRIGGER_EVENT": "workflow_run",
            "KESHER_CHILD_WORKFLOW": "Kesher Article Generation",
            "KESHER_CHILD_RUN_ID": "99999",
            "KESHER_CHILD_CONCLUSION": "success",
            "KESHER_CHILD_SLOT": "2026-10-14",
        }):
            valid, reject_reason = ctrl._validate_child_notification(state)
            self.assertFalse(valid)
            self.assertIn("cannot be retrieved or verified", reject_reason)
            self.assertEqual(state["article"]["run_id"], 111)
            self.assertEqual(len(state["processed_child_notifications"]), 0)

    def test_13_delayed_workflow_visibility_beyond_normal_grace_no_second_post(self):
        """When visibility lag exceeds grace period and run is not yet visible, no second POST is made."""
        mock_github = MagicMock()
        mock_site = MagicMock()
        ctrl = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)
        ctrl.now = datetime(2026, 10, 14, 12, 10, tzinfo=timezone.utc)
        ctrl._active_state_ref = {
            "cycle": "2026-10-14",
            "status": "long_video_running",
            "long_video": {"status": "running", "attempt_count": 1},
            "pending_dispatches": {
                v5.LONG_VIDEO_WORKFLOW: {
                    "workflow": v5.LONG_VIDEO_WORKFLOW,
                    "cycle": "2026-10-14",
                    "inputs": {"operation": "upload", "target_slug": "test-slug"},
                    "intent_at": "2026-10-14T12:00:00+00:00",
                    "dispatched_at": "2026-10-14T12:00:01+00:00",
                    "status": "dispatched",
                }
            }
        }
        mock_github.workflow_runs = MagicMock(return_value=[])
        raw_dispatch = MagicMock()

        with self.assertRaises(stabilized_mod._DuplicateDispatchSuppressed) as ctx:
            ctrl._guarded_dispatch(
                ctrl._active_state_ref,
                v5.LONG_VIDEO_WORKFLOW,
                {"operation": "upload", "target_slug": "test-slug"},
                raw_dispatch,
            )
        raw_dispatch.assert_not_called()
        self.assertIn("already dispatched for this cycle", ctx.exception.reason)

    def test_14_lost_dispatch_response_no_second_post(self):
        """When dispatch outcome was uncertain (lost response), controller suppresses second POST until reconciled."""
        mock_github = MagicMock()
        mock_site = MagicMock()
        ctrl = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)
        ctrl.now = datetime(2026, 10, 14, 12, 5, tzinfo=timezone.utc)
        ctrl._active_state_ref = {
            "cycle": "2026-10-14",
            "status": "article_deploying",
            "pending_dispatches": {
                v5.core.DEPLOY_WORKFLOW: {
                    "workflow": v5.core.DEPLOY_WORKFLOW,
                    "cycle": "2026-10-14",
                    "inputs": {},
                    "intent_at": "2026-10-14T12:00:00+00:00",
                    "status": "uncertain",
                }
            }
        }
        mock_github.workflow_runs = MagicMock(return_value=[])
        raw_dispatch = MagicMock()

        with self.assertRaises(stabilized_mod._DuplicateDispatchSuppressed) as ctx:
            ctrl._guarded_dispatch(
                ctrl._active_state_ref,
                v5.core.DEPLOY_WORKFLOW,
                {},
                raw_dispatch,
            )
        raw_dispatch.assert_not_called()
        self.assertIn("uncertain", ctx.exception.reason)

    def test_15_restart_with_pending_intent_reconciles_without_second_post(self):
        """Restarting with pending intent reconciles against visible run without second POST."""
        mock_github = MagicMock()
        mock_site = MagicMock()
        ctrl = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)
        ctrl.now = datetime(2026, 10, 14, 12, 2, tzinfo=timezone.utc)
        active_state = {
            "cycle": "2026-10-14",
            "status": "image_running",
            "image": {"status": "running"},
            "pending_dispatches": {
                v5.v3.IMAGE_WORKFLOW: {
                    "workflow": v5.v3.IMAGE_WORKFLOW,
                    "cycle": "2026-10-14",
                    "inputs": {"pr_number": "1117"},
                    "intent_at": "2026-10-14T12:01:00+00:00",
                    "status": "intent",
                }
            }
        }
        ctrl._active_state_ref = active_state
        mock_github.workflow_runs = MagicMock(return_value=[{
            "id": 55555,
            "event": "workflow_dispatch",
            "status": "in_progress",
            "created_at": "2026-10-14T12:01:05+00:00",
        }])
        raw_dispatch = MagicMock()

        with self.assertRaises(stabilized_mod._DuplicateDispatchSuppressed):
            ctrl._guarded_dispatch(
                active_state,
                v5.v3.IMAGE_WORKFLOW,
                {"pr_number": "1117"},
                raw_dispatch,
            )
        raw_dispatch.assert_not_called()
        self.assertEqual(active_state["pending_dispatches"][v5.v3.IMAGE_WORKFLOW]["observed_active_run_id"], 55555)
        self.assertEqual(active_state["pending_dispatches"][v5.v3.IMAGE_WORKFLOW]["status"], "active")

    def test_16_duplicate_pixels_with_different_encoding_rejected_everywhere(self):
        """Identical pixel data across different encodings (e.g. metadata or format changes) is rejected."""
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo
        img = Image.new("RGB", (1200, 630), color=(100, 150, 200))
        png_io = io.BytesIO()
        img.save(png_io, format="PNG")
        png_bytes = png_io.getvalue()

        info = PngInfo()
        info.add_text("comment", "extra metadata")
        png_io_meta = io.BytesIO()
        img.save(png_io_meta, format="PNG", pnginfo=info)
        png_meta_bytes = png_io_meta.getvalue()

        self.assertNotEqual(hashlib.sha256(png_bytes).hexdigest(), hashlib.sha256(png_meta_bytes).hexdigest())
        self.assertEqual(article_contract.image_pixel_sha256(png_bytes), article_contract.image_pixel_sha256(png_meta_bytes))

        client = V3GitHubClient("token", "repo")
        with tempfile.TemporaryDirectory() as tmpdir:
            pub_dir = Path(tmpdir) / "public" / "images" / "generated" / "blog"
            pub_dir.mkdir(parents=True)
            (pub_dir / "existing.png").write_bytes(png_bytes)

            with patch("scripts.kesher_content_controller_v3_entry.Path") as mock_path:
                mock_path.return_value.resolve.return_value.parents.__getitem__.return_value = Path(tmpdir)
                pr = {
                    "number": 123,
                    "head": {"sha": "headsha"},
                    "body": "Image Provider: Local\nImage SHA-256: " + hashlib.sha256(png_meta_bytes).hexdigest() + "\nImage Source URL: local://public/images/generated/blog/new.png\nImage Evidence Head: headsha",
                }
                client.contents_json = MagicMock(side_effect=[
                    [{"id": "existing", "image": "/images/generated/blog/existing.png"}],
                    [{"id": "existing", "image": "/images/generated/blog/existing.png"},
                     {"id": "new", "image": "/images/generated/blog/new.png", "imageAlt": "Valid descriptive image alt text for article"}]
                ])
                client.request = MagicMock(return_value={"encoding": "base64", "content": base64.b64encode(png_meta_bytes).decode("ascii")})
                ready, _ = client.article_pr_image_ready(pr)
                self.assertFalse(ready)

    def test_17_rebind_after_image_exhaustion_zero_provider_generation_calls(self):
        """When image attempts are exhausted and PR head moves, rebind refreshes head without provider generation."""
        mock_github = MagicMock()
        mock_github.article_pr_image_rebindable.return_value = (True, {"provider": "Local"})
        mock_github.article_pr_image_ready.return_value = (False, {})
        mock_github.article_pr_normalization_required.return_value = (False, "")
        mock_github.active_image_run.return_value = None
        mock_github.dispatch = MagicMock()

        from scripts.kesher_content_controller_v4 import V4Controller
        ctrl = V4Controller(mock_github, MagicMock())
        state = {
            "cycle": "2026-10-14",
            "status": "article_pr_open",
            "image": {
                "status": "exhausted",
                "attempt_count": 3,
                "evidence_rebind_head_sha": "old_head_sha",
            },
            "article": {"pr_number": 1113},
            "history": [],
        }
        pr = {
            "number": 1113,
            "head": {"sha": "2bdd1fba3f3faa89e2b6907e7aabd498603443d4"},
        }
        action = ctrl._handle_open_article_pr(state, pr)
        self.assertEqual(action.kind, "dispatch_image_rebind")
        self.assertEqual(state["image"]["attempt_count"], 3)
        self.assertEqual(state["image"]["evidence_rebind_head_sha"], "2bdd1fba3f3faa89e2b6907e7aabd498603443d4")

    def test_18_long_and_short_fresh_generation_caps_cannot_be_bypassed_through_recovery_paths(self):
        """Guarded dispatch strictly forbids 4th fresh generation for Long Video and Short."""
        mock_github = MagicMock()
        mock_site = MagicMock()
        ctrl = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)
        ctrl.now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        raw_dispatch = MagicMock()

        # 1. Long Video cap at 3
        state_video = {
            "cycle": "2026-10-14",
            "status": "long_video_running",
            "long_video": {"attempt_count": 3, "status": "running"},
            "pending_dispatches": {},
        }
        with self.assertRaises(stabilized_mod.v5.core.ControllerError) as ctx:
            ctrl._guarded_dispatch(
                state_video,
                v5.LONG_VIDEO_WORKFLOW,
                {"operation": "full", "target_slug": "test-slug"},
                raw_dispatch,
            )
        self.assertIn("VIDEO_ATTEMPTS_EXHAUSTED", str(ctx.exception))

        # 2. Short cap at 3
        state_short = {
            "cycle": "2026-10-14",
            "status": "short_running",
            "short": {"attempt_count": 3, "status": "running"},
            "pending_dispatches": {},
        }
        with self.assertRaises(stabilized_mod.v5.core.ControllerError) as ctx:
            ctrl._guarded_dispatch(
                state_short,
                v5.SHORT_WORKFLOW,
                {"operation": "derive", "derive_slug": "test-slug"},
                raw_dispatch,
            )
        self.assertIn("SHORT_ATTEMPTS_EXHAUSTED", str(ctx.exception))

    def test_19_public_article_disappears_or_changes_after_restart_media_remains_blocked(self):
        """If public article returns 404 or missing SHA on controller restart, media progression remains blocked."""
        mock_github = MagicMock()
        mock_site = MagicMock()
        ctrl = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)
        ctrl.now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)

        post = {
            "id": "restarted-article",
            "slug": "restarted-article",
            "title": "Restarted Article Title",
            "date": "2026-10-14",
            "content": "<p>Content</p>",
            "category": "זוגיות",
            "excerpt": "Valid excerpt of reasonable length for adoptable post",
            "image": "/images/generated/blog/restarted-article.jpg",
        }
        state = {
            "cycle": "2026-10-14",
            "status": "article_live",
            "article": {
                "slug": "restarted-article",
                "status": "complete",
                "quality_content_sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            },
            "image": {"status": "complete"},
            "long_video": {"status": "pending"},
            "short": {"status": "pending"},
            "history": [],
        }
        ctrl.github.load_controller_state.return_value = state
        ctrl.github.posts_on_main.return_value = [post]
        ctrl.github.active_workflow_run.return_value = None
        ctrl.github.dispatch = MagicMock()

        # Public site returns 404
        ctrl.site.get.return_value = (404, "Not Found")

        new_state, action = ctrl.tick()

        # Controller must transition to deploying and must NOT advance to long video
        self.assertEqual(new_state["status"], "article_deploying")
        self.assertEqual(action.kind, "dispatch_deploy")
        self.assertEqual(new_state["long_video"]["status"], "pending")
        self.assertFalse(new_state["article"]["live"])

    def test_20_pr_content_structure_preflight_failures(self):
        """Preflight detects catalog unreadable, invalid format, zero, or multiple new posts and blocks fail-closed."""
        mock_github = MagicMock()
        mock_site = MagicMock()
        ctrl = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)
        ctrl.now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        mock_github.article_pr_normalization_required.return_value = (False, "")
        mock_github.request.return_value = []
        pr = {"number": 1113, "head": {"sha": "head1113"}, "base": {"sha": "base1113"}}

        # 1. Catalog unreadable
        mock_github.contents_json.side_effect = Exception("network timeout")
        state1 = {"cycle": "2026-10-14", "status": "article_pr_open", "article": {}}
        action1 = ctrl._handle_open_article_pr(state1, pr)
        self.assertEqual(action1.kind, "blocked")
        self.assertIn("CONTENT_PREFLIGHT_CATALOG_UNREADABLE", action1.reason)
        self.assertEqual(state1["status"], "blocked")

        # 2. Catalog invalid (non-list)
        mock_github.contents_json.side_effect = None
        mock_github.contents_json.return_value = {"not": "a list"}
        state2 = {"cycle": "2026-10-14", "status": "article_pr_open", "article": {}}
        action2 = ctrl._handle_open_article_pr(state2, pr)
        self.assertEqual(action2.kind, "blocked")
        self.assertIn("CONTENT_PREFLIGHT_CATALOG_INVALID", action2.reason)
        self.assertEqual(state2["status"], "blocked")

        # 3. Zero new posts
        base_posts = [{"id": "post-1", "slug": "post-1"}]
        mock_github.contents_json.side_effect = lambda path, ref: list(base_posts)
        state3 = {"cycle": "2026-10-14", "status": "article_pr_open", "article": {}}
        action3 = ctrl._handle_open_article_pr(state3, pr)
        self.assertEqual(action3.kind, "blocked")
        self.assertIn("CONTENT_PREFLIGHT_ZERO_NEW_POSTS", action3.reason)
        self.assertEqual(state3["status"], "blocked")

        # 4. Multiple new posts
        mock_github.contents_json.side_effect = lambda path, ref: (
            [{"id": "post-1"}, {"id": "post-2"}, {"id": "post-3"}] if ref == "head1113" else [{"id": "post-1"}]
        )
        state4 = {"cycle": "2026-10-14", "status": "article_pr_open", "article": {}}
        action4 = ctrl._handle_open_article_pr(state4, pr)
        self.assertEqual(action4.kind, "blocked")
        self.assertIn("CONTENT_PREFLIGHT_MULTIPLE_NEW_POSTS", action4.reason)
        self.assertEqual(state4["status"], "blocked")

    def test_21_pr_repair_status_pagination_and_unreadable_comments(self):
        """PR repair history paginates through all pages, extracts markers, and fails closed if unreadable."""
        mock_github = MagicMock()
        mock_github.api = "https://api.github.com/repos/yanivsa/kesher-website"
        mock_site = MagicMock()
        ctrl = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)
        pr = {"number": 1113, "head": {"sha": "aabbccdd11223344556677889900aabbccddeeff"}}

        # Page 1: 100 empty comments, Page 2: comment with repair marker
        page1 = [{"body": f"comment {i}"} for i in range(100)]
        page2 = [{"body": "<!-- kesher-article-repair attempt=1 head=aabbccdd11223344556677889900aabbccddeeff -->"}]
        mock_github.request.side_effect = [page1, page2]

        max_att, repaired = ctrl._pr_repair_status(pr)
        self.assertEqual(max_att, 1)
        self.assertIn("aabbccdd11223344556677889900aabbccddeeff", repaired)
        self.assertEqual(mock_github.request.call_count, 2)

        # Unreadable comments raises PR_REPAIR_HISTORY_UNREADABLE
        mock_github.request.side_effect = Exception("HTTP 500 Internal Error")
        with self.assertRaises(stabilized_mod.v5.core.ControllerError) as ctx:
            ctrl._pr_repair_status(pr)
        self.assertIn("PR_REPAIR_HISTORY_UNREADABLE", str(ctx.exception))

    def test_22_image_duplicate_check_against_posts_and_posts_recent(self):
        """Hero image collision against src/data/postsRecent.json is rejected."""
        client = V3GitHubClient("token", "repo")
        with tempfile.TemporaryDirectory() as tmpdir:
            pub_dir = Path(tmpdir) / "public" / "images" / "generated" / "blog"
            pub_dir.mkdir(parents=True)
            img_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
            img_sha = hashlib.sha256(img_data).hexdigest()
            (pub_dir / "recent.png").write_bytes(img_data)

            with patch("scripts.kesher_content_controller_v3_entry.Path") as mock_path:
                mock_path.return_value.resolve.return_value.parents.__getitem__.return_value = Path(tmpdir)
                pr = {
                    "number": 123,
                    "head": {"sha": "headsha"},
                    "base": {"sha": "basesha"},
                    "body": f"Image Provider: Local\nImage SHA-256: {img_sha}\nImage Source URL: local://public/images/generated/blog/recent.png\nImage Evidence Head: headsha",
                }
                def mock_contents(path, ref):
                    if path == "src/data/posts.json":
                        if ref == "headsha":
                            return [{"id": "new-post", "image": "/images/generated/blog/recent.png", "imageAlt": "Valid descriptive image alt text for article"}]
                        return []
                    if path == "src/data/postsRecent.json":
                        return [{"id": "recent-post", "image": "/images/generated/blog/recent.png", "imageSha256": img_sha}]
                    return []

                client.contents_json = MagicMock(side_effect=mock_contents)
                client.request = MagicMock(return_value={"encoding": "base64", "content": base64.b64encode(img_data).decode("ascii")})
                ready, _ = client.article_pr_image_ready(pr)
                self.assertFalse(ready, "Hero image matching an asset in postsRecent.json must be rejected")

    def test_23_media_child_notification_identity_correlation(self):
        """Media child notifications without authoritative source identity cannot bind or mutate state."""
        mock_github = MagicMock()
        mock_site = MagicMock()
        ctrl = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)

        state = {
            "cycle": "2026-10-14",
            "status": "long_video_running",
            "article": {
                "slug": "correct-article-slug",
                "quality_content_sha256": "1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
            },
            "long_video": {
                "status": "running",
                "run_id": 100,
                "attempt_count": 1,
            },
            "short": {
                "status": "pending",
                "run_id": None,
                "attempt_count": 0,
            },
        }

        # 1. Missing source_slug for long_video is rejected as untrusted
        env_no_slug = {
            "KESHER_TRIGGER_EVENT": "workflow_dispatch",
            "KESHER_CHILD_WORKFLOW": "Kesher Daily NotebookLM Video Overview",
            "KESHER_CHILD_RUN_ID": "200",
            "KESHER_CHILD_CONCLUSION": "success",
            "KESHER_CHILD_SOURCE_SLUG": "",
            "KESHER_CHILD_SLOT": "2026-10-14",
        }
        with patch.dict(os.environ, env_no_slug):
            valid, msg = ctrl._validate_child_notification(state)
        self.assertFalse(valid)
        self.assertIn("missing mandatory source_slug", msg)

        # 2. Mismatched source_slug for short is rejected
        env_wrong_slug = {
            "KESHER_TRIGGER_EVENT": "workflow_dispatch",
            "KESHER_CHILD_WORKFLOW": "Kesher Daily Article Short V4",
            "KESHER_CHILD_RUN_ID": "300",
            "KESHER_CHILD_CONCLUSION": "success",
            "KESHER_CHILD_SOURCE_SLUG": "different-slug",
            "KESHER_CHILD_SLOT": "2026-10-14",
        }
        with patch.dict(os.environ, env_wrong_slug):
            valid, msg = ctrl._validate_child_notification(state)
        self.assertFalse(valid)
        self.assertIn("mismatch", msg)

        # 3. Matching source_slug but missing source_sha when current_sha is known is rejected
        env_no_sha = {
            "KESHER_TRIGGER_EVENT": "workflow_dispatch",
            "KESHER_CHILD_WORKFLOW": "Kesher Daily NotebookLM Video Overview",
            "KESHER_CHILD_RUN_ID": "200",
            "KESHER_CHILD_CONCLUSION": "success",
            "KESHER_CHILD_SOURCE_SLUG": "correct-article-slug",
            "KESHER_CHILD_SOURCE_SHA": "",
            "KESHER_CHILD_SLOT": "2026-10-14",
        }
        with patch.dict(os.environ, env_no_sha):
            valid, msg = ctrl._validate_child_notification(state)
        self.assertFalse(valid)
        self.assertIn("missing mandatory source_sha", msg)

        # 4. Matching source_slug but mismatched source_sha is rejected
        env_wrong_sha = {
            "KESHER_TRIGGER_EVENT": "workflow_dispatch",
            "KESHER_CHILD_WORKFLOW": "Kesher Daily NotebookLM Video Overview",
            "KESHER_CHILD_RUN_ID": "200",
            "KESHER_CHILD_CONCLUSION": "success",
            "KESHER_CHILD_SOURCE_SLUG": "correct-article-slug",
            "KESHER_CHILD_SOURCE_SHA": "9999222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
            "KESHER_CHILD_SLOT": "2026-10-14",
        }
        with patch.dict(os.environ, env_wrong_sha):
            valid, msg = ctrl._validate_child_notification(state)
        self.assertFalse(valid)
        self.assertIn("source_sha mismatch", msg)

        # 5. Matching source_slug and source_sha is valid
        mock_github.workflow_run_by_id.return_value = {
            "id": 200,
            "name": "Kesher Daily NotebookLM Video Overview",
            "conclusion": "success",
            "event": "workflow_dispatch",
        }
        env_correct = {
            "KESHER_TRIGGER_EVENT": "workflow_dispatch",
            "KESHER_CHILD_WORKFLOW": "Kesher Daily NotebookLM Video Overview",
            "KESHER_CHILD_RUN_ID": "200",
            "KESHER_CHILD_CONCLUSION": "success",
            "KESHER_CHILD_SOURCE_SLUG": "correct-article-slug",
            "KESHER_CHILD_SOURCE_SHA": "1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
            "KESHER_CHILD_SLOT": "2026-10-14",
        }
        with patch.dict(os.environ, env_correct):
            valid, msg = ctrl._validate_child_notification(state)
        self.assertTrue(valid)

    def test_24_public_verification_restart_safety_in_memory_only(self):
        """Live verification is tracked in-memory only and requires fresh HTTP verification after controller restart."""
        mock_github = MagicMock()
        mock_github.active_workflow_run.return_value = None
        mock_site = MagicMock()
        ctrl1 = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)
        ctrl1.now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)

        post = {
            "id": "restart-safety-post",
            "slug": "restart-safety-post",
            "title": "Restart Safety Title",
            "date": "2026-10-14",
            "content": "<p>Content</p>",
            "category": "זוגיות",
            "excerpt": "Valid excerpt of reasonable length for adoptable post",
            "image": "/images/generated/blog/restart-safety-post.jpg",
        }
        post_sha = "38f72e7c650c43ccc76291076fdba0123699af908345a3f19175c418d86a4c68"
        state = {
            "cycle": "2026-10-14",
            "status": "article_deploying",
            "article": {
                "slug": "restart-safety-post",
                "quality_content_sha256": post_sha,
            },
            "image": {"status": "complete"},
            "long_video": {"status": "pending"},
            "short": {"status": "pending"},
            "history": [],
        }
        mock_github.posts_on_main.return_value = [post]
        html_page = (
            "<html><head><title>Restart Safety Title</title>"
            "<meta property='article:published_time' content='2026-10-14'>"
            "<link rel='canonical' href='https://kesher.saharoni.com/blog/restart-safety-post'>"
            f"<meta name='kesher:content-sha256' content='{post_sha}'>"
            "<meta property='og:image' content='https://kesher.saharoni.com/images/generated/blog/restart-safety-post.jpg'>"
            "</head><body><h1>Restart Safety Title</h1></body></html>"
        )
        mock_site.get.return_value = (200, html_page)

        # Tick on ctrl1: verifies publicly and saves state
        is_pub, _ = ctrl1._ensure_article_public_and_deployed(state)
        self.assertTrue(is_pub)
        self.assertIn("restart-safety-post", ctrl1._in_memory_verified_articles)
        self.assertNotIn("_tick_live_verified", state.get("article", {}))

        # Second check on ctrl1: uses in-memory session tracking, no second HTTP call
        mock_site.get.reset_mock()
        is_pub2, _ = ctrl1._ensure_article_public_and_deployed(state)
        self.assertTrue(is_pub2)
        mock_site.get.assert_not_called()

        # Simulate controller restart: new controller instance
        ctrl2 = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)
        ctrl2.now = datetime(2026, 10, 14, 12, 10, tzinfo=timezone.utc)
        self.assertNotIn("restart-safety-post", ctrl2._in_memory_verified_articles)

        # Check on ctrl2: MUST issue fresh HTTP call to verify
        is_pub3, _ = ctrl2._ensure_article_public_and_deployed(state)
        self.assertTrue(is_pub3)
        mock_site.get.assert_called_once()


if __name__ == "__main__":
    unittest.main()

