from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_WORKFLOW = ROOT / ".github" / "workflows" / "kesher-content-controller.yml"
SHORT_WORKFLOW = ROOT / ".github" / "workflows" / "kesher-daily-video.yml"
SHORT_COMPONENT = ROOT / "src" / "remotion" / "ArticleShort.tsx"
SHORT_ROOT = ROOT / "src" / "remotion" / "Root.tsx"
V4_CONTROLLER = ROOT / "scripts" / "kesher_content_controller_v4.py"


class V4RuntimeActivationTests(unittest.TestCase):
    def test_content_controller_runs_v4_and_listens_to_short_v4(self):
        workflow = CONTROLLER_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Kesher Daily Article Short V4", workflow)
        self.assertNotIn("Kesher Daily NotebookLM Video Overview", workflow)
        self.assertIn("scripts/kesher_content_controller_v4.py --report-json", workflow)
        self.assertIn("Video fresh attempts: {video.get('attempt_count', 0)}/4", workflow)

    def test_v4_controller_uses_only_the_short_workflow_name(self):
        source = V4_CONTROLLER.read_text(encoding="utf-8")
        self.assertIn('SHORT_WORKFLOW_NAME = "Kesher Daily Article Short V4"', source)
        self.assertIn('core.VIDEO_WORKFLOW = "kesher-daily-video.yml"', source)
        self.assertIn("v3.entry.VIDEO_WORKFLOW_NAME = SHORT_WORKFLOW_NAME", source)

    def test_video_workflow_is_the_single_short_v4_production_worker(self):
        workflow = SHORT_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("name: Kesher Daily Article Short V4", workflow)
        self.assertIn("scripts/kesher_short_pipeline_v4.py", workflow)
        self.assertIn("- release", workflow)
        self.assertIn("release_slug:", workflow)
        self.assertIn("--release-without-short", workflow)
        self.assertNotIn("Generate or resume exact Video Overview", workflow)

    def test_article_short_embeds_the_notebooklm_video_and_audio(self):
        component = SHORT_COMPONENT.read_text(encoding="utf-8")
        self.assertIn('import { Video } from "@remotion/media"', component)
        self.assertIn("videoSrc: string", component)
        self.assertIn("sourceStartFrame: number", component)
        self.assertIn("durationInFrames: number", component)
        self.assertIn("<Video", component)
        self.assertIn("staticFile(videoSrc)", component)
        self.assertIn("trimBefore={sourceStartFrame}", component)
        self.assertIn("durationInFrames={durationInFrames}", component)

    def test_short_composition_duration_is_driven_by_v4_props(self):
        root = SHORT_ROOT.read_text(encoding="utf-8")
        self.assertIn("calculateMetadata={({props}) => ({durationInFrames: props.durationInFrames})}", root)
        self.assertIn('videoSrc: "kesher-input.mp4"', root)
        self.assertIn("sourceStartFrame: 0", root)


if __name__ == "__main__":
    unittest.main()
