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
            "<p>Intro</p>\n"
            + "".join(f"<h3>Section {i}</h3>\n<p>" + "word " * 160 + "</p>\n" for i in range(1, 6))
        )
        base_post = {
            "id": "i-told-you-so-criticism-in-relationships",
            "content": content_with_5_h3,
            "image": "/images/generated/blog/i-told-you-so-criticism-in-relationships.jpg",
            "imageSha256": colliding_sha,
        }
        new_post = {
            "id": "new-article-slug",
            "content": content_with_5_h3,
            "image": "/images/generated/blog/new-article-slug.jpg",
            "imageAlt": "A very detailed alt text description of the image content here",
        }
        pr = {
            "state": "open",
            "draft": False,
            "title": "Publish Kesher article: New Article",
            "body": (
                "<!-- image-evidence -->\n"
                "Image Pipeline Version: 2\n"
                "Image Provider: Local\n"
                "Image Generation Result: local_fallback\n"
                "Image Attempt Chain: gemini-1/gemini-2/pexels/pixabay/local-curated\n"
                "Image Source URL: local://public/images/generated/blog/new-article-slug.jpg\n"
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
            {"filename": "public/images/generated/blog/new-article-slug.jpg"},
        ]

        def mock_loader(entry):
            return colliding_bytes

        errors = validate_pr.evaluate_content(
            pr,
            files_data,
            [base_post],
            [new_post],
            image_loader=mock_loader,
        )
        self.assertTrue(
            any("Hero image SHA-256 collides with existing article" in e for e in errors),
            f"Expected hero SHA collision error, got: {errors}",
        )

        # Controller's article_pr_image_ready must also reject this colliding asset
        mock_github = MagicMock()
        mock_github.contents_json.side_effect = lambda path, ref: [base_post] if "base" in ref or ref == "main" else [new_post]
        mock_github.request.return_value = {
            "encoding": "base64",
            "content": base64.b64encode(colliding_bytes).decode("ascii"),
        }
        mock_github.api = "https://api.github.com/repos/yanivsa/kesher-website"
        
        # Test article_pr_image_ready directly
        ready, _ = V3GitHubClient.article_pr_image_ready(mock_github, pr)
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


if __name__ == "__main__":
    unittest.main()
