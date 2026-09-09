from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.kesher_video_enhancement import (
    ALLOWED_ENHANCEMENT_STATUSES,
    PROFILE_CONFIG,
    build_edit_plan,
    build_enhancement_manifest,
    execute_enhancement,
    publication_blockers,
)


class VideoEnhancementContractTestCase(unittest.TestCase):
    def test_profiles_keep_v5_v6_overview_and_short_shapes(self) -> None:
        self.assertEqual(PROFILE_CONFIG["overview_16_9"]["width"], 1280)
        self.assertEqual(PROFILE_CONFIG["overview_16_9"]["height"], 720)
        self.assertEqual(PROFILE_CONFIG["short_9_16"]["width"], 1080)
        self.assertEqual(PROFILE_CONFIG["short_9_16"]["height"], 1920)

    def test_missing_assets_is_non_blocking(self) -> None:
        plan = build_edit_plan(
            source_identity="pipeline:slug:sha:overview",
            profile="overview_16_9",
            base_timeline=[{"start": 0.0, "end": 4.0, "type": "push_in"}],
            asset_candidates=[],
        )
        self.assertEqual(plan["enhancement_schema_version"], 1)
        self.assertEqual(plan["enhancement_status"], "enhancement_partial")
        self.assertEqual(plan["assets_used"], [])
        self.assertEqual(publication_blockers(plan["enhancement_status"]), [])

    def test_unverified_or_semantically_wrong_assets_are_dropped(self) -> None:
        plan = build_edit_plan(
            source_identity="pipeline:slug:sha:short",
            profile="short_9_16",
            base_timeline=[{"start": 0.0, "end": 2.0, "type": "visual_hook"}],
            asset_candidates=[
                {
                    "asset_ref": "unsafe.jpg",
                    "type": "image",
                    "source": "https://example.invalid/unsafe.jpg",
                    "provenance": "unknown",
                    "usage_status": "unverified",
                    "semantic_fit": 0.95,
                },
                {
                    "asset_ref": "wrong.jpg",
                    "type": "image",
                    "source": "repo",
                    "provenance": "repo-owned",
                    "usage_status": "approved",
                    "semantic_fit": 0.10,
                },
            ],
        )
        self.assertEqual(plan["assets_used"], [])
        self.assertEqual(len(plan["assets_dropped"]), 2)
        self.assertTrue(all(entry["reason"] for entry in plan["assets_dropped"]))
        self.assertNotIn("unsafe.jpg", {entry.get("asset_ref") for entry in plan["timeline"]})
        self.assertNotIn("wrong.jpg", {entry.get("asset_ref") for entry in plan["timeline"]})

    def test_render_failure_retries_without_optional_assets_then_source_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp4"
            output = root / "final.mp4"
            source.write_bytes(b"valid-source-video")
            plan = build_edit_plan(
                source_identity="pipeline:slug:sha:overview",
                profile="overview_16_9",
                base_timeline=[{"start": 0.0, "end": 3.0, "type": "push_in"}],
                asset_candidates=[
                    {
                        "asset_ref": "approved.jpg",
                        "type": "image",
                        "source": "repo",
                        "provenance": "repo-owned",
                        "usage_status": "approved",
                        "semantic_fit": 0.9,
                    }
                ],
            )
            attempts: list[str] = []

            def renderer(candidate_plan: dict, candidate_output: Path) -> None:
                mode = candidate_plan["render_mode"]
                attempts.append(mode)
                if mode in {"full", "reduced"}:
                    raise RuntimeError(f"synthetic {mode} failure")
                candidate_output.write_bytes(b"source-only-render")

            result = execute_enhancement(
                source_path=source,
                output_path=output,
                edit_plan=plan,
                renderer=renderer,
                source_publishable=False,
            )
            self.assertEqual(attempts, ["full", "reduced", "source_only"])
            self.assertEqual(result["enhancement_status"], "fallback_source_only")
            self.assertTrue(output.exists())
            self.assertTrue(result["fallback_reason"])

    def test_manifest_records_hashes_plan_assets_and_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp4"
            final = root / "final.mp4"
            plan_path = root / "edit-plan.json"
            source.write_bytes(b"source")
            final.write_bytes(b"final")
            plan_path.write_text('{"enhancement_schema_version":1}', encoding="utf-8")
            manifest = build_enhancement_manifest(
                source_path=source,
                final_path=final,
                edit_plan_path=plan_path,
                enhancement_status="fallback_source_only",
                assets_used=[],
                assets_dropped=[{"asset_ref": "bad.jpg", "reason": "unverified"}],
                fallback_reason="optional render failed",
            )
            self.assertEqual(len(manifest["source_sha256"]), 64)
            self.assertEqual(len(manifest["final_sha256"]), 64)
            self.assertEqual(len(manifest["edit_plan_sha256"]), 64)
            self.assertEqual(manifest["enhancement_status"], "fallback_source_only")
            self.assertEqual(manifest["assets_used"], [])
            self.assertEqual(manifest["assets_dropped"][0]["asset_ref"], "bad.jpg")
            self.assertEqual(manifest["fallback_reason"], "optional render failed")

    def test_only_enhancement_states_are_non_blocking(self) -> None:
        expected = {
            "enhancement_complete",
            "enhancement_partial",
            "enhancement_skipped",
            "asset_dropped",
            "fallback_source_only",
        }
        self.assertEqual(ALLOWED_ENHANCEMENT_STATUSES, expected)
        for status in expected:
            self.assertEqual(publication_blockers(status), [])
        self.assertTrue(publication_blockers("wrong_source_identity"))


if __name__ == "__main__":
    unittest.main()
