from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import jules_article_runner as runner


class JulesArticleRunnerTests(unittest.TestCase):
    def test_current_policy_manifest_is_valid(self):
        policy = runner.load_policy()
        self.assertTrue(policy.startswith("# עדכון מחייב למדיניות מאמרי קשר"))
        meta = json.loads(runner.POLICY_META_PATH.read_text(encoding="utf-8"))
        self.assertEqual(meta["policy_version"], runner.ARTICLE_POLICY_VERSION)
        self.assertEqual(
            meta["git_blob_sha1"],
            runner.git_blob_sha1(runner.POLICY_PATH.read_bytes()),
        )

    def test_policy_loader_rejects_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.md"
            path.write_text("", encoding="utf-8")
            with self.assertRaises(runner.ArticleRunnerError):
                runner.load_policy(path)

    def test_policy_loader_rejects_content_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "policy.md"
            meta = root / "policy.meta.json"
            path.write_text("מדיניות תקינה", encoding="utf-8")
            meta.write_text(
                json.dumps(
                    {
                        "policy_version": runner.ARTICLE_POLICY_VERSION,
                        "git_blob_sha1": "0" * 40,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(runner.ArticleRunnerError, "content drift"):
                runner.load_policy(path, meta)

    def test_policy_loader_rejects_version_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "policy.md"
            meta = root / "policy.meta.json"
            raw = "מדיניות תקינה".encode("utf-8")
            path.write_bytes(raw)
            meta.write_text(
                json.dumps(
                    {
                        "policy_version": runner.ARTICLE_POLICY_VERSION + 1,
                        "git_blob_sha1": runner.git_blob_sha1(raw),
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(runner.ArticleRunnerError, "version mismatch"):
                runner.load_policy(path, meta)

    def test_prompt_injects_authoritative_policy_and_slot(self):
        marker = "UNIQUE_POLICY_MARKER_20260819"
        prompt = runner.build_prompt("2026-08-19", marker)
        self.assertIn(marker, prompt)
        self.assertIn("2026-08-19", prompt)
        self.assertIn("Article policy version: `1`", prompt)
        self.assertIn("BEGIN AUTHORITATIVE ARTICLE POLICY", prompt)
        self.assertIn("Article publication runs MUST NOT create a video", prompt)
        self.assertIn("Publish Kesher article:", prompt)
        self.assertIn("Never ask the user", prompt)

    def test_slot_duplicate_detection_is_exact(self):
        posts = [
            {"id": "a", "date": "2026-08-18"},
            {"id": "b", "date": "2026-08-19"},
        ]
        self.assertTrue(runner.article_exists_for_slot(posts, "2026-08-19"))
        self.assertFalse(runner.article_exists_for_slot(posts, "2026-08-20"))

    def test_runtime_prompt_is_short_task_wrapper_not_policy_duplication(self):
        policy = "POLICY_BODY_SENTINEL"
        prompt = runner.build_prompt("2026-08-19", policy)
        self.assertEqual(prompt.count(policy), 1)
        self.assertLess(len(prompt.replace(policy, "")), 2600)

    def test_create_session_uses_auto_create_pr_and_never_retries_post(self):
        with mock.patch.object(
            runner,
            "request_json",
            return_value={"name": "sessions/123", "url": "https://jules.google/session/123"},
        ) as request:
            session, url = runner.create_session("key", "prompt", "2026-08-19")

        self.assertEqual(session, "sessions/123")
        self.assertEqual(url, "https://jules.google/session/123")
        args, kwargs = request.call_args
        self.assertEqual(args[0], "POST")
        self.assertEqual(args[1], f"{runner.API_BASE}/sessions")
        self.assertEqual(args[3]["automationMode"], "AUTO_CREATE_PR")
        self.assertFalse(args[3]["requirePlanApproval"])
        self.assertEqual(kwargs["max_attempts"], 1)

    def test_existing_active_slot_session_is_reused_without_create(self):
        listed = {
            "sessions": [{
                "name": "sessions/oldest",
                "title": "Kesher article 2026-08-19",
                "state": "IN_PROGRESS",
                "createTime": "2026-08-19T04:00:00Z",
            }]
        }
        with mock.patch.object(runner, "request_json", return_value=listed) as request, mock.patch.object(
            runner, "create_session"
        ) as create:
            session = runner.acquire_session("key", "prompt", "2026-08-19")

        self.assertEqual(session[0], "sessions/oldest")
        create.assert_not_called()
        self.assertEqual(request.call_args.args[0], "GET")

    def test_duplicate_active_slot_sessions_are_reduced_to_one(self):
        listed = {
            "sessions": [
                {
                    "name": "sessions/newer",
                    "title": "Kesher article 2026-08-19",
                    "state": "PLANNING",
                    "createTime": "2026-08-19T04:01:00Z",
                },
                {
                    "name": "sessions/oldest",
                    "title": "Kesher article 2026-08-19",
                    "state": "IN_PROGRESS",
                    "createTime": "2026-08-19T04:00:00Z",
                },
            ]
        }
        with mock.patch.object(runner, "request_json", side_effect=[listed, {}]) as request:
            session = runner.recover_active_slot_session("key", "2026-08-19")

        self.assertEqual(session[0], "sessions/oldest")
        delete_call = request.call_args_list[1]
        self.assertEqual(delete_call.args[0], "DELETE")
        self.assertTrue(delete_call.args[1].endswith("/sessions/newer"))
        self.assertEqual(delete_call.kwargs["max_attempts"], 1)

    def test_uncertain_create_response_recovers_same_session_before_retry(self):
        network = runner.ArticleRunnerError("JULES_NETWORK_ERROR", "response lost")
        with mock.patch.object(
            runner,
            "recover_active_slot_session",
            side_effect=[None, ("sessions/recovered", "")],
        ) as recover, mock.patch.object(
            runner, "create_session", side_effect=network
        ) as create:
            session = runner.acquire_session("key", "prompt", "2026-08-19")

        self.assertEqual(session[0], "sessions/recovered")
        self.assertEqual(recover.call_count, 2)
        create.assert_called_once()

    def test_uncertain_create_without_recovery_is_retryable_but_safe(self):
        network = runner.ArticleRunnerError("JULES_NETWORK_ERROR", "response lost")
        with mock.patch.object(
            runner,
            "recover_active_slot_session",
            return_value=None,
        ), mock.patch.object(
            runner, "create_session", side_effect=network
        ), mock.patch.object(
            runner.time, "sleep"
        ):
            with self.assertRaisesRegex(runner.ArticleRunnerError, "create response was uncertain") as ctx:
                runner.acquire_session("key", "prompt", "2026-08-19")

        self.assertEqual(ctx.exception.code, "JULES_CREATE_UNCERTAIN")
        self.assertTrue(runner.retryable_code(ctx.exception.code))

    def test_timeout_with_unconfirmed_delete_has_distinct_retryable_outcome(self):
        with mock.patch.object(runner.time, "monotonic", side_effect=[0.0, 2.0]), mock.patch.object(
            runner,
            "request_json",
            side_effect=runner.ArticleRunnerError("JULES_NETWORK_ERROR", "delete uncertain"),
        ):
            outcome, _, message = runner.poll("key", "sessions/123", timeout_seconds=1)

        self.assertEqual(outcome, "JULES_TIMEOUT_CANCELLATION_UNCONFIRMED")
        self.assertIn("cancellation could not be confirmed", message)
        self.assertTrue(runner.retryable_code(outcome))


if __name__ == "__main__":
    unittest.main()
