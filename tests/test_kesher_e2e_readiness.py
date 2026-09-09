from __future__ import annotations

import unittest
from pathlib import Path

from scripts import kesher_e2e_delivery_guard as guard

ROOT = Path(__file__).resolve().parents[1]
SHORT_ROOT = ROOT / "src" / "remotion" / "Root.tsx"
LIVE_E2E_WORKFLOW = ROOT / ".github" / "workflows" / "kesher-live-e2e-test.yml"
STABILIZED_RUNTIME = ROOT / "scripts" / "kesher_content_controller_stabilized.py"


class KesherE2EReadinessTests(unittest.TestCase):
    def complete_state(self) -> dict:
        return {
            "article": {
                "live": True,
                "url": "https://kesher.saharoni.com/blog/e2e-new-article",
            },
            "long_video": {
                "verified": True,
                "youtube_url": "https://youtu.be/overview-e2e",
                "technical_verified": True,
                "visual_pipeline": "remotion-v1-notebooklm-audio",
                "codec": "h264",
                "width": 1280,
                "height": 720,
                "content_duration_seconds": 120.0,
                "duration": 123.0,
                "signature_duration_seconds": guard.SIGNATURE_DURATION_SECONDS,
                "signature_fullscreen": True,
                "signature_asset_sha256": "o" * 64,
            },
            "short": {
                "verified": True,
                "youtube_url": "https://youtu.be/short-e2e",
                "portrait_verified": True,
                "type": guard.CANONICAL_SHORT_TYPE,
                "source_mode": guard.CANONICAL_SHORT_SOURCE_MODE,
                "visual_pipeline": guard.CANONICAL_SHORT_PIPELINE,
                "signature_verified": True,
                "signature_fullscreen": True,
                "signature_duration_seconds": guard.SIGNATURE_DURATION_SECONDS,
                "signature_video_sha256": "s" * 64,
            },
        }

    def test_short_signature_is_appended_after_full_notebooklm_content(self) -> None:
        root = SHORT_ROOT.read_text(encoding="utf-8")
        self.assertIn("SHORT_SIGNATURE_OUTRO_FRAMES", root)
        self.assertIn(
            "durationInFrames: props.durationInFrames + SHORT_SIGNATURE_OUTRO_FRAMES",
            root,
        )

    def test_overview_signature_is_appended_after_full_notebooklm_content(self) -> None:
        root = SHORT_ROOT.read_text(encoding="utf-8")
        self.assertIn("OVERVIEW_SIGNATURE_OUTRO_FRAMES", root)
        self.assertIn(
            "durationInFrames: props.durationInFrames + OVERVIEW_SIGNATURE_OUTRO_FRAMES",
            root,
        )

    def test_delivery_contract_requires_canonical_overview_remotion_edit(self) -> None:
        state = self.complete_state()
        ready, deliverables = guard.delivery_contract(state)
        self.assertTrue(ready)
        self.assertTrue(deliverables["overview_edit_verified"])

        state["long_video"]["visual_pipeline"] = "raw-notebooklm"
        ready, deliverables = guard.delivery_contract(state)
        self.assertFalse(ready)
        self.assertFalse(deliverables["overview_edit_verified"])

    def test_production_overview_signature_must_be_appended_after_full_content(self) -> None:
        state = self.complete_state()
        state["long_video"]["overview_evidence_required"] = True
        ready, deliverables = guard.delivery_contract(state)
        self.assertTrue(ready)
        self.assertTrue(deliverables["overview_edit_verified"])

        state["long_video"]["duration"] = state["long_video"]["content_duration_seconds"]
        ready, deliverables = guard.delivery_contract(state)
        self.assertFalse(ready)
        self.assertFalse(deliverables["overview_edit_verified"])

    def test_production_marker_refuses_url_only_overview(self) -> None:
        state = self.complete_state()
        state["long_video"] = {
            "verified": True,
            "youtube_url": "https://youtu.be/overview-e2e",
            "overview_evidence_required": True,
        }
        ready, deliverables = guard.delivery_contract(state)
        self.assertFalse(ready)
        self.assertFalse(deliverables["overview_edit_verified"])
        stabilized = STABILIZED_RUNTIME.read_text(encoding="utf-8")
        self.assertIn('state["long_video"]["overview_evidence_required"] = True', stabilized)

    def test_live_e2e_test_entrypoint_drives_regular_article_and_waits_for_three_links(self) -> None:
        workflow = LIVE_E2E_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("name: Kesher Live E2E Test", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("slot:", workflow)
        self.assertIn("request_id:", workflow)
        self.assertIn("kesher-article-generation.yml", workflow)
        self.assertIn("test_mode=false", workflow)
        self.assertIn(".kesher-controller/state.json", workflow)
        self.assertIn("overview_edit_verified", workflow)
        self.assertIn("short_signature_verified", workflow)
        self.assertIn("short_origin_verified", workflow)
        self.assertIn("article_url", workflow)
        self.assertIn("overview_youtube_url", workflow)
        self.assertIn("short_youtube_url", workflow)
        self.assertIn("Adopting active regular article run", workflow)
        self.assertIn("youtube.com/oembed", workflow)
        self.assertNotIn("article_pr_number: 715", workflow)


if __name__ == "__main__":
    unittest.main()