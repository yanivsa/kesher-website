from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.kesher_automation_policy import POLICY_PATH, load_policy


ROOT = Path(__file__).resolve().parents[1]
LEGACY_POLICY = ROOT / "config" / "kesher-automation-policy.json"
VIDEO_WORKFLOW = ROOT / ".github" / "workflows" / "kesher-daily-video.yml"
VIDEO_REVIEW_POLICY = ROOT / ".github" / "prompts" / "jules-remotion-video-upgrade.md"
ARTICLE_POLICY = ROOT / ".github" / "prompts" / "jules-weekday-article-update.md"
ARTICLE_PR_CONTROLLER_V3 = ROOT / ".github" / "scripts" / "article-pr-controller-v3.py"
BEST_EFFORT_CONTROLLER = ROOT / "scripts" / "kesher_content_controller_v3_best_effort.py"
RUNTIME_V5_CONTROLLER = ROOT / "scripts" / "kesher_content_controller_v5_runtime.py"
SHORT_PIPELINE_V4 = ROOT / "scripts" / "kesher_short_pipeline_v4.py"
SHORT_WORKFLOW_V4 = ROOT / ".github" / "workflows" / "kesher-short-v4.yml"


class ProductionContractV3Tests(unittest.TestCase):
    def test_contract_is_the_canonical_policy_source(self) -> None:
        self.assertEqual(POLICY_PATH.name, "kesher-production-contract.json")
        contract = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(contract["contract_version"], 3)
        self.assertNotIn("review_gate", contract["video"])
        self.assertNotIn("jules_review_required", contract["video"])
        self.assertNotIn("upload_requires_approved_review", contract["video"])

    def test_scheduler_and_retry_ownership_are_locked(self) -> None:
        contract = load_policy()
        self.assertEqual(contract["scheduler"]["owner"], "kesher-content-controller")
        self.assertEqual(contract["scheduler"]["heartbeat_minutes"], 5)
        self.assertEqual(contract["scheduler"]["failure_recovery"], "heartbeat")
        self.assertTrue(contract["invariants"]["controller_owns_retries"])
        self.assertTrue(contract["invariants"]["workers_are_single_attempt"])
        self.assertTrue(contract["invariants"]["heartbeat_is_recovery_only"])

    def test_video_publication_contract_is_technical_and_advisory(self) -> None:
        contract = load_policy()
        video = contract["video"]
        self.assertEqual(video["publication_gate"], "technical")
        self.assertEqual(video["jules_review"], "advisory")
        self.assertEqual(video["queue_order"], "fifo")
        self.assertEqual(video["durable_state_artifacts_to_keep"], 3)
        self.assertEqual(video["durable_state_retention_days"], 14)

    def test_free_broll_is_free_only_bounded_and_never_publication_blocking(self) -> None:
        contract = load_policy()
        broll = contract["video"]["free_stock_broll"]
        self.assertEqual(broll["cost_policy"], "free-only")
        self.assertEqual(broll["provider_order"], ["pexels", "pixabay"])
        self.assertFalse(broll["automatic_paid_fallback"])
        self.assertFalse(broll["publication_blocking"])
        self.assertEqual(broll["missing_credentials"], "skip-and-continue")
        self.assertEqual(broll["provider_failure"], "skip-and-continue")
        self.assertEqual(broll["download_failure"], "skip-and-continue")
        self.assertEqual(broll["render_failure"], "drop-assets-and-continue")
        self.assertEqual(broll["time_budget_seconds"], 12)
        self.assertEqual(broll["max_short_assets"], 1)
        self.assertEqual(broll["max_overview_assets"], 2)
        self.assertTrue(broll["attribution_on_use"])
        self.assertFalse(broll["coverr_enabled"])
        self.assertTrue(contract["invariants"]["free_broll_never_blocks_publication"])
        self.assertTrue(contract["invariants"]["free_broll_never_triggers_paid_fallback"])
        self.assertTrue(contract["invariants"]["external_broll_attributed_when_used"])

    def test_free_stock_secrets_are_scoped_to_render_steps(self) -> None:
        for path in (VIDEO_WORKFLOW, SHORT_WORKFLOW_V4):
            workflow = path.read_text(encoding="utf-8")
            job_header = workflow.split("    steps:", 1)[0]
            self.assertNotIn("PEXELS_API_KEY:", job_header)
            self.assertNotIn("PIXABAY_API_KEY:", job_header)
            self.assertIn("PEXELS_API_KEY: ${{ secrets.PEXELS_API_KEY }}", workflow)
            self.assertIn("PIXABAY_API_KEY: ${{ secrets.PIXABAY_API_KEY }}", workflow)
            self.assertIn('KESHER_BROLL_ENABLED: "true"', workflow)
            self.assertIn('KESHER_BROLL_BUDGET_SECONDS: "12"', workflow)

    def test_image_stage_is_publication_blocking_with_guaranteed_local_fallback(self) -> None:
        contract = load_policy()
        image = contract["image"]
        self.assertTrue(image["required_for_article"])
        self.assertTrue(image["publication_blocking"])
        self.assertFalse(image["no_image_publication_allowed"])
        self.assertEqual(image["failure_mode"], "blocking-retry")
        self.assertEqual(image["worker_owner"], "github-actions")
        self.assertTrue(image["fallback_must_be_local"])

    def test_article_image_handoff_is_machine_readable_and_same_pr_recoverable(self) -> None:
        contract = load_policy()
        article = contract["article"]
        image = contract["image"]
        invariants = contract["invariants"]
        policy = ARTICLE_POLICY.read_text(encoding="utf-8")

        self.assertTrue(article["publication_ready_requires_trusted_image"])
        self.assertEqual(article["jules_pending_image_handoff_status"], "PENDING_TRUSTED_IMAGE_STAGE")
        self.assertEqual(image["pending_handoff_marker"], "Hero Image Status: PENDING_TRUSTED_IMAGE_STAGE")
        self.assertEqual(image["attached_handoff_marker"], "Hero Image Status: ATTACHED_TRUSTED_IMAGE_STAGE")
        self.assertEqual(image["controller_action_on_pending_handoff"], "dispatch_trusted_image_same_pr")
        self.assertEqual(image["controller_action_on_image_guard_failure"], "recover_trusted_image_same_pr")
        self.assertTrue(invariants["article_image_handoff_is_machine_readable"])
        self.assertTrue(invariants["image_guard_failure_repairs_same_pr"])
        self.assertIn("Hero Image Status: PENDING_TRUSTED_IMAGE_STAGE", policy)
        self.assertIn("Hero Image Status: ATTACHED_TRUSTED_IMAGE_STAGE", policy)
        self.assertIn("content ready", policy)
        self.assertIn("publication ready", policy)

    def test_article_auto_merge_requires_completed_trusted_image(self) -> None:
        controller = ARTICLE_PR_CONTROLLER_V3.read_text(encoding="utf-8")
        self.assertIn("controller_image_stage_terminal", controller)
        self.assertIn('image_status == "complete"', controller)
        self.assertNotIn('image_status == "deferred"', controller)
        self.assertIn('image.get("provider_id")', controller)
        self.assertIn('image.get("source_id")', controller)
        self.assertIn('image.get("artifact_sha256")', controller)
        self.assertIn("A deferred,", controller)
        self.assertIn("core.merge_and_deploy = merge_and_deploy_after_image_stage", controller)
        self.assertIn("merge deferred without consuming a content attempt", controller)

    def test_persisted_terminal_image_state_retriggers_auto_merge(self) -> None:
        controller = BEST_EFFORT_CONTROLLER.read_text(encoding="utf-8")
        self.assertIn('AUTO_MERGE_WORKFLOW = "auto-merge-article-prs.yml"', controller)
        self.assertIn('IMAGE_TERMINAL_STATES = {"complete", "deferred"}', controller)
        self.assertIn("image_was_terminal", controller)
        self.assertIn("merge_dispatch_at", controller)
        self.assertIn("self.github.dispatch(AUTO_MERGE_WORKFLOW)", controller)

    def test_legacy_policy_is_not_the_runtime_policy(self) -> None:
        self.assertNotEqual(POLICY_PATH, LEGACY_POLICY)

    def test_video_workflow_cannot_restore_mandatory_jules_gate(self) -> None:
        workflow = VIDEO_WORKFLOW.read_text(encoding="utf-8")
        review_policy = VIDEO_REVIEW_POLICY.read_text(encoding="utf-8")
        forbidden = (
            "mandatory Jules",
            "Jules-approved MP4",
            "upload_requires_approved_review",
            'review_gate"] == "mandatory"',
            "mandatory publication gate",
        )
        for text in forbidden:
            self.assertNotIn(text.lower(), workflow.lower())
            self.assertNotIn(text.lower(), review_policy.lower())
        self.assertIn("Prepare technically verified upload", workflow)
        self.assertIn("Upload exact technically verified MP4", workflow)
        self.assertIn("Jules performs strict advisory review", workflow)


    def test_video_upload_workflow_enforces_exact_identity_lock(self) -> None:
        workflow = VIDEO_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("target_content_sha256:", workflow)
        self.assertIn("target_item_id:", workflow)
        self.assertIn("id: prepare_upload", workflow)
        self.assertIn("KESHER_REQUESTED_TARGET_SLUG: ${{ inputs.target_slug }}", workflow)
        self.assertIn("KESHER_REQUESTED_TARGET_CONTENT_SHA256: ${{ inputs.target_content_sha256 }}", workflow)
        self.assertIn("KESHER_REQUESTED_TARGET_ITEM_ID: ${{ inputs.target_item_id }}", workflow)
        self.assertIn("KESHER_EXACT_UPLOAD_REQUIRED: ${{ inputs.operation == 'upload' }}", workflow)
        self.assertIn("steps.prepare_upload.outputs.ready == 'true'", workflow)
        self.assertIn("EXACT_UPLOAD_IDENTITY_OK", workflow)
        self.assertIn('--slug "$TARGET_SLUG" --item-id "$TARGET_ITEM_ID"', workflow)

    def test_video_workflow_retention_matches_contract(self) -> None:
        workflow = VIDEO_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Keep the newest three durable state artifacts", workflow)
        self.assertIn("| .[3:] | .[].id", workflow)
        self.assertNotIn("| .[7:]", workflow)
        self.assertIn("retention-days: 14", workflow)

    def test_short_controller_uses_same_approved_svg_signature_as_renderer(self) -> None:
        runtime = RUNTIME_V5_CONTROLLER.read_text(encoding="utf-8")
        pipeline = SHORT_PIPELINE_V4.read_text(encoding="utf-8")
        self.assertIn('SIGNATURE_SOURCE = Path("public/images/signature/signature-mask.svg")', pipeline)
        self.assertIn('DEFAULT_SIGNATURE_ASSET = "public/images/signature/signature-mask.svg"', runtime)
        self.assertNotIn('DEFAULT_SIGNATURE_ASSET = "public/shira-signature.mp4"', runtime)


if __name__ == "__main__":
    unittest.main()
