"""Tests for authoritative/latest verify check ordering and ambiguity fail-closed gate."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path
import unittest
import urllib.error
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / ".github" / "scripts" / "validate-article-pr.py"

spec = importlib.util.spec_from_file_location("validate_article_pr", VALIDATOR_PATH)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class ArticlePrVerifyCheckOrderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.head_sha = "a" * 40
        self.base_sha = "0" * 40

        output = io.BytesIO()
        Image.new("RGB", (1200, 675), (96, 127, 150)).save(output, format="PNG")
        self.image_bytes = output.getvalue()
        self.image_sha = hashlib.sha256(self.image_bytes).hexdigest()

        content = "<p>תקשורת זוגית היא הבסיס החשוב ביותר לכל זוג בישראל. " + ("מילה " * 750) + "</p>" + ("<h3>כותרת משנה</h3>" * 5)
        self.post = {
            "id": "couples-communication",
            "title": "תקשורת זוגית בישראל",
            "date": "2026-10-14",
            "category": "זוגיות",
            "excerpt": "תקציר ברור ומפורט העומד בכללי השער",
            "content": content,
            "image": "/images/generated/blog/couples-communication.png",
            "imageAlt": "זוג בשיחה פנים אל פנים המדגישה הקשבה ותקשורת באופן ברור",
            "primaryKeyword": "תקשורת זוגית",
        }
        post_sha = hashlib.sha256(
            json.dumps(self.post, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()

        self.body = f"""Primary Keyword: תקשורת זוגית
