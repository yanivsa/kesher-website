from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from scripts.kesher_runtime.controller import reconcile
from scripts.kesher_runtime.github import GitHubStateStore
from scripts.kesher_runtime.identity import MediaIdentity, SlotIdentity
from scripts.kesher_runtime.observe import RepositoryObserver
from scripts.kesher_runtime.outbox import workflow_for
from scripts.kesher_runtime.state import StateInvalid, bind_source, new_state, plan_command
from scripts.kesher_runtime.worker import WorkerContext
from tests.test_kesher_autonomous_controller import later, observed, publication
from tests.test_kesher_canonical_state import CODE, NOW, SOURCE, ContentsServer


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / ".github" / "workflows" / "kesher-content-controller.yml"
PRODUCTION_CONTRACT = ROOT / "config" / "kesher-production-contract.json"
ARTICLE = ROOT / ".github" / "workflows" / "kesher-article-generation.yml"
ARTICLE_RUNNER_V4 = ROOT / "scripts" / "jules_article_runner_v4.py"
SHORT = ROOT / ".github" / "workflows" / "kesher-short-v4.yml"
LEGACY_VIDEO = ROOT / ".github" / "workflows" / "kesher-daily-video.yml"
LEGACY_WEEKDAY = ROOT / ".github" / "workflows" / "jules-weekday-article.yml"
LEGACY_WEEKEND = ROOT / ".github" / "workflows" / "jules-weekend-article.yml"


