from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

from scripts import kesher_content_controller as controller
from scripts import kesher_content_controller_v5 as v5
from scripts import kesher_content_controller_v5_runtime as runtime
from scripts import jules_article_runner_v3 as article_runner
from scripts.kesher_runtime import bridge_admission

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = ROOT / ".github" / "workflows"
POLICY_PATH = ROOT / "scripts" / "kesher_runtime" / "authority_policy.json"


class FakeGitHub:
    def __init__(self, posts, recent=None):
        self.posts = posts
        self.recent = recent or []

    def contents_json(self, path, ref="main"):
        if path == "src/data/posts.json":
            return self.posts
        if path == "src/data/postsRecent.json":
            return self.recent
        raise AssertionError(path)


class PreCutoverDailyAuthorityTests(unittest.TestCase):
    def test_controller_authority_is_schema5_only_and_exact(self) -> None:
        env = {
            "GITHUB_REPOSITORY": "yanivsa/kesher-website",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "schedule",
            "GITHUB_WORKFLOW_REF": "yanivsa/kesher-website/.github/workflows/kesher-content-controller.yml@refs/heads/main",
            "KESHER_PRE_CUTOVER_DAILY_AUTHORITY": "true",
        }
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(bridge_admission, "GitHub") as github_cls:
            github_cls.return_value.read_controller_state.return_value = {"schema_version": 5}
            bridge_admission.require_controller_authority(env)
            github_cls.return_value.read_controller_state.assert_called_once()

        bad_env = dict(env)
        bad_env["GITHUB_EVENT_NAME"] = "pull_request"
        with self.assertRaises(SystemExit):
            bridge_admission.require_controller_authority(bad_env)

    def test_schema6_or_handover_markers_automatically_invalidate_pre_cutover_authority(self) -> None:
        env = {
            "GITHUB_REPOSITORY": "yanivsa/kesher-website",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "schedule",
            "GITHUB_WORKFLOW_REF": "yanivsa/kesher-website/.github/workflows/kesher-content-controller.yml@refs/heads/main",
            "KESHER_PRE_CUTOVER_DAILY_AUTHORITY": "true",
        }
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(bridge_admission, "GitHub") as github_cls:
            github_cls.return_value.read_controller_state.return_value = {"schema_version": 6}
            with self.assertRaises(SystemExit):
                bridge_admission.require_controller_authority(env)

        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(bridge_admission, "GitHub"), \
             mock.patch.object(bridge_admission, "GitHubHandover") as handover:
            handover.return_value.read_snapshot.return_value.state = {"schema_version": 6}
            with self.assertRaises(SystemExit):
                bridge_admission.require_controller_authority(env)

    def test_unified_catalog_finds_articles_in_posts_recent_and_deduplicates(self) -> None:
        post = {
            "id": "today",
            "slug": "today",
            "title": "כותרת",
            "date": "2026-10-12",
            "category": "זוגיות",
            "excerpt": "תקציר",
            "content": "<p>תוכן</p>",
        }
        gh = FakeGitHub([post], [dict(post)])
        ctrl = object.__new__(v5.V5Controller)
        ctrl.github = gh
        rows = ctrl.posts_on_main("main")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["slug"], "today")

    def test_jules_generation_checks_recent_catalog_before_provider_mutation(self) -> None:
        recent = [{
            "id": "recent",
            "slug": "recent",
            "title": "כותרת",
            "date": "2026-10-12",
            "category": "זוגיות",
            "excerpt": "תקציר",
            "content": "<p>תוכן</p>",
        }]
        client = mock.Mock()
        client.contents_json.side_effect = lambda path, ref="main": [] if path.endswith("posts.json") else recent
        with mock.patch.object(article_runner, "GitHub", return_value=client), \
             mock.patch.object(article_runner, "create_session") as create_session:
            with self.assertRaisesRegex(RuntimeError, "already published"):
                article_runner.assert_slot_available(client, "2026-10-12")
        create_session.assert_not_called()

    def test_exact_worker_invocations_are_controller_children_only(self) -> None:
        for name in (
            "kesher-article-generation.yml",
            "kesher-article-image.yml",
            "kesher-daily-video.yml",
            "kesher-short-v4.yml",
        ):
            worker_env = {
                "GITHUB_REPOSITORY": "yanivsa/kesher-website",
                "GITHUB_REF": "refs/heads/main",
                "GITHUB_EVENT_NAME": "workflow_dispatch",
                "GITHUB_WORKFLOW_REF": f"yanivsa/kesher-website/.github/workflows/{name}@refs/heads/main",
            }
            bridge_admission.require_invocation(worker_env)
            with mock.patch.dict(os.environ, worker_env, clear=True), \
                 mock.patch.object(bridge_admission, "GitHub"), \
                 mock.patch.object(bridge_admission, "GitHubHandover") as handover:
                handover.return_value.read_snapshot.return_value.state = {"schema_version": 6}
                self.assertEqual(bridge_admission.main([]), 1)

    # 9.C. Single scheduler policy
    def test_only_content_controller_is_active_kesher_production_scheduler(self) -> None:
        controller_text = (WORKFLOWS_DIR / "kesher-content-controller.yml").read_text(encoding="utf-8")
        controller_data = yaml.safe_load(controller_text)
        events = controller_data.get("on", controller_data.get(True))
        self.assertEqual(set(events), {"schedule", "workflow_run", "push", "workflow_dispatch"})
        self.assertEqual(
            events["schedule"],
            [{"cron": "4,9,14,19,24,29,34,39,44,49,54,59 * * * *"}],
        )
        self.assertEqual(
            controller_data["concurrency"],
            {"group": "kesher-content-controller", "cancel-in-progress": False},
        )
        self.assertNotIn("KESHER_MANUAL_EMERGENCY_BRIDGE", controller_text)
        self.assertIn('KESHER_PRE_CUTOVER_DAILY_AUTHORITY: "true"', controller_text)

        for wf_path in sorted(WORKFLOWS_DIR.glob("kesher-*.yml")):
            if wf_path.name == "kesher-content-controller.yml":
                continue
            wf_data = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
            wf_events = wf_data.get("on", wf_data.get(True))
            if isinstance(wf_events, dict) and "schedule" in wf_events:
                schedule = wf_events["schedule"]
                self.assertFalse(
                    schedule,
                    f"{wf_path.name} must not own a production schedule",
                )

        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        controller_roles = [
            row for row in policy["components"]
            if row.get("role") == "controller"
        ]
        self.assertEqual(len(controller_roles), 1)
        self.assertEqual(
            controller_roles[0]["path"],
            ".github/workflows/kesher-content-controller.yml",
        )

    def test_no_emergency_bridge_can_become_scheduled_authority(self) -> None:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        emergency = {
            row["path"] for row in policy["components"]
            if row.get("role") == "emergency_bridge"
        }
        for path in emergency:
            text = (ROOT / path).read_text(encoding="utf-8")
            data = yaml.safe_load(text)
            events = data.get("on", data.get(True))
            self.assertTrue(isinstance(events, dict))
            self.assertNotIn("schedule", events)

    def test_controller_runtime_is_stabilized_v5_not_schema6_gateway(self) -> None:
        controller_text = (WORKFLOWS_DIR / "kesher-content-controller.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/kesher_content_controller_stabilized.py --report-json", controller_text)
        self.assertNotIn("scripts/kesher_runtime/controller_entry.py --mode live", controller_text)

    def test_policy_pins_match_current_authority_files(self) -> None:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        for row in policy["components"]:
            path = ROOT / row["path"]
            if not path.exists() or not row.get("definition_sha256"):
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(
                row["definition_sha256"],
                actual,
                row["path"],
            )


if __name__ == "__main__":
    unittest.main()
