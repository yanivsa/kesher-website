"""Unit tests for the Kesher Publish Request workflow and Cloud Publisher."""

import json
import unittest
from pathlib import Path
import yaml

import scripts.kesher_cloud_publisher as publisher


class PublishRequestWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow_path = Path(".github/workflows/kesher-publish-request.yml")

    def test_workflow_file_exists_and_schema(self):
        self.assertTrue(self.workflow_path.is_file())
        content = yaml.safe_load(self.workflow_path.read_text(encoding="utf-8"))
        self.assertEqual(content.get("name"), "Kesher Publish Request")
        on_block = content.get("on") or content.get(True) or {}
        self.assertIn("workflow_dispatch", on_block)

        inputs = on_block["workflow_dispatch"]["inputs"]
        self.assertIn("action", inputs)
        allowed_actions = inputs["action"]["options"]
        for expected in ("daily", "run_now", "resume", "audit", "repair"):
            self.assertIn(expected, allowed_actions)

        # Single Scheduler policy: Must NOT contain any schedule triggers
        self.assertNotIn("schedule", on_block)
        self.assertNotIn("push", on_block)

    def test_client_headers(self):
        client = publisher.GitHubActionsClient("dummy_token", "yanivsa/kesher-website")
        headers = client._headers()
        self.assertEqual(headers["Authorization"], "Bearer dummy_token")
        self.assertEqual(headers["X-GitHub-Api-Version"], "2022-11-28")

    def test_handle_audit_slot(self):
        from unittest.mock import patch

        with patch.object(publisher, "run_supervisor_audit", return_value={"complete": True}):
            res = publisher.handle_audit("2026-11-21")
        self.assertEqual(res["action"], "audit")
        self.assertEqual(res["slot"], "2026-11-21")
        self.assertTrue(res["contract_complete"])
        self.assertEqual(res["status"], "success")

    def test_handle_daily_already_complete_guarantee(self):
        from unittest.mock import patch

        with patch.object(publisher, "run_supervisor_audit", return_value={"complete": True}):
            res = publisher.handle_daily("2026-11-21", client=None, dry_run=True)
        self.assertEqual(res["action"], "daily")
        self.assertEqual(res["slot"], "2026-11-21")
        self.assertEqual(res["status"], "already_complete")
        self.assertTrue(res["contract_complete"])

    def test_handle_audit_does_not_claim_success_on_missing_evidence(self):
        from unittest.mock import patch

        with patch.object(publisher, "run_supervisor_audit", return_value={"complete": False}):
            result = publisher.handle_audit("2026-11-21")
        self.assertFalse(result["contract_complete"])
        self.assertEqual(result["status"], "pending_or_unverified")

    def test_supervisor_audit_requires_exact_slug(self):
        from unittest.mock import patch, Mock, MagicMock

        payload = {
            "delivery": {
                "complete": True,
                "article_count": 1,
                "triads": [{"slug": "another-article", "complete": True}],
            },
            "controller_health": {"direct_takeover_required": False},
        }
        with patch.object(publisher.subprocess, "run", return_value=Mock(
            stdout=json.dumps(payload), stderr="", returncode=0,
        )):
            audit = publisher.run_supervisor_audit("2026-11-21", target_slug="requested-article")
            self.assertFalse(audit["complete"])
            audit_ok = publisher.run_supervisor_audit("2026-11-21", target_slug="another-article")
            self.assertTrue(audit_ok["complete"])

    def test_supervisor_audit_refuses_empty_success(self):
        from unittest.mock import patch, Mock

        payload = {"delivery": {"complete": True, "article_count": 0, "triads": []}}
        with patch.object(publisher.subprocess, "run", return_value=Mock(
            stdout=json.dumps(payload), stderr="", returncode=0,
        )):
            self.assertFalse(publisher.run_supervisor_audit("2026-11-22")["complete"])

    def test_get_latest_run_does_not_adopt_stale_or_ambiguous_dispatch(self):
        from unittest.mock import patch, Mock, MagicMock

        client = publisher.GitHubActionsClient("dummy_token")
        def response(rows):
            return MagicMock(__enter__=Mock(return_value=Mock(
                read=Mock(return_value=json.dumps({"workflow_runs": rows}).encode("utf-8"))
            )), __exit__=Mock(return_value=False))

        start = "2026-11-22T05:27:52+00:00"
        with patch.object(publisher.urllib.request, "urlopen", return_value=response([
            {"id": 111, "created_at": "2026-11-21T00:00:00Z", "event": "workflow_dispatch"},
        ])):
            self.assertIsNone(client.get_latest_run("kesher-daily-video.yml", start))

        rows = [
            {"id": 222, "created_at": "2026-11-22T05:27:53Z", "event": "workflow_dispatch"},
            {"id": 333, "created_at": "2026-11-22T05:27:54Z", "event": "workflow_dispatch"},
        ]
        with patch.object(publisher.urllib.request, "urlopen", return_value=response(rows)):
            with self.assertRaisesRegex(RuntimeError, "AMBIGUOUS_WORKFLOW_DISPATCH"):
                client.get_latest_run("kesher-daily-video.yml", start)

        # REST runs report second-granularity created_at even if the dispatch
        # timestamp includes microseconds within that same second.
        with patch.object(publisher.urllib.request, "urlopen", return_value=response([
            {"id": 444, "created_at": "2026-11-22T05:27:52Z", "event": "workflow_dispatch"},
        ])):
            found = client.get_latest_run(
                "kesher-daily-video.yml", "2026-11-22T05:27:52.987654+00:00"
            )
            self.assertEqual(found["id"], 444)

    def test_live_publish_stages_pr_and_never_pushes_main(self):
        from unittest.mock import Mock, patch

        sha = "a" * 64
        post = {
            "id": "cloud-publishing-safe-test",
            "slug": "cloud-publishing-safe-test",
            "title": "מאמר ניסוי",
            "content": "תוכן",
            "source_sha256": sha,
            "date": "2026-11-22",
        }
        article = {
            "slug": "cloud-publishing-safe-test",
            "title": "מאמר ניסוי",
            "source_sha256": sha,
            "canonical_url": "https://kesher.saharoni.com/blog/cloud-publishing-safe-test",
            "hero_image": "/images/generated/blog/cloud-publishing-safe-test.jpg",
            "post": post,
        }
        client = Mock()
        client.lookup_cloud_candidate.return_value = None
        client.create_cloud_candidate_pr.return_value = {
            "number": 8888, "html_url": "https://github.com/yanivsa/kesher-website/pull/8888"
        }
        mock_posts = Mock()
        mock_posts.read_text.return_value = "[]"
        with patch("scripts.kesher_cloud_article_generator.generate_article", return_value=article) as gen:
            with patch.object(publisher.subprocess, "run") as run:
                with patch.object(publisher, "POSTS_FILE", mock_posts):
                    out = publisher.handle_run_now("2026-11-22", client, stage_only=True)
        self.assertEqual(out["status"], "candidate_pr_pending_ci_and_authority")
        self.assertFalse(out["contract_complete"])
        self.assertEqual(out["pr_number"], 8888)
        self.assertFalse(gen.call_args.kwargs["commit"])
        expected = f"content/kesher-cloud-publishing-safe-test-{sha[:12]}"
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn(["git", "push", "origin", f"HEAD:refs/heads/{expected}"], commands)
        self.assertFalse(any(cmd[:2] == ["git", "push"] and "main" in cmd for cmd in commands))
        client.dispatch.assert_called_once_with("ci.yml", ref=expected)

    def test_live_publish_adopts_existing_same_source_candidate(self):
        from unittest.mock import Mock, patch

        sha = "b" * 64
        article = {
            "slug": "existing-cloud-candidate",
            "title": "מאמר",
            "source_sha256": sha,
            "canonical_url": "https://kesher.saharoni.com/blog/existing-cloud-candidate",
            "hero_image": "/images/generated/blog/existing-cloud-candidate.jpg",
        }
        client = Mock()
        client.lookup_cloud_candidate.return_value = {
            "number": 7777, "html_url": "https://github.com/yanivsa/kesher-website/pull/7777"
        }
        with patch("scripts.kesher_cloud_article_generator.generate_article", return_value=article):
            with patch.object(publisher.subprocess, "run") as run:
                out = publisher.handle_run_now("2026-11-22", client, stage_only=True)
        self.assertEqual(out["status"], "candidate_pr_exists")
        self.assertFalse(out["contract_complete"])
        run.assert_not_called()
        client.create_cloud_candidate_pr.assert_not_called()

    def test_live_publish_full_pipeline_mocked(self):
        from unittest.mock import Mock, patch

        sha = "c" * 64
        post = {
            "id": "cloud-publishing-full-test",
            "slug": "cloud-publishing-full-test",
            "title": "מאמר מלא",
            "content": "תוכן מלא",
            "source_sha256": sha,
            "date": "2026-11-22",
        }
        article = {
            "slug": "cloud-publishing-full-test",
            "title": "מאמר מלא",
            "source_sha256": sha,
            "canonical_url": "https://kesher.saharoni.com/blog/cloud-publishing-full-test",
            "hero_image": "/images/generated/blog/cloud-publishing-full-test.jpg",
            "post": post,
        }
        client = Mock()
        client.lookup_cloud_candidate.return_value = None
        client.create_cloud_candidate_pr.return_value = {
            "number": 9999, "html_url": "https://github.com/yanivsa/kesher-website/pull/9999"
        }
        client.poll_workflow.side_effect = [
            {"conclusion": "success", "id": 101},  # CI
            {"conclusion": "success", "id": 102},  # Deploy after PR merge
            {"conclusion": "success", "id": 103},  # Long Video
            {"conclusion": "success", "id": 104},  # Short
            {"conclusion": "success", "id": 105},  # Deploy after metadata update
        ]
        client.merge_pr.return_value = {"merged": True}

        mock_posts = Mock()
        mock_posts.read_text.return_value = "[]"

        with patch("scripts.kesher_cloud_article_generator.generate_article", return_value=article), \
             patch.object(publisher.subprocess, "run"), \
             patch.object(publisher, "POSTS_FILE", mock_posts), \
             patch.object(publisher, "verify_live_article", return_value=True), \
             patch.object(publisher, "extract_video_state", return_value=("item-102", "yt-long-123")), \
             patch.object(publisher, "extract_short_state", return_value="yt-short-456"), \
             patch.object(publisher, "update_article_videos"), \
             patch.object(publisher, "run_supervisor_audit", return_value={"complete": True}):
            out = publisher.handle_run_now("2026-11-22", client, stage_only=False)

        self.assertEqual(out["status"], "success")
        self.assertTrue(out["contract_complete"])
        self.assertEqual(out["youtube_id"], "yt-long-123")
        self.assertEqual(out["short_youtube_id"], "yt-short-456")

    def test_live_publish_refuses_missing_github_client_before_content_creation(self):
        from unittest.mock import patch

        with patch("scripts.kesher_cloud_article_generator.generate_article") as gen:
            with self.assertRaisesRegex(RuntimeError, "GITHUB_CLIENT_REQUIRED"):
                publisher.handle_run_now("2026-11-22", None, dry_run=False)
        gen.assert_not_called()

    def test_handle_run_now_dry_run(self):
        res = publisher.handle_run_now("2026-11-21", client=None, dry_run=True)
        self.assertEqual(res["action"], "run_now")
        self.assertEqual(res["status"], "dry_run_success")
        self.assertTrue(res["slug"])
        self.assertTrue(res["article_url"].startswith("https://kesher.saharoni.com/blog/"))


if __name__ == "__main__":
    unittest.main()