def trigger_block(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text.split("permissions:", 1)[0]


class SingleSchedulerPolicyTests(unittest.TestCase):
    def test_controller_is_the_only_scheduler_in_unified_content_pipeline(self):
        controller = trigger_block(CONTROLLER)
        article = trigger_block(ARTICLE)
        short = trigger_block(SHORT)
        legacy_video = trigger_block(LEGACY_VIDEO)
        self.assertIn("  schedule:", controller)
        self.assertNotIn("  schedule:", article)
        self.assertNotIn("  schedule:", short)
        self.assertNotIn("  schedule:", legacy_video)
        self.assertIn("workflow_dispatch:", article)
        self.assertIn("workflow_dispatch:", short)

    def test_superseded_article_scheduler_files_are_removed(self):
        self.assertFalse(LEGACY_WEEKDAY.exists())
        self.assertFalse(LEGACY_WEEKEND.exists())

    def claimed_command(self, target, operation):
        state = new_state()
        if not isinstance(target, SlotIdentity):
            state = bind_source(state, SOURCE, now=NOW)
        state, command_id = plan_command(state, target, operation, 1, {}, code_sha=CODE, now=NOW)
        store = GitHubStateStore(ContentsServer(state), "owner/repo")
        worker = WorkerContext(store, command_id, "123/1", target, code_sha=CODE, now=lambda: NOW)
        worker.claim()
        return store.load().state, command_id

    def test_controller_observes_every_canonical_child_completion_including_failures(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn("python -m scripts.kesher_runtime.controller_entry --mode live", text)
        # Retired child callbacks are replaced by exact durable run observations.
        self.assertNotIn("workflow_run:", trigger_block(CONTROLLER))
        for target, operation in (
            (SlotIdentity(SOURCE.slot), "settle_article"),
            (SlotIdentity(SOURCE.slot), "normalize_article"),
            (SlotIdentity(SOURCE.slot), "attach_image"),
            (MediaIdentity(SOURCE, "overview"), "publish"),
            (MediaIdentity(SOURCE, "short"), "publish"),
            (SOURCE, "deploy_article"),
        ):
            for conclusion in ("success", "failure", "cancelled", "timed_out"):
                with self.subTest(target=target, operation=operation, conclusion=conclusion):
                    state, command_id = self.claimed_command(target, operation)
                    command = state["commands"][command_id]
                    api = mock.Mock()
                    api.request.return_value = {
                        "id": 123, "run_attempt": 1, "head_sha": CODE, "head_branch": "main",
                        "event": "workflow_dispatch", "display_title": "kesher-command:" + command_id,
                        "path": ".github/workflows/" + workflow_for(command),
                        "status": "completed", "conclusion": conclusion,
                    }
                    observer = RepositoryObserver(api, "owner/repo", inventory_reader=mock.Mock(), auditor=mock.Mock())
                    self.assertEqual(observer.runs(state), [{
                        "command_id": command_id, "run_id": "123/1", "code_sha": CODE,
                        "status": "completed", "conclusion": conclusion,
                    }])
                    api.request.assert_called_once_with("GET", "/repos/owner/repo/actions/runs/123/attempts/1")

    def test_controller_refuses_pull_request_completion_as_canonical_worker_evidence(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn("github.repository == 'yanivsa/kesher-website'", text)
        self.assertIn("github.ref == 'refs/heads/main'", text)
        self.assertIn("ref: ${{ github.sha }}", text)
        self.assertNotIn("workflow_run:", trigger_block(CONTROLLER))
        state, command_id = self.claimed_command(MediaIdentity(SOURCE, "overview"), "publish")
        api = mock.Mock()
        api.request.return_value = {
            "id": 123, "run_attempt": 1, "head_sha": CODE, "head_branch": "main",
            "event": "pull_request", "display_title": "kesher-command:" + command_id,
            "path": ".github/workflows/kesher-media-worker.yml", "status": "completed", "conclusion": "success",
        }
        observer = RepositoryObserver(api, "owner/repo", inventory_reader=mock.Mock(), auditor=mock.Mock())
        with self.assertRaisesRegex(StateInvalid, "wrong run/attempt/workflow/code identity"):
            observer.runs(state)

    def test_canonical_heartbeat_runs_every_five_minutes_and_respects_durable_retry_backoff(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn("cron: '*/5 * * * *'", text)
        self.assertIn("group: kesher-canonical-controller", text)
        self.assertIn("cancel-in-progress: false", text)
        first = reconcile(new_state(), observed(publication(short="verified")), now=NOW)
        store = GitHubStateStore(ContentsServer(first.state), "owner/repo")
        worker = WorkerContext(store, first.command_id, "123/1", MediaIdentity(SOURCE, "overview"),
                               code_sha=CODE, now=lambda: NOW)
        worker.claim()
        worker.finish(failure={"class": "WORKER_FAILED"})
        before_due = reconcile(store.load().state, observed(publication(short="verified"), now=later(299)), now=later(299))
        self.assertIsNone(before_due.command_id)
        due = reconcile(before_due.state, observed(publication(short="verified"), now=later(300)), now=later(300))
        retry = due.state["commands"][due.command_id]
        self.assertEqual(retry["operation"], "reconcile")
        self.assertEqual(retry["target"], MediaIdentity(SOURCE, "overview").to_dict())
        repeated = reconcile(due.state, observed(publication(short="verified"), now=later(300)), now=later(300))
        self.assertEqual(repeated.command_id, due.command_id)
        self.assertEqual(len(repeated.state["commands"]), 2)

    def test_production_contract_declares_five_minute_recovery_heartbeat(self):
        contract = json.loads(PRODUCTION_CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract["scheduler"]["heartbeat_minutes"], 5)

    def test_controller_has_no_runtime_scheduler_mutation(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertNotIn("/disable", text)
        self.assertNotIn("jules-weekday-article.yml", text)
        self.assertNotIn("jules-weekend-article.yml", text)

    def test_article_worker_is_single_attempt_and_persists_result(self):
        text = ARTICLE.read_text(encoding="utf-8")
        self.assertIn("Run exactly one autonomous Jules article text attempt", text)
        self.assertIn("python3 -u scripts/jules_article_runner_v4.py", text)
        wrapper = ARTICLE_RUNNER_V4.read_text(encoding="utf-8")
        self.assertIn("jules_article_runner_v3", wrapper)
        self.assertIn("v3.main()", wrapper)
        self.assertIn("kesher-article-result-${{ github.run_id }}", text)
        self.assertIn("the controller owns retry/backoff", text)

    def test_short_state_retains_exactly_three_snapshots_for_fourteen_days(self):
        text = SHORT.read_text(encoding="utf-8")
        self.assertIn("name: kesher-short-v4-state", text)
        self.assertIn("retention-days: 14", text)
        self.assertIn("Keep only the newest three Short V4 state artifacts", text)
        self.assertIn("| .[3:] | .[].id", text)
        self.assertNotIn("newest seven", text)
        self.assertNotIn("| .[7:]", text)


if __name__ == "__main__":
    unittest.main()