Image Pipeline Version: 2
Image Provider: Local
Image Attempt Chain: gemini-1/gemini-2/pexels/pixabay/local-curated
Image Generation Result: local_fallback
Image Source URL: local://public/images/generated/blog/listening-in-relationships.jpg
Image SHA-256: {self.image_sha}
Image Dimensions: 1200x675
Image Visual Match: זוג בשיחה פנים אל פנים המדגישה הקשבה ותקשורת באופן ברור
Image Article ID: couples-communication
Image Article SHA-256: {post_sha}
Image Evidence Head: {self.head_sha}"""

        self.pr = {
            "state": "open",
            "draft": False,
            "title": "Publish Kesher article: couples-communication",
            "body": self.body,
            "base": {"ref": "main", "sha": self.base_sha, "repo": {"full_name": "yanivsa/kesher-website"}},
            "head": {"sha": self.head_sha, "repo": {"full_name": "yanivsa/kesher-website"}},
        }
        self.files = [
            {"filename": "src/data/posts.json"},
            {"filename": "public/images/generated/blog/couples-communication.png"},
        ]
        self.base_posts: list[dict] = []
        self.head_posts: list[dict] = [self.post]

    def _eval(self, checks: list[dict]) -> list[str]:
        return validator.evaluate(
            self.pr,
            self.files,
            checks,
            self.base_posts,
            self.head_posts,
            lambda _: self.image_bytes,
        )

    # -------------------------------------------------------------------------
    # Scenario A: same SHA: old success + newer failure => BLOCK MERGE
    # -------------------------------------------------------------------------
    def test_same_sha_old_success_newer_failure_blocks_merge(self) -> None:
        checks = [
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "success",
                "id": 100,
                "started_at": "2026-10-14T10:00:00Z",
                "completed_at": "2026-10-14T10:05:00Z",
            },
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "failure",
                "id": 101,
                "started_at": "2026-10-14T10:06:00Z",
                "completed_at": "2026-10-14T10:08:00Z",
            },
        ]
        errors = self._eval(checks)
        self.assertIn("Fresh successful verify check is required on the current head", errors)

    # -------------------------------------------------------------------------
    # Scenario B: same SHA: old success + newer in-progress => WAIT/BLOCK
    # -------------------------------------------------------------------------
    def test_same_sha_old_success_newer_in_progress_blocks_merge(self) -> None:
        checks = [
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "success",
                "id": 100,
                "started_at": "2026-10-14T10:00:00Z",
                "completed_at": "2026-10-14T10:05:00Z",
            },
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "in_progress",
                "conclusion": None,
                "id": 101,
                "started_at": "2026-10-14T10:06:00Z",
                "completed_at": None,
            },
        ]
        errors = self._eval(checks)
        self.assertIn("Fresh successful verify check is required on the current head", errors)

    # -------------------------------------------------------------------------
    # Scenario C: same SHA: old failure + newer success => ALLOW
    # -------------------------------------------------------------------------
    def test_same_sha_old_failure_newer_success_allows_merge(self) -> None:
        checks = [
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "failure",
                "id": 100,
                "started_at": "2026-10-14T10:00:00Z",
                "completed_at": "2026-10-14T10:05:00Z",
            },
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "success",
                "id": 101,
                "started_at": "2026-10-14T10:06:00Z",
                "completed_at": "2026-10-14T10:10:00Z",
            },
        ]
        errors = self._eval(checks)
        self.assertEqual(errors, [])

    # -------------------------------------------------------------------------
    # Scenario D: different SHA success => does not satisfy current HEAD
    # -------------------------------------------------------------------------
    def test_different_sha_success_does_not_satisfy_current_head(self) -> None:
        checks = [
            {
                "name": "verify",
                "head_sha": "b" * 40,
                "status": "completed",
                "conclusion": "success",
                "id": 200,
                "started_at": "2026-10-14T10:00:00Z",
            }
        ]
        errors = self._eval(checks)
        self.assertIn("Fresh successful verify check is required on the current head", errors)

    # -------------------------------------------------------------------------
    # Scenario E: multiple indistinguishable/ambiguous latest checks => fail closed
    # -------------------------------------------------------------------------
    def test_ambiguous_checks_without_timestamps_or_ids_fail_closed(self) -> None:
        checks = [
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "success",
            },
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "failure",
            },
        ]
        errors = self._eval(checks)
        self.assertIn("Fresh successful verify check is required on the current head", errors)
        self.assertTrue(any("Ambiguous" in err for err in errors), errors)

    def test_conflicting_timestamp_and_id_signals_fail_closed(self) -> None:
        # Check 1 has earlier timestamp but higher ID; Check 2 has later timestamp but lower ID
        checks = [
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "success",
                "id": 200,
                "started_at": "2026-10-14T10:00:00Z",
            },
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "failure",
                "id": 100,
                "started_at": "2026-10-14T10:10:00Z",
            },
        ]
        errors = self._eval(checks)
        self.assertIn("Fresh successful verify check is required on the current head", errors)
        self.assertTrue(any("Ambiguous" in err for err in errors), errors)

    def test_duplicate_identical_check_runs_fail_closed(self) -> None:
        check = {
            "name": "verify",
            "head_sha": self.head_sha,
            "status": "completed",
            "conclusion": "success",
            "id": 100,
            "started_at": "2026-10-14T10:00:00Z",
        }
        checks = [copy.deepcopy(check), copy.deepcopy(check)]
        errors = self._eval(checks)
        self.assertIn("Fresh successful verify check is required on the current head", errors)
        self.assertTrue(any("Ambiguous" in err for err in errors), errors)

    # -------------------------------------------------------------------------
    # Order independence in input list
    # -------------------------------------------------------------------------
    def test_checks_order_in_input_list_does_not_affect_resolution(self) -> None:
        # Check newer success listed before older failure
        checks_forward = [
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "success",
                "id": 102,
                "started_at": "2026-10-14T10:15:00Z",
            },
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "failure",
                "id": 101,
                "started_at": "2026-10-14T10:05:00Z",
            },
        ]
        self.assertEqual(self._eval(checks_forward), [])

        # Check newer failure listed before older success
        checks_reverse = [
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "failure",
                "id": 102,
                "started_at": "2026-10-14T10:15:00Z",
            },
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "success",
                "id": 101,
                "started_at": "2026-10-14T10:05:00Z",
            },
        ]
        self.assertIn("Fresh successful verify check is required on the current head", self._eval(checks_reverse))

    # -------------------------------------------------------------------------
    # Newer cancelled / timed out runs must block
    # -------------------------------------------------------------------------
    def test_newer_cancelled_run_blocks_merge(self) -> None:
        checks = [
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "success",
                "id": 10,
                "started_at": "2026-10-14T10:00:00Z",
            },
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "cancelled",
                "id": 11,
                "started_at": "2026-10-14T10:10:00Z",
            },
        ]
        errors = self._eval(checks)
        self.assertIn("Fresh successful verify check is required on the current head", errors)

    def test_unrelated_checks_are_ignored(self) -> None:
        checks = [
            {
                "name": "unrelated-lint",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "failure",
                "id": 999,
                "started_at": "2026-10-14T11:00:00Z",
            },
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "success",
                "id": 100,
                "started_at": "2026-10-14T10:00:00Z",
            },
        ]
        self.assertEqual(self._eval(checks), [])

    def test_duplicate_image_in_posts_recent_blocks_merge(self) -> None:
        checks = [
            {
                "name": "verify",
                "head_sha": self.head_sha,
                "status": "completed",
                "conclusion": "success",
                "id": 100,
                "started_at": "2026-10-14T10:00:00Z",
            },
        ]
        extra_posts = [
            {
                "id": "prior-recent-post",
                "title": "פוסט ישן מהזמן האחרון",
                "image": "/images/generated/blog/new-post.png",  # duplicates self.post's image!
            }
        ]
        errors = validator.evaluate(
            self.pr,
            self.files,
            checks,
            self.base_posts,
            self.head_posts,
            lambda _: self.image_bytes,
            extra_base_posts=extra_posts,
        )
        self.assertTrue(any("collides with existing article" in err for err in errors))

    def test_posts_recent_fetch_failure_fails_closed(self) -> None:
        import sys
        from unittest.mock import patch, mock_open

        pr_json = json.dumps(self.pr)
        files_json = json.dumps(self.files)
        checks_json = json.dumps({"check_runs": [{"name": "verify", "head_sha": self.head_sha, "conclusion": "success", "status": "completed", "id": 1}]})

        def mock_fetch(repo, ref, token, filename):
            if filename == "src/data/postsRecent.json":
                raise ValueError("postsRecent.json fetch failure")
            return []

        with patch("sys.argv", ["validate-article-pr.py", "pr.json", "files.json", "checks.json"]), \
             patch("os.environ", {"REPO": "yanivsa/kesher-website", "GITHUB_TOKEN": "dummy"}), \
             patch("builtins.open", mock_open(read_data=pr_json)), \
             patch("json.load", side_effect=[self.pr, self.files, {"check_runs": []}]), \
             patch.object(validator, "fetch_posts", side_effect=mock_fetch):
            with self.assertRaisesRegex(ValueError, "postsRecent.json fetch failure"):
                validator.main()

    def test_article_controller_image_loader_retries_transient_503(self) -> None:
        controller_path = ROOT / ".github" / "scripts" / "article-pr-controller.py"
        spec = importlib.util.spec_from_file_location("article_pr_controller_retry_test", controller_path)
        assert spec and spec.loader
        controller = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = controller
        spec.loader.exec_module(controller)

        transient = urllib.error.HTTPError(
            "https://raw.githubusercontent.com/example/image.jpg",
            503,
            "between bytes timeout",
            hdrs=None,
            fp=io.BytesIO(b""),
        )

        class Response:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def read(self):
                return b"image-bytes"

        with unittest.mock.patch.object(
            controller.urllib.request,
            "urlopen",
            side_effect=[transient, Response()],
        ) as urlopen, unittest.mock.patch.object(controller.time, "sleep"):
            payload = controller.image_loader(
                {"raw_url": "https://raw.githubusercontent.com/example/image.jpg"},
                "token",
            )

        self.assertEqual(payload, b"image-bytes")
        self.assertEqual(urlopen.call_count, 2)


    def test_content_error_requests_repair_even_while_verify_is_in_progress(self) -> None:
        controller_path = ROOT / ".github" / "scripts" / "article-pr-controller.py"
        spec = importlib.util.spec_from_file_location("article_pr_controller_pending_verify_repair_test", controller_path)
        assert spec and spec.loader
        controller = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = controller
        spec.loader.exec_module(controller)

        pr = {
            "number": 1244,
            "state": "open",
            "draft": False,
            "head": {"sha": self.head_sha, "ref": "jules-article"},
            "base": {"sha": self.base_sha},
            "body": "https://jules.google.com/task/14848436556523580886",
        }
        files = [{"filename": "src/data/posts.json"}]
        checks = {"check_runs": [{
            "name": "verify",
            "head_sha": self.head_sha,
            "status": "in_progress",
            "conclusion": None,
            "id": 200,
            "started_at": "2026-10-28T13:26:00Z",
            "completed_at": None,
        }]}
        fake_validator = unittest.mock.MagicMock()
        fake_validator.fetch_posts.side_effect = [[], []]
        fake_validator.fetch_repo_json.return_value = []
        fake_validator.evaluate.return_value = [
            "internal_blog_link_missing: /blog/quiet-resignation",
            "Fresh successful verify check is required on the current head",
        ]

        with unittest.mock.patch.object(controller, "request_json", side_effect=[pr, files]), \
             unittest.mock.patch.object(controller, "is_article_scope", return_value=True), \
             unittest.mock.patch.object(controller, "normalize_pr_body"), \
             unittest.mock.patch.object(controller, "forbidden_paths", return_value=[]), \
             unittest.mock.patch.object(controller, "clean_forbidden_files", return_value=False), \
             unittest.mock.patch.object(controller, "fetch_checks", return_value=checks), \
             unittest.mock.patch.object(controller, "load_validator", return_value=fake_validator), \
             unittest.mock.patch.object(controller, "send_jules_repair", return_value=True) as repair, \
             unittest.mock.patch.object(controller, "merge_and_deploy") as merge:
            result = controller.process("yanivsa/kesher-website", 1244, "token", "jules-key")

        self.assertEqual(result, 0)
        repair.assert_called_once()
        merge.assert_not_called()



if __name__ == "__main__":
    unittest.main()
